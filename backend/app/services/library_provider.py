"""Gemini API Free Tier transport for the private TPS library."""

import json
import stat
import asyncio
from pathlib import Path

import httpx
from fastapi import HTTPException

from app.core.config import settings

MODEL = "gemini-3.5-flash-lite"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:streamGenerateContent?alt=sse"


def verified_key() -> str:
    if not settings.LIBRARY_GEMINI_FREE_TIER_CONFIRMED:
        raise HTTPException(503, "Confirma primero que la clave Gemini pertenece a un proyecto Free Tier sin facturación vinculada.")
    path = settings.LIBRARY_GEMINI_KEY_FILE
    if not path:
        raise HTTPException(503, "Falta la clave Gemini del proyecto gratuito en el servidor.")
    try:
        key_file = Path(path)
        if stat.S_IMODE(key_file.stat().st_mode) & 0o077:
            raise ValueError("Key file permissions must be 0600")
        key = key_file.read_text().strip()
        if not key or any(c.isspace() for c in key):
            raise ValueError("Expected one API key")
        return key
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "La clave Gemini no está disponible o no tiene permisos 0600.") from exc


def provider_error(status: int) -> str:
    if status == 503:
        return "Gemini está temporalmente saturado. Intenta de nuevo más tarde."
    if status == 429:
        return "Se alcanzó el límite gratuito de Gemini. Intenta de nuevo cuando se renueve la cuota."
    if status == 403:
        return "El proyecto Gemini no tiene acceso al nivel gratuito o la clave no está autorizada. Revisa AI Studio."
    if status == 401:
        return "La clave Gemini no es válida."
    if status == 404:
        return f"El modelo {MODEL} no está disponible para este proyecto gratuito."
    return f"Gemini no pudo completar la respuesta ({status})."


def request_body(messages: list[dict]) -> dict:
    instruction = "\n".join(m["content"] for m in messages if m["role"] == "developer")
    contents = [{"role": "model" if m["role"] == "assistant" else "user",
                 "parts": [{"text": m["content"]}]}
                for m in messages if m["role"] in ("user", "assistant")]
    body = {"contents": contents,
            "generationConfig": {"maxOutputTokens": 2400,
                                 "thinkingConfig": {"thinkingLevel": "low"}}}
    if instruction:
        body["systemInstruction"] = {"parts": [{"text": instruction}]}
    return body


async def generate(key: str, messages: list[dict]):
    # No tools, files, web grounding, or provider-side conversation state.
    body = request_body(messages)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=15, read=120)) as client:
            for attempt in range(2):
                async with client.stream("POST", ENDPOINT, headers={
                    "x-goog-api-key": key, "Content-Type": "application/json"}, json=body) as response:
                    if response.status_code == 503 and attempt == 0:
                        await response.aread()
                        await asyncio.sleep(1)
                        continue
                    if response.status_code != 200:
                        await response.aread()
                        raise HTTPException(503, provider_error(response.status_code))
                    usage = {}
                    finished = False
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        try:
                            event = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue
                        if event.get("usageMetadata"):
                            usage = event["usageMetadata"]
                        if event.get("promptFeedback", {}).get("blockReason"):
                            raise HTTPException(503, "Gemini bloqueó la consulta; reformúlala sin instrucciones ajenas al manual.")
                        for candidate in event.get("candidates", []):
                            for part in candidate.get("content", {}).get("parts", []):
                                delta = part.get("text")
                                if not part.get("thought") and isinstance(delta, str) and delta:
                                    yield "delta", delta
                            reason = candidate.get("finishReason")
                            if reason == "STOP":
                                finished = True
                            elif reason:
                                raise HTTPException(503, f"Gemini detuvo la respuesta ({reason}).")
                    if finished:
                        yield "completed", usage
                        return
    except httpx.HTTPError as exc:
        raise HTTPException(503, "No se pudo conectar con Gemini.") from exc
    raise HTTPException(503, "Gemini terminó la transmisión antes de completar la respuesta.")
