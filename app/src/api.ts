import { getMeta } from "./db";

// En dev, Vite hace proxy de /api al backend. En prod, mismo dominio vía Caddy.
const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getMeta("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function handle(res: Response): Promise<any> {
  if (!res.ok) {
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
  const res = await fetch(`${BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
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
