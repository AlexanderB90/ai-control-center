"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

type Agent = "assistant" | "research" | "options";
type Source = { title: string; url: string };
type Web = { status: string; checked_at?: string; warning?: string; sources: Source[] };
type Message = { role: "user" | "assistant"; content: string; web?: Web; online?: boolean };
type Conversation = { id: string; agent: Agent; title: string; updated: string; messages: Message[] };
type ArchiveItem = { id: string; created_at: string; task_excerpt: string; kind: "research" | "options" };
const API = "http://localhost:8000";
const STORAGE = "ai-control-center.chats.v1";
const agents = {
  assistant: { name: "Assistent", mark: "✳", detail: "En tanke. En idé. Et sted at begynde.", intro: "Hvad har du på hjertet?", subtitle: "Dit personlige arbejdsrum. Tænk højt, stil spørgsmål, og arbejd videre på dine idéer.", suggestions: ["Hjælp mig med at få overblik over en idé", "Lad os planlægge min næste opgave", "Forklar et emne, jeg gerne vil forstå"] },
  research: { name: "Research Agent", mark: "⌕", detail: "Undersøg. Forstå. Find sammenhænge.", intro: "Hvad vil du undersøge?", subtitle: "Gå fra et åbent spørgsmål til indsigt. Vi kan tage det ét skridt ad gangen.", suggestions: ["Hjælp mig med at undersøge en virksomhed", "Sammenlign to muligheder med mig", "Find kilder til et emne"] },
  options: { name: "Options Agent", mark: "◈", detail: "Din samtalepartner om optioner.", intro: "Lad os tale om din næste handel.", subtitle: "Beskriv dine overvejelser med dine egne ord. Agenten spørger ind, når der mangler noget.", suggestions: ["Jeg overvejer en covered call på NFLX", "Hjælp mig med at forstå risikoen ved en put", "Hvornår passer en cash-secured put til mit mål?"] },
} as const;

function validChats(value: unknown): value is Conversation[] {
  if (!Array.isArray(value) || value.length > 50) return false;
  return value.every(c => c && typeof c.id === "string" &&
    ["assistant", "research", "options"].includes(c.agent) && typeof c.title === "string" &&
    typeof c.updated === "string" && Array.isArray(c.messages) && c.messages.length <= 40 &&
    c.messages.every((m: Message) => m && ["user", "assistant"].includes(m.role) && typeof m.content === "string" &&
      (!m.web || (typeof m.web.status === "string" && Array.isArray(m.web.sources) &&
        m.web.sources.every(s => typeof s.title === "string" && typeof s.url === "string")))));
}

function contextFor(messages: Message[]) {
  let selected = messages.slice(-19).map(m => ({ role: m.role, content: m.content.slice(0, 10000) }));
  while (selected.length > 1 && (selected[0].role !== "user" || selected.reduce((sum, m) => sum + m.content.length, 0) > 40000)) {
    selected = selected.slice(selected[0].role === "user" ? 2 : 1);
  }
  return selected;
}

