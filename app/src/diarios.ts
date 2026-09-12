import { db, getMeta } from "./db";
import { ApiError } from "./api";
import { CATALOGO_FALLBACK } from "./catalogo";
import type { Estado, SyncState } from "./types";

export type EstadoLCN = "OK" | "SUSPECT";
export type EstadoUCN = "OK" | "FAIL";
export interface DatosDiario {
  fecha: string;
  hora: string;
  responsable: string;
  lcn_a: EstadoLCN | null;
  lcn_b: EstadoLCN | null;
  // Opcionales para consultar capturas anteriores a la incorporación de UCN.
  ucn1?: EstadoUCN | null;
  ucn2?: EstadoUCN | null;
  ucn3?: EstadoUCN | null;
  gus: Record<string, Estado>;
  temperatura_ish1: number | null;
  temperatura_ish2: number | null;
  observaciones: string;
}
export interface VersionDiario {
  version: number;
  fecha: string;
  hora: string;
  png_url: string;
  png_sha256: string;
  content_hash: string;
  fecha_generacion: string;
  generado_por: string;
}
export interface Diario {
  id: string;
  datos: DatosDiario;
  estado: "BORRADOR" | "FINALIZADA";
  version: number;
  client_updated_at: string;
  server_updated_at?: string;
  created_by?: string;
  versiones: VersionDiario[];
  syncState: SyncState;
}
export const GUS = CATALOGO_FALLBACK.filter((c) => c.nombre.startsWith("GUS"));

export function fechaHoraVenezuela() {
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "America/Caracas", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date());
  const get = (type: string) => parts.find((p) => p.type === type)!.value;
  return { fecha: `${get("year")}-${get("month")}-${get("day")}`, hora: `${get("hour")}:${get("minute")}` };
}

export function validarDiario(datos: DatosDiario): string | null {
  if (!datos.fecha || !datos.hora || !datos.responsable.trim()) return "Completa fecha, hora y responsable.";
  if (!datos.lcn_a || !datos.lcn_b) return "Selecciona el estado de LCN A y LCN B.";
  if ([datos.ucn1, datos.ucn2, datos.ucn3].some((state) => state !== "OK" && state !== "FAIL")) {
    return "Selecciona el estado de UCN1, UCN2 y UCN3.";
  }
  if (GUS.some((g) => !datos.gus[g.codigo])) return "Selecciona el estado de todas las GUS.";
  if ([datos.temperatura_ish1, datos.temperatura_ish2].some((t) => t === null || !Number.isFinite(t))) {
    return "Completa ambas temperaturas con valores numéricos.";
  }
  return null;
}

async function request(path = "", method = "GET", body?: unknown): Promise<Response> {
  const token = await getMeta("token");
  let res: Response;
  try {
    res = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? ""}/api/diarios${path}`, {
    method, headers: { Authorization: `Bearer ${token ?? ""}`, ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
    });
  } catch {
    throw new ApiError(0, "No se pudo conectar con el servidor. El borrador permanece guardado en el teléfono.");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const message = typeof data.detail === "string" ? data.detail : "Datos inválidos. Revisa los campos del reporte.";
    throw new ApiError(res.status, message);
  }
  return res;
}

export async function saveRemoteDiario(item: Diario): Promise<{ status: string; diario: Diario }> {
  return (await request(`/${item.id}`, "PUT", payload(item))).json();
}
function payload(item: Diario) {
  return { id: item.id, datos: item.datos, version: item.version, client_updated_at: item.client_updated_at };
}
export async function closeDiario(item: Diario): Promise<Diario> {
  return (await request(`/${item.id}/finalizar`, "POST", {
    version: item.version, client_updated_at: item.client_updated_at,
  })).json();
}
export async function reopenDiario(item: Diario): Promise<Diario> {
  return (await request(`/${item.id}/reabrir`, "POST", { version: item.version })).json();
}
export async function fetchDiarioImage(id: string, version: number): Promise<Blob> {
  return (await request(`/${id}/versiones/${version}/imagen`)).blob();
}

let running: Promise<{ synced: number; pulled: number }> | null = null;
export function syncDiarios(): Promise<{ synced: number; pulled: number }> {
  if (running) return running;
  running = runSync().finally(() => { running = null; });
  return running;
}
async function runSync() {
  if (!navigator.onLine) return { synced: 0, pulled: 0 };
  let synced = 0;
  let pulled = 0;
  const pending = await db.diarios.where("syncState").equals("pending").toArray();
  for (let offset = 0; offset < pending.length; offset += 100) {
    const batch = pending.slice(offset, offset + 100);
    const response: { results: { diario: Diario; status: string }[] } = await (
      await request("/sync", "POST", { diarios: batch.map(payload) })
    ).json();
    for (const result of response.results) {
      const sent = batch.find((d) => d.id === result.diario.id)!;
      await db.transaction("rw", db.diarios, async () => {
        const current = await db.diarios.get(sent.id);
        // Una edición hecha mientras viajaba la petición sigue pendiente.
        if (current?.client_updated_at !== sent.client_updated_at || current.version !== sent.version) return;
        await db.diarios.put({ ...result.diario, syncState: "synced" });
        synced++;
      });
    }
  }
  const remotes: Diario[] = await (await request()).json();
  for (const remote of remotes) {
    await db.transaction("rw", db.diarios, async () => {
      const current = await db.diarios.get(remote.id);
      if (current?.syncState === "pending") return;
      if (current?.server_updated_at && remote.server_updated_at
        && current.server_updated_at >= remote.server_updated_at) return;
      await db.diarios.put({ ...remote, syncState: "synced" });
      pulled++;
    });
  }
  return { synced, pulled };
}
