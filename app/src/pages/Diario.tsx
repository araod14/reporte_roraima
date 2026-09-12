import { useEffect, useRef, useState } from "react";
import { liveQuery } from "dexie";
import { useNavigate, useParams } from "react-router-dom";
import { db, getMeta, setMeta } from "../db";
import {
  closeDiario, fetchDiarioImage, fechaHoraVenezuela, GUS, reopenDiario,
  saveRemoteDiario, syncDiarios, validarDiario,
  type Diario as DiarioData, type DatosDiario,
} from "../diarios";
import { downloadBlob } from "../report";

export function Diario() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [item, setItem] = useState<DiarioData | null>(null);
  const current = useRef<DiarioData | null>(null);
  const writes = useRef(Promise.resolve());
  const [busy, setBusy] = useState(false);
  const acting = useRef(false);
  const [message, setMessage] = useState("");
  const [image, setImage] = useState<{ url: string; blob: Blob; version: number; filename: string } | null>(null);
  const [temperatureText, setTemperatureText] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!id) return;
    let alive = true;
    const subscription = liveQuery(() => db.diarios.get(id)).subscribe((value) => {
      if (!alive || !value) return;
      const local = current.current;
      if (local?.syncState === "pending" && value.syncState === "pending"
        && Date.parse(local.client_updated_at) > Date.parse(value.client_updated_at)) return;
      if (local) {
        setTemperatureText((previous) => {
          const next = { ...previous };
          for (const key of ["temperatura_ish1", "temperatura_ish2"] as const) {
            if (local.datos[key] !== value.datos[key]) delete next[key];
          }
          return next;
        });
      }
      current.current = value;
      setItem(value);
    });
    void (async () => {
      let value = await db.diarios.get(id);
      if (!value) {
        value = {
          id, datos: { ...fechaHoraVenezuela(), responsable: await getMeta("diarioResponsable") ?? "",
            lcn_a: null, lcn_b: null, gus: {}, temperatura_ish1: null, temperatura_ish2: null, observaciones: "" },
          estado: "BORRADOR", version: 0, versiones: [], syncState: "pending", client_updated_at: new Date().toISOString(),
        };
        await db.diarios.put(value);
      }
      if (alive) { current.current = value; setItem(value); }
    })().catch(() => setMessage("No se pudo abrir el borrador local."));
    const sync = () => {
      if (acting.current) return;
      void writes.current.then(() => syncDiarios()).catch((e) => { if (alive) setMessage(e.message); });
    };
    const interval = window.setInterval(sync, 60_000);
    window.addEventListener("online", sync);
    return () => { alive = false; subscription.unsubscribe(); clearInterval(interval); window.removeEventListener("online", sync); };
  }, [id]);

  useEffect(() => () => { if (image) URL.revokeObjectURL(image.url); }, [image]);

  function apply(patch: Partial<DatosDiario>) {
    const previous = current.current;
    if (!previous || previous.estado === "FINALIZADA" || busy) return;
    const next: DiarioData = { ...previous, datos: { ...previous.datos, ...patch }, syncState: "pending",
      client_updated_at: new Date(Math.max(Date.now(), Date.parse(previous.client_updated_at) + 1)).toISOString() };
    current.current = next;
    setItem(next);
    writes.current = writes.current.then(async () => {
      await db.diarios.put(next);
      if (patch.responsable !== undefined) await setMeta("diarioResponsable", patch.responsable);
    });
    void writes.current.catch(() => setMessage("No se pudo guardar en el teléfono. No cierres esta pantalla."));
  }

  async function showImage(value: DiarioData, version: number) {
    const blob = await fetchDiarioImage(value.id, version);
    const meta = value.versiones.find((v) => v.version === version)!;
    const filename = `reporte-diario-${meta.fecha}-${meta.hora.replace(":", "")}-v${version}.png`;
    setImage({ blob, version, filename, url: URL.createObjectURL(blob) });
  }

  async function action(task: () => Promise<void>) {
    if (!navigator.onLine) { setMessage("Necesitas conexión para esta acción. El borrador se guarda en el teléfono."); return; }
    if (acting.current) return;
    acting.current = true;
    setBusy(true); setMessage("");
    try { await writes.current; await task(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "No se pudo completar la acción."); }
    finally { acting.current = false; setBusy(false); }
  }

  async function finalizar() {
    const value = current.current;
    if (!value) return;
    const invalidTemperature = Object.values(temperatureText).some((text) => text.trim() !== ""
      && (!/^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)$/.test(text.trim()) || !Number.isFinite(Number(text.replace(",", ".")))));
    const error = invalidTemperature ? "Revisa el formato de las temperaturas." : validarDiario(value.datos);
    if (error) { setMessage(error); return; }
    await action(async () => {
      // Esperar cualquier sincronización anterior antes del guardado y cierre.
      await syncDiarios();
      const local = await db.diarios.get(value.id);
      if (local && (local.version !== value.version || local.estado !== value.estado
        || Date.parse(local.client_updated_at) !== Date.parse(value.client_updated_at))) {
        setTemperatureText({});
        throw new Error("El reporte cambió al sincronizar. Revisa los datos antes de finalizar.");
      }
      const saved = await saveRemoteDiario(value);
      await db.diarios.put({ ...saved.diario, syncState: "synced" });
      if (saved.status.startsWith("skipped") && (saved.diario.estado !== "BORRADOR"
        || saved.diario.version !== value.version
        || Date.parse(saved.diario.client_updated_at) !== Date.parse(value.client_updated_at))) {
        setTemperatureText({});
        throw new Error("Se recuperó una versión del servidor. Revisa los datos antes de finalizar.");
      }
      const closed = await closeDiario(saved.diario);
      await db.diarios.put({ ...closed, syncState: "synced" });
      setTemperatureText({});
      setMessage("Reporte finalizado.");
      await showImage(closed, closed.version);
    });
  }

  async function compartir() {
    if (!item || !image) return;
    const filename = image.filename;
    const file = new File([image.blob], filename, { type: "image/png" });
    try {
      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: "Reporte diario" });
        setMessage("Imagen compartida.");
      } else { downloadBlob(image.blob, filename); setMessage("Imagen descargada para adjuntar desde el teléfono."); }
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") { setMessage("Compartir cancelado."); return; }
      downloadBlob(image.blob, filename);
      setMessage("No se pudo compartir; se descargó la imagen.");
    }
  }

  if (!item) return <div className="content">{message || "Abriendo reporte…"}</div>;
  const readOnly = item.estado === "FINALIZADA";
  const disabled = busy || readOnly;
  const data = item.datos;

  function status(label: string, value: string | null | undefined, options: string[], onChange: (v: string) => void) {
    return <div className="elem"><div className="nombre">{label}</div>
      <div className="segmented" role="group" aria-label={label}>
        {options.map((v) => <button key={v} disabled={disabled} aria-pressed={value === v}
          className={value === v ? v === "OK" ? "sel-ok" : v === "MALO" ? "sel-malo" : "daily-amber" : ""}
          onClick={() => onChange(v)}>{v === "OBSERVACION" ? "OBSERVACIÓN" : v}</button>)}
      </div></div>;
  }

  return <div className="app daily">
    <div className="topbar"><div><h1>Reporte diario</h1><div className="sub">{readOnly ? `Finalizado · v${item.version}` : "Borrador · guardado automático"}</div></div>
      <button disabled={busy} onClick={() => navigate("/")}>Volver</button></div>
    <div className="content">
      {message && <div className="daily-message" role="status">{message}</div>}
      {readOnly && <div className="finalized-note">Reporte finalizado. Las correcciones crean una nueva versión.</div>}
      <section className="section daily-section">
        <div className="valores">
          <label className="field"><span>Fecha</span><input type="date" disabled={disabled} value={data.fecha} onChange={(e) => apply({ fecha: e.target.value })} /></label>
          <label className="field"><span>Hora (Venezuela)</span><input type="time" disabled={disabled} value={data.hora} onChange={(e) => apply({ hora: e.target.value })} /></label>
        </div>
        <label className="field"><span>Responsable</span><input disabled={disabled} maxLength={120} value={data.responsable} onChange={(e) => apply({ responsable: e.target.value })} /></label>
      </section>
      <section className="section daily-section"><h2>Estado LCN</h2>
        {status("LCN A", data.lcn_a, ["OK", "SUSPECT"], (v) => apply({ lcn_a: v as DatosDiario["lcn_a"] }))}
        {status("LCN B", data.lcn_b, ["OK", "SUSPECT"], (v) => apply({ lcn_b: v as DatosDiario["lcn_b"] }))}
      </section>
      <section className="section daily-section"><h2>Temperaturas</h2>
        {(["temperatura_ish1", "temperatura_ish2"] as const).map((key, index) => <label key={key} className="field">
          <span>ISH-{index + 1} (°C)</span><input inputMode="decimal" disabled={disabled}
            value={readOnly ? data[key] ?? "" : temperatureText[key] ?? data[key] ?? ""}
            placeholder="Ej.: 24,5" onChange={(e) => {
              const text = e.target.value;
              setTemperatureText((prev) => ({ ...prev, [key]: text }));
              const number = Number(text.replace(",", "."));
              apply({ [key]: text.trim() && /^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)$/.test(text.trim()) && Number.isFinite(number) ? number : null });
            }} /></label>)}
      </section>
      <section className="section daily-section"><h2>Estado GUS <small>{Object.keys(data.gus).length}/{GUS.length}</small></h2>
        {GUS.map((g) => <div key={g.codigo}>{status(g.nombre, data.gus[g.codigo], ["OK", "MALO", "OBSERVACION"],
          (v) => apply({ gus: { ...data.gus, [g.codigo]: v as DatosDiario["gus"][string] } }))}</div>)}
      </section>
      <section className="section daily-section"><label className="field"><span>Observaciones (opcional)</span>
        <textarea disabled={disabled} maxLength={1000} value={data.observaciones} onChange={(e) => apply({ observaciones: e.target.value })} />
      </label><div className="word-count">{data.observaciones.length}/1000 caracteres</div></section>
      {!readOnly && <button className="btn-primary btn-block" disabled={busy} onClick={() => void finalizar()}>{busy ? "Procesando…" : "Finalizar y generar PNG"}</button>}
      {readOnly && <button className="btn-block" disabled={busy} onClick={() => void action(async () => {
        const reopened = await reopenDiario(item);
        await db.diarios.put({ ...reopened, syncState: "synced" });
        setImage(null); setTemperatureText({});
      })}>Reabrir para corregir (nueva versión)</button>}
      {item.versiones.length > 0 && <section className="section daily-section"><h2>Imágenes guardadas</h2><div className="btn-row">
        {item.versiones.map((v) => <button key={v.version} disabled={busy} onClick={() => void action(() => showImage(item, v.version))}>Ver PNG · v{v.version}</button>)}
      </div></section>}
      {image && <section className="section daily-section"><h2>Vista previa · v{image.version}</h2>
        <img className="daily-preview" src={image.url} alt={`Reporte diario, versión ${image.version}`} />
        <div className="btn-row"><button className="btn-green" onClick={() => void compartir()}>Compartir PNG</button>
          <button onClick={() => downloadBlob(image.blob, image.filename)}>Descargar PNG</button></div>
      </section>}
    </div>
  </div>;
}