export default function Home() {
  const [chats, setChats] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [agent, setAgent] = useState<Agent>("assistant");
  const [draft, setDraft] = useState("");
  const [web, setWeb] = useState(false);
  const [ready, setReady] = useState(false);
  const [storageOK, setStorageOK] = useState(true);
  const [storageWarning, setStorageWarning] = useState("");
  const [online, setOnline] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [menu, setMenu] = useState(false);
  const [archive, setArchive] = useState(false);
  const inFlight = useRef(false);
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const active = chats.find(c => c.id === activeId);
  const selectedAgent = active?.agent ?? agent;
  const profile = agents[selectedAgent];

  useEffect(() => {
    let mounted = true;
    Promise.resolve().then(() => {
      if (!mounted) return;
      try {
        const raw = localStorage.getItem(STORAGE);
        if (raw) {
          const stored: unknown = JSON.parse(raw);
          if (!validChats(stored)) throw new Error("Invalid history");
          setChats(stored);
        }
      } catch {
        setStorageOK(false);
        setStorageWarning("Browserens samtalehistorik kunne ikke læses. Nye samtaler gemmes kun i denne åbne fane.");
      }
      setReady(true);
    });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (!ready || !storageOK) return;
    try { localStorage.setItem(STORAGE, JSON.stringify(chats.map(c => ({ ...c, messages: c.messages.at(-1)?.role === "user" ? c.messages.slice(0, -1) : c.messages })))); }
    catch {
      // Defer state notification; persistence failure must never retry an AI call.
      Promise.resolve().then(() => setStorageWarning("Samtalen kunne ikke gemmes i browseren. Kopiér vigtig tekst, før du lukker fanen."));
    }
  }, [chats, ready, storageOK]);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();
    async function check() {
      try {
        const response = await fetch(API + "/health", { signal: controller.signal, cache: "no-store" });
        if (mounted) setOnline(response.ok);
      } catch { if (mounted) setOnline(false); }
    }
    void check();
    const timer = setInterval(check, 10000);
    return () => { mounted = false; controller.abort(); clearInterval(timer); };
  }, []);

  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [active?.messages.length, busy]);

  function newChat(next: Agent = selectedAgent) {
    if (inFlight.current) return;
    setActiveId(null); setAgent(next); setDraft(""); setError(""); setArchive(false); setMenu(false);
    input.current?.focus();
  }

  function openChat(chat: Conversation) {
    if (inFlight.current) return;
    setActiveId(chat.id); setAgent(chat.agent); setDraft(""); setError(""); setArchive(false); setMenu(false);
  }

  function deleteChat() {
    if (!active || inFlight.current || !window.confirm("Slet denne samtale fra browserens historik?")) return;
    setChats(current => current.filter(c => c.id !== active.id));
    newChat(active.agent);
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || inFlight.current || !online || !ready) return;
    if (!active && chats.length >= 50) { setError("Du har 50 samtaler. Slet en gammel samtale for at oprette en ny."); return; }
    const previous = active?.messages ?? [];
    const messages: Message[] = [...previous, { role: "user", content: text }];
    const chat: Conversation = active ?? { id: crypto.randomUUID(), agent: selectedAgent, title: text.slice(0, 65), updated: new Date().toISOString(), messages: [] };
    const useWeb = web;
    inFlight.current = true; setBusy(true); setError(""); setDraft(""); setActiveId(chat.id);
    setChats(current => [{ ...chat, messages: messages.slice(-39), updated: new Date().toISOString() }, ...current.filter(c => c.id !== chat.id)]);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 135000);
    try {
      const response = await fetch(API + "/chat/run", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
        body: JSON.stringify({ agent: chat.agent, web_research: useWeb, messages: contextFor(messages) }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Beskeden kunne ikke behandles.");
      if (typeof result.response !== "string" || !result.response.trim()) throw new Error("Agenten returnerede et tomt svar.");
      const answer: Message = { role: "assistant", content: result.response, web: result.web, online: useWeb };
      setChats(current => current.map(c => c.id === chat.id ? { ...c, messages: [...messages, answer].slice(-40), updated: new Date().toISOString() } : c));
    } catch (failure) {
      setChats(current => current.map(c => c.id === chat.id ? { ...c, messages: previous } : c));
      setDraft(text);
      setError(failure instanceof Error && failure.name === "AbortError" ? "Svaret nåede ikke frem inden tidsgrænsen. Ingen automatisk gentagelse." :
        failure instanceof Error && !(failure instanceof TypeError) ? failure.message : "Kunne ikke forbinde til agenten. Kontrollér at serveren kører.");
    } finally {
      clearTimeout(timer); inFlight.current = false; setBusy(false);
    }
  }

  return <main className="workspace">
    {menu && <button className="sidebar-shade" aria-label="Luk menu" onClick={() => setMenu(false)} />}
    <aside className={"sidebar " + (menu ? "sidebar-open" : "")} aria-label="Arbejdsrum">
      <a href="/" className="brand"><span className="brand-symbol">✳</span><span>Control Center<small>ALEXANDERS ARBEJDSRUM</small></span></a>
      <button className="new-chat" disabled={busy || !ready} onClick={() => newChat()}><span>＋</span> Ny samtale <span className="button-hint">↗</span></button>
      <p className="nav-label">DINE AGENTER <span>03</span></p>
      <nav className="agent-nav" aria-label="Vælg agent">{(Object.keys(agents) as Agent[]).map(key =>
        <button key={key} disabled={busy} onClick={() => newChat(key)} className={!archive && selectedAgent === key ? "selected" : ""}>
          <span className="nav-icon">{agents[key].mark}</span><span>{agents[key].name}</span>
          {!archive && selectedAgent === key && <span className="active-dot" />}
        </button>)}</nav>
      <div className="history-heading"><p className="nav-label">SAMTALER</p><span>{chats.length.toString().padStart(2, "0")}</span></div>
      <nav className="conversation-nav" aria-label="Tidligere samtaler">
        {!chats.length && <p className="empty-history">Dine samtaler finder et hjem her.</p>}
        {chats.map(chat => <button key={chat.id} disabled={busy} onClick={() => openChat(chat)} className={!archive && activeId === chat.id ? "current" : ""}>
          <span className="conversation-mark">{agents[chat.agent].mark}</span><span>{chat.title || "Ny samtale"}</span>
        </button>)}
      </nav>
      <button className={"archive-button " + (archive ? "current" : "")} disabled={busy} onClick={() => { setArchive(true); setMenu(false); }}><span>▤</span> Tidligere analyser <span>↗</span></button>
      <div className="sidebar-footer"><span className="avatar">A</span><div>Alexander<small>Personligt arbejdsrum</small></div><span className="footer-dot" /></div>
    </aside>

    <section className="main-pane">
      <header className="topbar">
        <div className="breadcrumbs"><button className="mobile-menu" aria-label="Åbn menu" onClick={() => setMenu(true)}>☰</button><span>Arbejdsrum</span><span className="slash">/</span><strong>{archive ? "Tidligere analyser" : profile.name}</strong></div>
        <div className="topbar-actions"><span className={"connection " + (online ? "connected" : "")}><i />{online === null ? "Forbinder" : online ? "Forbundet" : "Offline"}</span>
          {!archive && active && <button className="text-button" disabled={busy} onClick={deleteChat}>Slet samtale</button>}</div>
      </header>
      {storageWarning && <p className="storage-warning" role="alert">{storageWarning}</p>}
      {archive ? <Archive /> : <>
        <div className="conversation-area">
          {!active?.messages.length ? <div className="welcome">
            <div className="welcome-emblem">{profile.mark}<span /></div>
            <p className="eyebrow">PLADS TIL DINE TANKER</p>
            <h1>{profile.intro}</h1><p className="welcome-description">{profile.subtitle}</p>
            <div className="suggestions">{profile.suggestions.map((suggestion, index) => <button key={suggestion} disabled={busy || !ready} onClick={() => { setDraft(suggestion); input.current?.focus(); }}>
              <span className="suggestion-number">0{index + 1}</span><span>{suggestion}</span><span className="suggestion-arrow">↗</span>
            </button>)}</div>
            <p className="welcome-note">Begynd med et spørgsmål. Resten tager vi undervejs.</p>
          </div> : <div className="messages">
            <p className="conversation-title">{profile.detail}</p>
            {active.messages.map((message, index) => <article key={index} className={"message " + message.role}>
              <div className="message-avatar">{message.role === "user" ? "A" : profile.mark}</div>
              <div className="message-body"><div className="message-label">{message.role === "user" ? "Dig" : profile.name}
                {message.role === "assistant" && <span>{message.online ? "Med websøgning" : "Uden web"}</span>}</div>
                <div className="message-text">{message.content}</div>
                {message.web && <WebSources web={message.web} />}
              </div>
            </article>)}
            {busy && <div className="thinking" role="status"><span className="message-avatar">{profile.mark}</span><span>{web ? "Undersøger og samler et svar" : "Tænker over dit spørgsmål"}<span className="thinking-dots"> …</span></span></div>}
            <div ref={end} />
          </div>}
        </div>
        <div className="composer-region">
          {error && <p role="alert" className="chat-error">{error}</p>}
          <form className="composer" onSubmit={send}>
            <label className="sr-only" htmlFor="message">Besked til {profile.name}</label>
            <textarea id="message" ref={input} value={draft} disabled={busy || !ready} maxLength={10000} rows={2}
              onChange={e => setDraft(e.target.value)} placeholder={"Skriv til " + profile.name + "…"}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }} />
            <div className="composer-toolbar">
              <label className={"web-toggle " + (web ? "enabled" : "")}><input type="checkbox" checked={web} disabled={busy} onChange={e => setWeb(e.target.checked)} /><span>◎</span> Søg på nettet</label>
              <span className="composer-agent">{profile.mark} {profile.name}</span>
              <button type="submit" className="send-button" aria-label="Send besked" disabled={busy || !online || !ready || !draft.trim()}>{busy ? "···" : "↑"}</button>
            </div>
          </form>
          <p className="composer-caption">{!online && online !== null ? "Start serveren med python3 dev.py for at skrive til agenterne." : "Enter sender · Shift + Enter giver ny linje"}<span>Samtaler gemmes i denne browser.</span></p>
          <details className="privacy-note"><summary>Om samtaler og data</summary><p>De seneste 40 beskeder pr. samtale gemmes i klartekst i denne browser. Et udsnit på højst 19 beskeder og 40.000 tegn sendes via Codex ved hvert svar. Chatten har ikke automatisk adgang til andre samtaler eller dine tidligere analyser. Websøgning er eksperimentel. Optionschatten giver samtalebaseret vejledning; svar er ikke kontrolleret af beregningsmotoren.</p></details>
        </div>
      </>}
    </section>
  </main>;
}

