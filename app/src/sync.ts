import { syncBatch, fetchCatalogo, ApiError } from "./api";
import { db, setMeta } from "./db";
import { CATALOGO_FALLBACK } from "./catalogo";
import type { Inspeccion } from "./types";

// Convierte una inspección local al formato que espera el backend.
export function toPayload(insp: Inspeccion) {
  return {
    id: insp.id,
    fecha: insp.fecha,
    inspeccionado_por_nombre: insp.inspeccionado_por_nombre,
    verificado_por_nombre: insp.verificado_por_nombre,
    aprobado_por_nombre: insp.aprobado_por_nombre,
    observaciones_generales: insp.observaciones_generales,
    client_updated_at: insp.client_updated_at,
    registros: Object.values(insp.registros),
  };
}

let syncing = false;

export interface SyncResult {
  ok: boolean;
  synced: number;
  message?: string;
}

// Sube todas las inspecciones pendientes. Idempotente (por UUID).
export async function syncNow(): Promise<SyncResult> {
  if (syncing) return { ok: true, synced: 0, message: "Ya sincronizando…" };
  if (!navigator.onLine) return { ok: false, synced: 0, message: "Sin conexión" };
  syncing = true;
  try {
    const pendientes = await db.inspecciones
      .where("syncState")
      .equals("pending")
      .toArray();
    if (pendientes.length === 0) return { ok: true, synced: 0 };

    const res = await syncBatch(pendientes.map(toPayload));
    const okIds = new Set(
      (res.results ?? [])
        .filter((r: any) =>
          ["created", "updated", "skipped_finalizada", "skipped_older"].includes(r.status),
        )
        .map((r: any) => r.id),
    );
    let synced = 0;
    for (const insp of pendientes) {
      if (okIds.has(insp.id)) {
        insp.syncState = "synced";
        await db.inspecciones.put(insp);
        synced++;
      }
    }
    return { ok: true, synced };
  } catch (e) {
    const msg = e instanceof ApiError ? e.message : "Error de red";
    return { ok: false, synced: 0, message: msg };
  } finally {
    syncing = false;
  }
}

// Refresca el catálogo desde el backend; si falla, usa el empaquetado.
export async function refreshCatalogo(): Promise<void> {
  try {
    const remote = await fetchCatalogo();
    if (Array.isArray(remote) && remote.length > 0) {
      await db.catalogo.clear();
      await db.catalogo.bulkPut(remote);
      await setMeta("catalogoAt", new Date().toISOString());
      return;
    }
  } catch {
    /* offline: usamos fallback */
  }
  const count = await db.catalogo.count();
  if (count === 0) {
    await db.catalogo.bulkPut(CATALOGO_FALLBACK);
  }
}

// Arranca la sincronización automática (al recuperar conexión + intervalo).
export function startAutoSync(onChange?: () => void): () => void {
  const run = async () => {
    const r = await syncNow();
    if (r.synced > 0) onChange?.();
  };
  const onlineHandler = () => void run();
  window.addEventListener("online", onlineHandler);
  const interval = window.setInterval(() => void run(), 60_000);
  void run();
  return () => {
    window.removeEventListener("online", onlineHandler);
    window.clearInterval(interval);
  };
}
