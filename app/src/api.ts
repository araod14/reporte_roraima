import { delMeta, getMeta } from "./db";

// En dev, Vite hace proxy de /api al backend. En prod, mismo dominio vía Caddy.
const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getMeta("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function libraryRequest(path: string, method = "GET", body?: object): Promise<any> {
  const res = await fetch(`${BASE}/api/library${path}`, {
    method, headers: { ...(await authHeaders()), ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  return handle(res);
}

export async function libraryPdf(id: string): Promise<Blob> {
  const res = await fetch(`${BASE}/api/library/documents/${id}/pdf`, { headers: await authHeaders() });
  if (!res.ok) {
    await expireSessionIf401(res.status);
    throw new ApiError(res.status, "No se pudo abrir el PDF");
  }
  return res.blob();
}

export async function libraryPage(id: string, page: number): Promise<Blob> {
  const res = await fetch(`${BASE}/api/library/documents/${id}/pages/${page}`, { headers: await authHeaders() });
  if (!res.ok) {
    await expireSessionIf401(res.status);
    throw new ApiError(res.status, "No se pudo abrir la página citada");
  }
  return res.blob();
}

export async function libraryStream(id: string, content: string, regenerate: boolean, requestId: string,
  onEvent: (event: string, data: any) => void, signal: AbortSignal): Promise<void> {
  const res = await fetch(`${BASE}/api/library/conversations/${id}/responses`, {
    method: "POST", headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ content, regenerate, request_id: requestId }), signal,
  });
  if (!res.ok) return handle(res);
  if (!res.body) throw new Error("El servidor no admite respuestas progresivas");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    pending += decoder.decode(value, { stream: true });
    const events = pending.split("\n\n");
    pending = events.pop() ?? "";
    for (const block of events) {
      const event = block.match(/^event: (.+)$/m)?.[1];
      const data = block.match(/^data: (.+)$/m)?.[1];
      if (event && data) onEvent(event, JSON.parse(data));
    }
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Token vencido o inválido: se borra (los borradores siguen en IndexedDB) y se
// vuelve al login; si no, la app queda "logueada" recibiendo 401 indefinidamente.
export async function expireSessionIf401(status: number): Promise<void> {
  if (status !== 401 || !(await getMeta("token"))) return;
  await delMeta("token");
  window.location.hash = "#/login";
}

async function handle(res: Response): Promise<any> {
  if (!res.ok) {
    await expireSessionIf401(res.status);
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  const ct = res.headers.get("content-type") ?? "";
  return ct.includes("application/json") ? res.json() : res.text();
}

export async function login(username: string, password: string): Promise<string> {
  const form = new URLSearchParams({ username, password });
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
  } catch {
    throw new ApiError(0, "No se pudo conectar con el servidor. Revisa tu conexión a internet e inténtalo de nuevo.");
  }
  const data = await handle(res);
  return data.access_token;
}

export async function fetchCatalogo(): Promise<any[]> {
  const res = await fetch(`${BASE}/api/catalogo`, { headers: await authHeaders() });
  return handle(res);
}

// Lista de todas las inspecciones del servidor (de todos los usuarios).
export async function fetchInspecciones(): Promise<any[]> {
  const res = await fetch(`${BASE}/api/inspecciones`, { headers: await authHeaders() });
  return handle(res);
}

// Detalle completo de una inspección (incluye registros).
export async function fetchInspeccion(id: string): Promise<any> {
  const res = await fetch(`${BASE}/api/inspecciones/${id}`, { headers: await authHeaders() });
  return handle(res);
}

// Versiones de reporte de una inspección finalizada.
export async function fetchReportes(id: string): Promise<any[]> {
  const res = await fetch(`${BASE}/api/reportes/${id}`, { headers: await authHeaders() });
  return handle(res);
}

export async function syncBatch(inspecciones: any[]): Promise<any> {
  const res = await fetch(`${BASE}/api/sync/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ inspecciones }),
  });
  return handle(res);
}

export async function finalizar(inspeccionId: string): Promise<any> {
  const res = await fetch(`${BASE}/api/inspecciones/${inspeccionId}/finalizar`, {
    method: "POST",
    headers: await authHeaders(),
  });
  return handle(res);
}

// Descarga la vista visual (panel sinóptico) como blob: html interactivo o pdf.
export async function fetchSlides(
  inspeccionId: string,
  formato: "html" | "pdf",
): Promise<Blob> {
  const res = await fetch(`${BASE}/api/inspecciones/${inspeccionId}/slides.${formato}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    await expireSessionIf401(res.status);
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return res.blob();
}

export async function reabrir(inspeccionId: string): Promise<any> {
  const res = await fetch(`${BASE}/api/inspecciones/${inspeccionId}/reabrir`, {
    method: "POST",
    headers: await authHeaders(),
  });
  return handle(res);
}
