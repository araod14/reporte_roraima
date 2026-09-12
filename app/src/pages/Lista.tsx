import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { v4 as uuid } from "uuid";
import { db, delMeta, getMeta } from "../db";
import { startAutoSync, syncAll } from "../sync";
import type { Diario } from "../diarios";
import type { Inspeccion } from "../types";

function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}

function estadoBadge(insp: Pick<Inspeccion, "estado" | "syncState">) {
  if (insp.estado === "FINALIZADA") return <span className="badge finalizada">Finalizada</span>;
  if (insp.syncState === "pending") return <span className="badge pending">Pendiente</span>;
  return <span className="badge synced">Sincronizada</span>;
}

export function Lista() {
  const [items, setItems] = useState<Inspeccion[]>([]);
  const [diarios, setDiarios] = useState<Diario[]>([]);
  const [filter, setFilter] = useState("todos");
  const [username, setUsername] = useState("");
  const [toast, setToast] = useState("");
  const [syncing, setSyncing] = useState(false);
  const online = useOnline();
  const navigate = useNavigate();

  const load = useCallback(async () => {
    const all = await db.inspecciones.toArray();
    all.sort((a, b) => b.client_updated_at.localeCompare(a.client_updated_at));
    setItems(all);
    setDiarios(await db.diarios.toArray());
  }, []);

  useEffect(() => {
    void getMeta("username").then((u) => setUsername(u ?? ""));
    void load();
    const stop = startAutoSync(load);
    const onFocus = () => void load();
    window.addEventListener("focus", onFocus);
    return () => {
      stop();
      window.removeEventListener("focus", onFocus);
    };
  }, [load]);

  async function handleSync() {
    setSyncing(true);
    const r = await syncAll();
    setSyncing(false);
    await load();
    if (r.ok) {
      const partes = [`↑ ${r.synced}`, `↓ ${r.pulled}`];
      setToast(`Sincronizado (${partes.join("  ")})`);
    } else {
      setToast(`Error: ${r.message}`);
    }
    setTimeout(() => setToast(""), 2500);
  }

  async function logout() {
    await delMeta("token");
    navigate("/login", { replace: true });
  }

  function nueva() {
    navigate(`/insp/${uuid()}`);
  }

  const pendientes = [...items, ...diarios].filter((i) => i.syncState === "pending").length;
  const entries = [
    ...items.map((i) => ({ id: i.id, tipo: "semanal", fecha: i.fecha, hora: "", who: i.inspeccionado_por_nombre,
      url: `/insp/${i.id}`, estado: i.estado, syncState: i.syncState, updated: i.client_updated_at })),
    ...diarios.map((i) => ({ id: i.id, tipo: "diario", fecha: i.datos.fecha, hora: i.datos.hora, who: i.datos.responsable,
      url: `/diario/${i.id}`, estado: i.estado, syncState: i.syncState, updated: i.client_updated_at })),
  ].filter((i) => filter === "todos" || i.tipo === filter).sort((a, b) => b.updated.localeCompare(a.updated));

  return (
    <div className="app">
      <div className="topbar">
        <div>
          <h1>Reportes</h1>
          <div className="sub">{username}</div>
        </div>
        <button onClick={logout}>Salir</button>
      </div>

      <div className="content">
        <div className={`sync-bar ${online ? "" : "offline"}`}>
          <span>
            <span className={`dot ${online ? "on" : "off"}`} />{" "}
            {online ? "En línea" : "Sin conexión"}
            {pendientes > 0 && ` · ${pendientes} pendiente(s)`}
          </span>
          <button className="btn-primary" onClick={handleSync} disabled={syncing || !online}>
            {syncing ? "Sincronizando…" : "Sincronizar ahora"}
          </button>
        </div>

        <div className="report-actions">
          <button className="btn-primary" onClick={nueva}>Reporte semanal</button>
          <button className="btn-primary" onClick={() => navigate(`/diario/${uuid()}`)}>Reporte diario</button>
        </div>
        <div className="btn-row report-filters" role="group" aria-label="Tipo de reporte">
          {[["todos", "Todos"], ["semanal", "Semanales"], ["diario", "Diarios"]].map(([value, label]) =>
            <button key={value} aria-pressed={filter === value} className={filter === value ? "btn-primary" : ""}
              onClick={() => setFilter(value)}>{label}</button>)}
        </div>
        {entries.length === 0 && <p>No hay reportes en esta vista. Crea uno con los botones superiores.</p>}
        {entries.map((entry) => (
          <Link key={`${entry.tipo}-${entry.id}`} to={entry.url} className="list-item">
            <div>
              <div className="fecha">{entry.fecha} {entry.hora}</div>
              <div className="who">{entry.tipo === "diario" ? "Diario" : "Semanal"} · {entry.who || "Sin responsable"}</div>
            </div>
            {estadoBadge(entry)}
          </Link>
        ))}
      </div>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
