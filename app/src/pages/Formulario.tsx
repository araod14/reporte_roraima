import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { v4 as uuid } from "uuid";
import { db } from "../db";
import { finalizar as apiFinalizar, reabrir as apiReabrir, ApiError } from "../api";
import { syncNow } from "../sync";
import { compartirPDFs, verSlides } from "../slides";
import type { CatalogoElemento, Estado, Inspeccion, Registro } from "../types";

const HOY = () => new Date().toISOString().slice(0, 10);
const AHORA = () => new Date().toISOString();

const INSTALACIONES = ["SDC", "ISH-1", "ISH-2"];
const SISTEMAS = ["LCN", "PCN", "MANT", "SSLL", "FSC", "AIT", "CCC", "UCN", "PLC"];
const COMMENT_WORD_LIMIT = 20;

function countWords(value: string): number {
  return value.trim() ? value.trim().split(/\s+/).length : 0;
}

function limitWords(value: string): string {
  const words = value.trim().split(/\s+/);
  return words.length > COMMENT_WORD_LIMIT
    ? words.slice(0, COMMENT_WORD_LIMIT).join(" ")
    : value;
}

function nuevaInspeccion(id: string): Inspeccion {
  return {
    id,
    fecha: HOY(),
    inspeccionado_por_nombre: "",
    verificado_por_nombre: "",
    aprobado_por_nombre: "",
    observaciones_generales: "",
    estado: "BORRADOR",
    syncState: "pending",
    client_updated_at: AHORA(),
    registros: {},
  };
}