function WebSources({ web }: { web: Web }) {
  return <details className="source-details"><summary>◎ {web.status === "searched" ? "Websøgning registreret" : "Webstatus"} · {web.sources.length} kildelinks</summary>
    {web.warning && <p>{web.warning}</p>}
    <ul>{web.sources.filter(s => s.url.startsWith("https://")).map(source => <li key={source.url}><a href={source.url} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">{source.title} ↗</a></li>)}</ul>
  </details>;
}

function Archive() {
  const [items, setItems] = useState<ArchiveItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [opening, setOpening] = useState(false);
  const [saved, setSaved] = useState<{ title: string; response: string; data?: unknown } | null>(null);
  useEffect(() => {
    let active = true;
    Promise.all((["research", "options"] as const).map(async kind => {
      const response = await fetch(API + "/agents/" + kind + "/history", { cache: "no-store" });
      if (!response.ok) throw new Error("Historikken kunne ikke hentes.");
      const list: Omit<ArchiveItem, "kind">[] = await response.json();
      return list.map(item => ({ ...item, kind }));
    })).then(lists => { if (active) setItems(lists.flat().sort((a, b) => b.created_at.localeCompare(a.created_at))); })
      .catch(() => { if (active) setError("Tidligere analyser kunne ikke hentes. Kontrollér forbindelsen og åbn siden igen."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  async function open(item: ArchiveItem) {
    setOpening(true); setError("");
    try {
      const response = await fetch(API + "/agents/" + item.kind + "/history/" + encodeURIComponent(item.id));
      if (!response.ok) throw new Error();
      const record = await response.json();
      setSaved({ title: record.task, response: item.kind === "options" ? record.result?.response || "Ingen AI-vurdering gemt." : record.response, data: record.result?.calculation });
    } catch { setError("Analysen kunne ikke åbnes."); }
    finally { setOpening(false); }
  }
  return <div className="archive-view"><p className="eyebrow">DIT ARKIV</p><h1>Tidligere analyser</h1><p className="archive-intro">Dine gemte research- og optionsanalyser fra det tidligere dashboard.</p>
    {loading && <p role="status">Henter analyser…</p>}{error && <p className="chat-error" role="alert">{error}</p>}
    {saved ? <div className="saved-analysis"><button className="text-button" onClick={() => setSaved(null)}>← Tilbage til arkivet</button><h2>{saved.title}</h2><div className="message-text">{saved.response}</div>
      {saved.data != null && <details className="source-details"><summary>Vis gemte beregningsdata</summary><pre>{JSON.stringify(saved.data, null, 2)}</pre></details>}</div> :
      <div className="archive-list">{!loading && !error && items.length === 0 && <p>Ingen gemte analyser endnu.</p>}
        {items.map(item => <button key={item.kind + item.id} disabled={opening} onClick={() => open(item)}><span className="archive-kind">{item.kind === "options" ? "◈ Options Agent" : "⌕ Research Agent"}</span><strong>{item.task_excerpt}</strong><small>{new Date(item.created_at).toLocaleString("da-DK")} ↗</small></button>)}</div>}
    {opening && <p role="status">Åbner analyse…</p>}
  </div>;
}
