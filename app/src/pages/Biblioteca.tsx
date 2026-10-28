import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { libraryPage, libraryPdf, libraryRequest, libraryStream } from "../api";

type Source = { number: number; type?: "manual" | "inventory"; document_id?: string; title: string; page?: number; section?: string; sheet?: string; row?: number };
type Message = { id: string; role: string; content: string; sources: Source[] };
type Conversation = { id: string; title: string };

function Markdown({ text }: { text: string }) {
  return <div className="library-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}
    components={{ a: ({ children }) => <span>{children}</span>, img: () => null }}>
    {text}
  </ReactMarkdown></div>;
}

export function Biblioteca() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [active, setActive] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [filter, setFilter] = useState("");
  const [status, setStatus] = useState<{ ready: boolean; documents: number; detail?: string; inventory?: { items: number; error?: string } }>();
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const [draft, setDraft] = useState("");
  const [mobileMenu, setMobileMenu] = useState(false);
  const [pdfUrl, setPdfUrl] = useState("");
  const [pageUrl, setPageUrl] = useState("");
  const [pdfDocument, setPdfDocument] = useState("");
  const [pdfPage, setPdfPage] = useState(1);
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement | null>(null);

  const loadConversations = useCallback(async () => {
    setConversations(await libraryRequest(`/conversations?q=${encodeURIComponent(filter)}`));
  }, [filter]);
  useEffect(() => { void loadConversations().catch(e => setError(e.message)); }, [loadConversations]);
  useEffect(() => { void libraryRequest("/status").then(setStatus).catch(e => setError(e.message)); }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, draft]);
  useEffect(() => () => { if (pdfUrl) URL.revokeObjectURL(pdfUrl); }, [pdfUrl]);
  useEffect(() => () => { if (pageUrl) URL.revokeObjectURL(pageUrl); }, [pageUrl]);

  async function open(id: string) {
    abort.current?.abort();
    setWorking(false); setDraft(""); setError(""); setMobileMenu(false);
    const item = await libraryRequest(`/conversations/${id}`);
    setActive(id); setMessages(item.messages);
  }
  async function create() {
    setQuestion("");
    const item = await libraryRequest("/conversations", "POST");
    setActive(item.id); setMessages([]); setMobileMenu(false);
    await loadConversations();
  }
  async function rename(item: Conversation) {
    const title = window.prompt("Nuevo nombre", item.title)?.trim();
    if (!title) return;
    await libraryRequest(`/conversations/${item.id}`, "PATCH", { title });
    await loadConversations();
  }
  async function remove(item: Conversation) {
    if (!window.confirm(`¿Eliminar «${item.title}»?`)) return;
    if (item.id === active) { abort.current?.abort(); setActive(""); setMessages([]); }
    await libraryRequest(`/conversations/${item.id}`, "DELETE");
    await loadConversations();
  }
  async function ask(regenerate = false) {
    if (working || (!regenerate && !question.trim())) return;
    let id = active;
    if (!id) {
      const item = await libraryRequest("/conversations", "POST");
      id = item.id; setActive(id);
    }
    const content = question.trim();
    const requestId = crypto.randomUUID();
    if (!regenerate) { setMessages(previous => [...previous, { id: requestId, role: "user", content, sources: [] }]); setQuestion(""); }
    else setMessages(previous => previous[previous.length - 1]?.role === "assistant" ? previous.slice(0, -1) : previous);
    setError(""); setDraft(""); setWorking(true);
    const controller = new AbortController(); abort.current = controller;
    try {
      await libraryStream(id, content || "Regenerar", regenerate, requestId, (event, data) => {
        if (event === "delta") setDraft(previous => previous + data);
        if (event === "done") { setMessages(previous => [...previous, data]); setDraft(""); }
        if (event === "error") { setError(data); setDraft(""); }
      }, controller.signal);
      await loadConversations();
    } catch (e: any) {
      if (e.name !== "AbortError") setError(e.message ?? "No se pudo responder");
    } finally { setWorking(false); abort.current = null; }
  }
  async function showPdf(source: Source) {
    if (!source.document_id || !source.page) return;
    try {
      const blob = await libraryPage(source.document_id, source.page);
      setPdfDocument(source.document_id); setPdfPage(source.page);
      setPdfUrl(""); setPageUrl(URL.createObjectURL(blob));
    } catch (e: any) { setError(e.message); }
  }
  async function openFullPdf() {
    try {
      const blob = await libraryPdf(pdfDocument);
      setPdfUrl(URL.createObjectURL(blob));
    } catch (e: any) { setError(e.message); }
  }

  return <div className="library">
    <header className="library-header"><button onClick={() => setMobileMenu(!mobileMenu)} className="library-menu" aria-label="Conversaciones">☰</button>
      <div><h1>Biblioteca Automatización Roraima</h1><small>Manuales Honeywell TPS · respuestas en español</small></div>
      <Link to="/" className="library-back">Reportes</Link></header>
    <div className="library-body">
      <aside className={`library-sidebar ${mobileMenu ? "open" : ""}`}>
        <button className="btn-primary btn-block" onClick={() => void create()}>+ Nueva conversación</button>
        <input aria-label="Buscar conversaciones" placeholder="Buscar historial" value={filter} onChange={e => setFilter(e.target.value)} />
        <div className="library-conversations">{conversations.map(item => <div key={item.id} className={`library-conversation ${item.id === active ? "selected" : ""}`}>
          <button onClick={() => void open(item.id)}>{item.title}</button>
          <button aria-label={`Renombrar ${item.title}`} title="Renombrar" onClick={() => void rename(item)}>✎</button>
          <button aria-label={`Eliminar ${item.title}`} title="Eliminar" onClick={() => void remove(item)}>×</button>
        </div>)}</div>
      </aside>
      <main className="library-main">
        {status && <div className={`library-status ${status.ready ? "ready" : ""}`}>
          {status.ready ? `${status.documents} manuales · ${status.inventory?.items ?? 0} materiales · Gemini 3.5 Flash-Lite (nivel gratuito)` : status.detail || "Biblioteca pendiente de configuración"}
          {status.inventory?.error && <small> · Inventario: {status.inventory.error}</small>}</div>}
        <div className="library-messages">
          {messages.length === 0 && <div className="library-welcome"><h2>Consulta manuales e inventario</h2><p>Busca procedimientos, materiales, códigos, cantidades y ubicaciones.</p>
            <div className="library-suggestions">{["¿Cómo se configura un HPM?", "¿Dónde está el material 3410719?", "¿Qué indica una alarma en UCN?"].map(s =>
              <button key={s} onClick={() => setQuestion(s)}>{s}</button>)}</div></div>}
          {messages.map(message => <article key={message.id} className={`library-message ${message.role}`}>
            <div className="library-avatar">{message.role === "user" ? "Tú" : "TPS"}</div>
            <div className="library-answer"><Markdown text={message.content} />
              <div className="library-message-actions"><button onClick={() => void navigator.clipboard.writeText(message.content)}>Copiar</button>
                {message === messages[messages.length - 1] && <button disabled={working} onClick={() => void ask(true)}>{message.role === "assistant" ? "Regenerar" : "Reintentar"}</button>}</div>
              {message.sources?.length > 0 && <div className="library-sources"><strong>Fuentes</strong>{message.sources.map(source =>
                source.type === "inventory" ?
                  <span key={`inventory-${source.sheet}-${source.row}`}>[{source.number}] {source.title} · {source.sheet}, fila {source.row}</span> :
                  <button key={`${source.document_id}-${source.page}`} onClick={() => void showPdf(source)}>[{source.number}] {source.title} · pág. {source.page}</button>)}</div>}
            </div></article>)}
          {working && <article className="library-message assistant"><div className="library-avatar">TPS</div><div className="library-answer"><Markdown text={draft || "Buscando en los manuales…"} /><small>Respuesta provisional; verificando citas</small></div></article>}
          <div ref={bottom} />
        </div>
        {error && <div role="alert" className="error library-error">{error}</div>}
        <form className="library-composer" onSubmit={e => { e.preventDefault(); void ask(); }}>
          <textarea value={question} onChange={e => setQuestion(e.target.value)} placeholder="Pregunta sobre manuales TPS o inventario…"
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void ask(); } }} />
          {working ? <button type="button" onClick={() => { abort.current?.abort(); setWorking(false); setDraft(""); }}>Detener</button>
            : <button type="submit" className="btn-primary" disabled={!question.trim()}>Enviar</button>}
        </form>
      </main>
    </div>
    {(pageUrl || pdfUrl) && <div className="library-pdf-overlay" role="dialog" aria-label="Visor PDF"><div className="library-pdf-top"><span>Página PDF {pdfPage}</span>
      {!pdfUrl && <button onClick={() => void openFullPdf()}>PDF completo</button>}
      <button onClick={() => { setPageUrl(""); setPdfUrl(""); setPdfDocument(""); }}>Cerrar</button></div>
      {pdfUrl ? <iframe title="Manual citado" src={`${pdfUrl}#page=${pdfPage}`} />
        : <div className="library-pdf-page"><img src={pageUrl} alt={`Página ${pdfPage} del manual citado`} /></div>}</div>}
  </div>;
}
