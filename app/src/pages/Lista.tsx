import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { v4 as uuid } from "uuid";
import { db, delMeta, getMeta } from "../db";
import { startAutoSync, syncNow } from "../sync";
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

function estadoBadge(insp: Inspeccion) {
  if (insp.estado === "FINALIZADA") return <span className="badge finalizada">Finalizada</span>;
  if (insp.syncState === "pending") return <span className="badge pending">Pendiente</span>;
  return <span className="badge synced">Sincronizada</span>;
}

export function Lista() {
  const [items, setItems] = useState<Inspeccion[]>([]);
  const [username, setUsername] = useState("");
  const [toast, setToast] = useState("");
  const [syncing, setSyncing] = useState(false);
  const online = useOnline();
  const navigate = useNavigate();

  const load = useCallback(async () => {
    const all = await db.inspecciones.toArray();
    all.sort((a, b) => b.client_updated_at.localeCompare(a.client_updated_at));
    setItems(all);
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
    const r = await syncNow();
    setSyncing(false);
    await load();
    setToast(r.ok ? `Sincronizado (${r.synced})` : `Error: ${r.message}`);
    setTimeout(() => setToast(""), 2500);
  }

  async function logout() {
    await delMeta("token");
    navigate("/login", { replace: true });
  }

  function nueva() {
    navigate(`/insp/${uuid()}`);
  }

  const pendientes = items.filter((i) => i.syncState === "pending").length;

  return (
    <div className="app">
      <div className="topbar">
        <div>
          <h1>Inspecciones</h1>
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

        {items.length === 0 && (
          <p style={{ color: "var(--muted)", textAlign: "center", marginTop: 40 }}>
            No hay inspecciones. Crea una nueva con el botón +.
          </p>
        )}

        {items.map((insp) => (
          <Link key={insp.id} to={`/insp/${insp.id}`} className="list-item">
            <div>
              <div className="fecha">{insp.fecha}</div>
              <div className="who">
                {insp.inspeccionado_por_nombre || "Sin inspector"}
              </div>
            </div>
            {estadoBadge(insp)}
          </Link>
        ))}
      </div>

      <button className="btn-primary fab" onClick={nueva} aria-label="Nueva inspección">
        + Nueva
      </button>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
