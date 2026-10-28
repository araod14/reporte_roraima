"""Minimal Gemini Free Tier check; run only after confirming an unbilled project."""

import asyncio
import json

from app.services.library_provider import MODEL, generate, verified_key


async def main() -> None:
    key = verified_key()
    answer = []
    usage = {}
    async for kind, value in generate(key, [{
        "role": "user", "content": "Responde solo: OK",
    }]):
        if kind == "delta":
            answer.append(value)
        elif kind == "completed":
            usage = value
    print(json.dumps({"model": MODEL, "answer": "".join(answer).strip(), "usage": usage},
                     ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