export function Formulario() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [insp, setInsp] = useState<Inspeccion | null>(null);
  const [catalogo, setCatalogo] = useState<CatalogoElemento[]>([]);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    void (async () => {
      const cat = await db.catalogo.orderBy("orden").toArray();
      setCatalogo(cat);
      const existing = await db.inspecciones.get(id);
      setInsp(existing ?? nuevaInspeccion(id));
    })();
  }, [id]);

  const readOnly = insp?.estado === "FINALIZADA";

  // Aplica un cambio: actualiza estado y persiste en IndexedDB (autosave offline).
  const apply = useCallback(
    (patch: Partial<Inspeccion>) => {
      setInsp((prev) => {
        if (!prev) return prev;
        const next: Inspeccion = {
          ...prev,
          ...patch,
          syncState: "pending",
          client_updated_at: AHORA(),
        };
        void db.inspecciones.put(next);
        return next;
      });
    },
    [],
  );

  const updateReg = useCallback(
    (codigo: string, patch: Partial<Registro>) => {
      setInsp((prev) => {
        if (!prev) return prev;
        const actual = prev.registros[codigo] ?? { id: uuid(), catalogo_codigo: codigo };
        const registros = { ...prev.registros, [codigo]: { ...actual, ...patch } };
        const next: Inspeccion = {
          ...prev,
          registros,
          syncState: "pending",
          client_updated_at: AHORA(),
        };
        void db.inspecciones.put(next);
        return next;
      });
    },
    [],
  );

  const grupos = useMemo(() => {
    const map = new Map<string, CatalogoElemento[]>();
    for (const c of catalogo) {
      const key = `${c.instalacion}|${c.sistema}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(c);
    }
    return map;
  }, [catalogo]);

  if (!insp) return null;

  async function finalizar() {
    if (!insp) return;
    const comentarioInvalido = catalogo.find((el) => {
      const reg = insp.registros[el.codigo];
      const toleraFaltantes = el.tipo === "UPS"
        && (el.nombre.toUpperCase().includes("HPM") || el.sistema.toUpperCase() === "PLC");
      const palabras = countWords(reg?.comentario ?? "");
      return toleraFaltantes && reg?.estado === "MALO"
        && (palabras === 0 || palabras > COMMENT_WORD_LIMIT);
    });
    if (comentarioInvalido) {
      showToast(`Agrega un comentario de hasta 20 palabras para ${comentarioInvalido.nombre}.`);
      return;
    }
    if (!navigator.onLine) {
      showToast("Necesitas conexión para finalizar.");
      return;
    }
    setBusy(true);
    try {
      await db.inspecciones.put(insp);
      await syncNow();
      const rep = await apiFinalizar(insp.id);
      const next: Inspeccion = {
        ...insp,
        estado: "FINALIZADA",
        syncState: "synced",
        reporte: {
          version: rep.version,
          pdf_url: rep.pdf_url,
          html_url: rep.html_url,
          verificar_url: rep.verificar_url,
          pdf_hash_short: rep.pdf_hash_short,
          content_hash: rep.content_hash,
        },
      };
      await db.inspecciones.put(next);
      setInsp(next);
      showToast(`Finalizada · v${rep.version}`);
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Error al finalizar");
    } finally {
      setBusy(false);
    }
  }

  async function reabrir() {
    if (!insp) return;
    setBusy(true);
    try {
      await apiReabrir(insp.id);
      const next: Inspeccion = { ...insp, estado: "BORRADOR" };
      await db.inspecciones.put(next);
      setInsp(next);
      showToast("Reabierta para corrección (generará nueva versión)");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Error al reabrir");
    } finally {
      setBusy(false);
    }
  }

  async function compartir() {
    if (!insp?.reporte) return;
    if (!navigator.onLine) return showToast("Necesitas conexión para compartir los PDF.");
    setBusy(true);
    try {
      showToast(await compartirPDFs(insp.reporte, insp.id, insp.fecha));
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Error al preparar los PDF");
    } finally {
      setBusy(false);
    }
  }

  async function verPanel() {
    if (!insp) return;
    if (!navigator.onLine) return showToast("Necesitas conexión para ver el panel.");
    setBusy(true);
    try {
      await verSlides(insp.id);
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Error al abrir el panel");
    } finally {
      setBusy(false);
    }
  }

  function showToast(m: string) {
    setToast(m);
    setTimeout(() => setToast(""), 2600);
  }

  return (
    <div className="app">
      <div className="topbar">
        <div>
          <h1>{readOnly ? "Reporte" : "Inspección"}</h1>
          <div className="sub">{insp.fecha}</div>
        </div>
        <button onClick={() => navigate("/")}>Volver</button>
      </div>

      <div className="content">
        {readOnly && (
          <div className="finalized-note">
            ✓ Inspección finalizada{insp.reporte ? ` (v${insp.reporte.version})` : ""}. Solo lectura.
          </div>
        )}

        {/* ---- Cabecera ---- */}
        <div className="section" style={{ padding: 14 }}>
          <label className="field">
            <span>Fecha</span>
            <input type="date" value={insp.fecha} disabled={readOnly}
              onChange={(e) => apply({ fecha: e.target.value })} />
          </label>
          <label className="field">
            <span>Inspeccionado por</span>
            <input value={insp.inspeccionado_por_nombre} disabled={readOnly}
              onChange={(e) => apply({ inspeccionado_por_nombre: e.target.value })} />
          </label>
          <label className="field">
            <span>Verificado por</span>
            <input value={insp.verificado_por_nombre} disabled={readOnly}
              onChange={(e) => apply({ verificado_por_nombre: e.target.value })} />
          </label>
          <label className="field">
            <span>Aprobado por</span>
            <input value={insp.aprobado_por_nombre} disabled={readOnly}
              onChange={(e) => apply({ aprobado_por_nombre: e.target.value })} />
          </label>
          <label className="field" style={{ marginBottom: 0 }}>
            <span>Observaciones generales</span>
            <textarea value={insp.observaciones_generales} disabled={readOnly}
              onChange={(e) => apply({ observaciones_generales: e.target.value })} />
          </label>
        </div>

        {/* ---- Secciones por instalación / sistema ---- */}
        {INSTALACIONES.map((inst) => {
          const sistemasDeInst = SISTEMAS.filter((s) => grupos.has(`${inst}|${s}`));
          if (sistemasDeInst.length === 0) return null;
          return (
            <div key={inst}>
              <div className="inst-title">{inst}</div>
              {sistemasDeInst.map((sis) => {
                const key = `${inst}|${sis}`;
                const elementos = grupos.get(key)!;
                const isOpen = open[key] ?? false;
                const done = elementos.filter((e) => {
                  const r = insp.registros[e.codigo];
                  if (!r) return false;
                  return e.tipo === "UPS" ? true : !!r.estado;
                }).length;
                return (
                  <div className="section" key={key}>
                    <button className="accordion-head"
                      onClick={() => setOpen((o) => ({ ...o, [key]: !isOpen }))}>
                      <span>{sis}</span>
                      <span className="count">{done}/{elementos.length} {isOpen ? "▲" : "▼"}</span>
                    </button>
                    {isOpen && (
                      <div className="accordion-body">
                        {elementos.map((el) => (
                          <ElementoRow key={el.codigo} el={el}
                            reg={insp.registros[el.codigo]} readOnly={readOnly}
                            onChange={(patch) => updateReg(el.codigo, patch)} />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}

        <div className="spacer" />

        {/* ---- Acciones ---- */}
        {readOnly ? (
          <div className="btn-row">
            <button className="btn-green btn-block" onClick={compartir} disabled={busy}>
              Compartir PDF por WhatsApp
            </button>
            <button className="btn-block" onClick={verPanel} disabled={busy}>
              Ver esquema visual
            </button>
            <button className="btn-block" onClick={reabrir} disabled={busy}>
              Reabrir para corregir (nueva versión)
            </button>
          </div>
        ) : (
          <button className="btn-primary btn-block" onClick={finalizar} disabled={busy}>
            {busy ? "Procesando…" : "Finalizar y generar reporte"}
          </button>
        )}
      </div>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

function ElementoRow({
  el, reg, readOnly, onChange,
}: {
  el: CatalogoElemento;
  reg?: Registro;
  readOnly: boolean;
  onChange: (patch: Partial<Registro>) => void;
}) {
  if (el.tipo === "UPS") {
    const pares = el.ups_dobles ? [1, 2, 3, 4] : [1, 2];
    const toleraFaltantes = el.nombre.toUpperCase().includes("HPM")
      || el.sistema.toUpperCase() === "PLC";
    const forzarMalo = reg?.estado === "MALO";
    return (
      <div className="elem">
        <div className="nombre">{el.nombre}</div>
        <div className="chips">
          {pares.map((i) =>
            (["fuente", "bateria", "fan"] as const).map((kind) => {
              const field = `${kind}_${i}` as keyof Registro;
              const on = !!reg?.[field];
              const label = { fuente: "Fuente", bateria: "Batería", fan: "Fan" }[kind];
              return (
                <button key={field} type="button" disabled={readOnly}
                  className={`chip ${on ? "on" : ""}`}
                  onClick={() => onChange({ [field]: !on } as Partial<Registro>)}>
                  {label} {i}
                </button>
              );
            }),
          )}
        </div>
        {toleraFaltantes && (
          <label className={`bad-toggle ${forzarMalo ? "on" : ""}`}>
            <input type="checkbox" checked={forzarMalo} disabled={readOnly}
              onChange={(e) => onChange({ estado: e.target.checked ? "MALO" : null })} />
            <span>Marcar equipo como MALO</span>
          </label>
        )}
        <CommentField value={reg?.comentario ?? ""} readOnly={readOnly}
          onChange={(comentario) => onChange({ comentario })} />
      </div>
    );
  }

  const estados: { v: Estado; label: string; cls: string }[] = [
    { v: "OK", label: "OK", cls: "sel-ok" },
    { v: "MALO", label: "MALO", cls: "sel-malo" },
    { v: "OBSERVACION", label: "OBSERV.", cls: "sel-obs" },
  ];
  return (
    <div className="elem">
      <div className="nombre">{el.nombre}</div>
      <div className="segmented">
        {estados.map((e) => (
          <button key={e.v} type="button" disabled={readOnly}
            className={reg?.estado === e.v ? e.cls : ""}
            onClick={() => onChange({ estado: e.v })}>
            {e.label}
          </button>
        ))}
      </div>
      {el.tipo === "CCC" && (
        <div className="valores">
          <label className="field">
            <span>Valor A</span>
            <input value={reg?.valor_a ?? ""} disabled={readOnly}
              onChange={(e) => onChange({ valor_a: e.target.value })} />
          </label>
          <label className="field">
            <span>Valor B</span>
            <input value={reg?.valor_b ?? ""} disabled={readOnly}
              onChange={(e) => onChange({ valor_b: e.target.value })} />
          </label>
        </div>
      )}
      <CommentField value={reg?.comentario ?? ""} readOnly={readOnly}
        onChange={(comentario) => onChange({ comentario })} />
    </div>
  );
}

function CommentField({
  value, readOnly, onChange,
}: {
  value: string;
  readOnly: boolean;
  onChange: (value: string) => void;
}) {
  const words = countWords(value);
  return (
    <div className="comment-wrap">
      <textarea className="comment" placeholder="Comentario (opcional)"
        value={value} disabled={readOnly}
        onChange={(e) => onChange(limitWords(e.target.value))} />
      {!readOnly && (
        <div className={`word-count ${words >= COMMENT_WORD_LIMIT ? "limit" : ""}`}>
          {words}/{COMMENT_WORD_LIMIT} palabras
        </div>
      )}
    </div>
  );
}
