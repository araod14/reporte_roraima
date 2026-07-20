import {
  syncBatch,
  fetchCatalogo,
  fetchInspecciones,
  fetchInspeccion,
  fetchReportes,
  ApiError,
} from "./api";
import { db, setMeta } from "./db";
import { CATALOGO_FALLBACK } from "./catalogo";
import type { Inspeccion, Registro } from "./types";

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

// Baja las inspecciones del servidor (de todos los usuarios) y las fusiona en
// IndexedDB. Nunca pisa ediciones locales aún sin subir (syncState === "pending").
// Devuelve cuántas inspecciones locales cambiaron.
export async function pullRemote(): Promise<number> {
  if (!navigator.onLine) return 0;
  let changed = 0;
  const remotos = await fetchInspecciones();
  for (const item of remotos) {
    const local = await db.inspecciones.get(item.id);
    // No sobreescribir cambios locales que todavía no se subieron.
    if (local?.syncState === "pending") continue;
    // Ya tenemos exactamente esta versión del servidor: nada que hacer.
    if (local && local.server_updated_at === item.updated_at) continue;

    const full = await fetchInspeccion(item.id);
    const registros: Record<string, Registro> = {};
    for (const r of full.registros ?? []) registros[r.catalogo_codigo] = r;

    const insp: Inspeccion = {
      id: full.id,
      fecha: full.fecha,
      inspeccionado_por_nombre: full.inspeccionado_por_nombre ?? "",
      verificado_por_nombre: full.verificado_por_nombre ?? "",
      aprobado_por_nombre: full.aprobado_por_nombre ?? "",
      observaciones_generales: full.observaciones_generales ?? "",
      estado: full.estado,
      syncState: "synced",
      client_updated_at: local?.client_updated_at ?? full.updated_at,
      server_updated_at: item.updated_at,
      created_by: full.created_by,
      registros,
      reporte: local?.reporte,
    };

    // Para finalizadas, traer la metadata del reporte (para ver/compartir el PDF).
    if (full.estado === "FINALIZADA") {
      try {
        const reps = await fetchReportes(full.id);
        if (reps.length > 0) {
          const last = reps[reps.length - 1];
          insp.reporte = {
            version: last.version,
            pdf_url: last.pdf_url,
            html_url: last.html_url,
            verificar_url: last.verificar_url,
            pdf_hash_short: last.pdf_hash_short,
            content_hash: last.content_hash,
          };
        }
      } catch {
        /* si falla, se muestra sin botón de compartir */
      }
    }

    await db.inspecciones.put(insp);
    changed++;
  }
  return changed;
}

// Sube pendientes y luego baja lo del servidor. Devuelve si hubo cambios locales.
export async function syncAll(): Promise<SyncResult & { pulled: number }> {
  const push = await syncNow();
  let pulled = 0;
  try {
    pulled = await pullRemote();
  } catch (e) {
    if (!push.ok) return { ...push, pulled: 0 };
    const msg = e instanceof ApiError ? e.message : "Error al descargar";
    return { ok: false, synced: push.synced, message: msg, pulled: 0 };
  }
  return { ...push, pulled };
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
// Sube pendientes y baja lo de los demás usuarios.
export function startAutoSync(onChange?: () => void): () => void {
  const run = async () => {
    const r = await syncAll();
    if (r.synced > 0 || r.pulled > 0) onChange?.();
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
