"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import { Settings, X, ArrowUp, Download, ExternalLink } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const REGIONS = ["All", "US", "UK", "EMEA", "APAC", "LATAM", "NA"];
const EXAMPLES = [
  "How many vacation days can I carry over in the UK?",
  "What is the notice period for EMP-102?",
  "Compare the carry-over cap for EMP-101 and EMP-104",
];

type Chunk = { chunk_id?: string; section?: string; region?: string; score?: number; text?: string };

type Turn = {
  id: string;
  question: string;
  region: string;
  answer?: string;
  citations?: string[];
  chunks?: Chunk[];
  latencyMs?: number;
  tokens?: number;
  status?: string;
  route?: string;
  routeReasons?: string[];
  traceId?: string;
  error?: string;
  feedback?: "up" | "down";
};

const STATUS_LABEL: Record<string, string> = {
  VERIFIED: "Answered",
  PROMPT_INJECTION_BLOCKED: "Blocked: unsafe input",
  GUARDRAIL_BLOCKED: "Blocked: answer check",
  PIPELINE_ERROR: "Error",
};

const ROUTE_LABEL: Record<string, string> = {
  rag: "Searched the handbook",
  fixed_workflow: "Looked up the employee record",
  react_agent: "Agent checked each topic",
  multi_agent_squad: "Compared employees in parallel",
  policy_desk: "India / UK policy desk",
  blocked: "Blocked before answering",
};

const SPAN_LABEL: Record<string, string> = {
  query_condensation: "Rewrite follow-up",
  input_injection_scan: "Check question",
  route_decision: "Choose route",
  rag: "Handbook search",
  hybrid_retrieval: "Find passages",
  dense_search: "Vector search",
  bm25_search: "Keyword search",
  rrf_fusion: "Merge rankings",
  answer_synthesis: "Write answer",
  llm_call: "Model call",
  fixed_workflow: "Fixed workflow",
  react_agent: "ReAct agent",
  multi_agent_squad: "Agent squad",
  policy_desk: "Policy desk",
  output_invariant_check: "Check answer",
  "eval::failure_taxonomy": "Failure label",
  "eval::citation_grounding": "Citation check",
};

function spanLabel(name: string) {
  if (SPAN_LABEL[name]) return SPAN_LABEL[name];
  const [kind, ...rest] = name.split("::");
  const pretty: Record<string, string> = { tool: "Tool", mcp_tool: "MCP tool", react_loop: "Agent loop", squad: "Specialist" };
  return pretty[kind] ? `${pretty[kind]} · ${rest.join(" · ").replaceAll("_", " ")}` : name.replaceAll("_", " ");
}

function shortCite(c: string) {
  return c.replace(/Section\s*/i, "§").trim();
}

/** Renders **bold**, [[citation]] stamps, list dashes and paragraphs. Nothing else in the answers needs markup. */
function AnswerText({ text }: { text: string }) {
  return (
    <>
      {text.split(/\n{2,}/).map((para, i) => (
        <p key={i} className="mt-3 first:mt-0">
          {para.split(/(\*\*[^*]+\*\*|\[\[[^\]]+\]\])/g).map((part, j) => {
            if (part.startsWith("**")) return <strong key={j} className="font-semibold text-champagne">{part.slice(2, -2)}</strong>;
            if (part.startsWith("[[")) return <span key={j} className="hallmark mx-0.5">{shortCite(part.slice(2, -2))}</span>;
            return (
              <Fragment key={j}>
                {part.split("\n").map((line, k) => (
                  <Fragment key={k}>{k > 0 && <br />}{line.replace(/^- /, "— ")}</Fragment>
                ))}
              </Fragment>
            );
          })}
        </p>
      ))}
    </>
  );
}

export default function Home() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [region, setRegion] = useState("All");
  const [busy, setBusy] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [focusTrace, setFocusTrace] = useState<string | null>(null);
  const [sessionId] = useState(() => (typeof crypto !== "undefined" ? crypto.randomUUID() : "local"));
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  const ask = async (q?: string) => {
    const question = (q ?? draft).trim();
    if (!question || busy) return;
    const id = crypto.randomUUID();
    const history = turns.filter((t) => t.answer).map((t) => ({ user: t.question, assistant: t.answer! }));
    setTurns((prev) => [...prev, { id, question, region }]);
    setDraft("");
    setBusy(true);
    const patch = (p: Partial<Turn>) => setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...p } : t)));
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: question, history, region: region === "All" ? null : region, top_k: 5, hybrid: true, session_id: sessionId,
        }),
      });
      if (!res.ok) throw new Error(`The policy service returned ${res.status}.`);
      const d = await res.json();
      patch({
        answer: d.answer,
        citations: d.citations,
        chunks: d.retrieved_chunks,
        latencyMs: d.latency_ms,
        tokens: d.tokens_used,
        status: d.security_status,
        route: d.route,
        routeReasons: d.route_reasons,
        traceId: d.langfuse_trace_id,
      });
    } catch (e) {
      patch({
        error: e instanceof TypeError
          ? `Couldn't reach the policy service at ${API_BASE}. Start the backend, then ask again.`
          : (e as Error).message,
      });
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  };

  const sendFeedback = async (turn: Turn, value: "up" | "down") => {
    setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, feedback: value } : t)));
    if (!turn.traceId) return;
    await fetch(`${API_BASE}/api/capstone/traces/${turn.traceId}/score`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "user_feedback", value: value === "up" ? 1 : 0 }),
    }).catch(() => {});
  };

  const openTrace = (traceId?: string) => {
    setFocusTrace(traceId ?? null);
    setSettingsOpen(true);
  };

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between gap-4 border-b border-cherry-800 px-4 py-3 sm:px-8">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-2xl italic tracking-tight">Policy Desk</span>
          <span className="hidden font-mono text-[11px] uppercase tracking-[0.2em] text-champagne-muted sm:inline">HR-207</span>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-champagne-muted">
            <span className="hidden sm:inline">Region</span>
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="rounded-sm border border-cherry-700 bg-cherry-900 px-2 py-1 text-sm text-champagne"
            >
              {REGIONS.map((r) => (
                <option key={r} value={r}>{r === "All" ? "All regions" : r}</option>
              ))}
            </select>
          </label>
          <button
            onClick={() => openTrace()}
            aria-label="Settings"
            className="rounded-sm p-2 text-champagne-muted transition-colors hover:bg-cherry-800 hover:text-champagne"
          >
            <Settings size={18} strokeWidth={1.6} />
          </button>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-4 pb-10 pt-10 sm:px-6">
          {turns.length === 0 ? (
            <section className="pt-[12vh]">
              <h1 className="font-display text-4xl leading-[1.1] sm:text-5xl">
                Ask the leave policy <em className="text-rose">anything.</em>
              </h1>
              <p className="mt-4 max-w-md text-champagne-muted">
                Every answer quotes where it comes from. Name an employee ID to check their own entitlement.
              </p>
              <ul className="mt-10 border-t border-cherry-800">
                {EXAMPLES.map((q) => (
                  <li key={q} className="border-b border-cherry-800">
                    <button
                      onClick={() => ask(q)}
                      className="w-full py-3 text-left text-champagne/90 transition-colors hover:text-rose"
                    >
                      {q}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ) : (
            <ol className="space-y-12">
              {turns.map((t) => (
                <li key={t.id}>
                  <p className="text-sm text-champagne-muted">
                    <span className="mr-2 font-mono text-[11px] uppercase tracking-[0.15em] text-rose">
                      {t.region === "All" ? "You" : `You · ${t.region}`}
                    </span>
                    {t.question}
                  </p>

                  <div className="mt-3 text-[17px] leading-relaxed text-champagne/95">
                    {t.error ? (
                      <p className="text-rose">{t.error}</p>
                    ) : t.answer === undefined ? (
                      <p className="text-champagne-muted motion-safe:animate-pulse">Reading the handbook…</p>
                    ) : (
                      <AnswerText text={t.answer} />
                    )}
                  </div>

                  {t.answer !== undefined && (
                    <>
                      {(() => {
                        const extra = (t.citations ?? []).filter((c) => !t.answer!.includes(`[[${c}]]`));
                        return extra.length > 0 && (
                          <div className="mt-4 flex flex-wrap gap-2">
                            {extra.map((c) => <span key={c} className="hallmark">{shortCite(c)}</span>)}
                          </div>
                        );
                      })()}

                      {!!t.chunks?.length && (
                        <details className="group mt-4 text-sm">
                          <summary className="cursor-pointer list-none text-champagne-muted hover:text-champagne">
                            <span className="group-open:hidden">Show the {t.chunks.length} passages used</span>
                            <span className="hidden group-open:inline">Hide passages</span>
                          </summary>
                          <ul className="mt-3 space-y-3 border-l border-cherry-700 pl-4">
                            {t.chunks.map((c, i) => (
                              <li key={c.chunk_id ?? i}>
                                <div className="font-mono text-[11px] text-rose">
                                  {c.section} · {c.region}
                                  {c.score !== undefined && <span className="text-champagne-muted"> · {c.score.toFixed(3)}</span>}
                                </div>
                                <p className="mt-1 line-clamp-3 text-champagne-muted">{c.text}</p>
                              </li>
                            ))}
                          </ul>
                        </details>
                      )}

                      <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 font-mono text-[11px] text-champagne-muted">
                        {t.route && (
                          <span title={t.routeReasons?.join(" ")} className="font-sans text-xs text-champagne/80">
                            {ROUTE_LABEL[t.route] ?? t.route}
                          </span>
                        )}
                        {t.status && t.status !== "VERIFIED" && <span className="text-rose">{STATUS_LABEL[t.status] ?? t.status}</span>}
                        <span>{(t.latencyMs ?? 0) < 1 ? "<1" : Math.round(t.latencyMs ?? 0)} ms</span>
                        {!!t.tokens && <span>{t.tokens} tokens</span>}
                        {t.traceId && (
                          <button onClick={() => openTrace(t.traceId)} className="underline decoration-cherry-700 underline-offset-4 hover:text-champagne">
                            trace {t.traceId.slice(0, 8)}
                          </button>
                        )}
                        <span className="ml-auto flex gap-3 font-sans text-xs">
                          {t.feedback ? (
                            <span>Feedback recorded</span>
                          ) : (
                            <>
                              <button onClick={() => sendFeedback(t, "up")} className="hover:text-champagne">Helpful</button>
                              <button onClick={() => sendFeedback(t, "down")} className="hover:text-champagne">Not helpful</button>
                            </>
                          )}
                        </span>
                      </div>
                    </>
                  )}
                </li>
              ))}
            </ol>
          )}
          <div ref={endRef} />
        </div>
      </main>

      <form
        onSubmit={(e) => { e.preventDefault(); ask(); }}
        className="border-t border-cherry-800 bg-cherry-900/60 px-4 py-4 sm:px-8"
      >
        <div className="mx-auto flex max-w-2xl items-end gap-3 rounded-sm border border-cherry-700 bg-cherry-950 px-4 py-2 focus-within:border-rose-deep">
          <textarea
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); }
            }}
            rows={1}
            placeholder="Ask about leave, notice periods, carry-over…"
            aria-label="Your question"
            className="max-h-40 flex-1 resize-none bg-transparent py-1.5 text-champagne placeholder:text-champagne-muted/70 focus:outline-none"
          />
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            aria-label="Ask"
            className="mb-0.5 rounded-sm bg-rose-deep p-2 text-cherry-950 transition-opacity hover:bg-rose disabled:opacity-30"
          >
            <ArrowUp size={16} strokeWidth={2.2} />
          </button>
        </div>
      </form>

      <SettingsDrawer open={settingsOpen} focusTrace={focusTrace} sessionId={sessionId} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}

/* ------------------------------------------------------------------ settings */

type Stats = {
  total_queries: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  total_tokens_in: number;
  total_tokens_out: number;
  pii_compliance_rate_pct: number;
  route_distribution: Record<string, number>;
  failure_taxonomy: Record<string, number>;
  score_averages: Record<string, number>;
  langfuse_status: { is_active: boolean; host: string; store: string; release: string | null };
};

type Score = { name: string; value: number; source: string; comment: string };

type TraceRow = {
  trace_id: string;
  status: string;
  route: string | null;
  timestamp_start: string;
  total_latency_ms: number;
  request: { input?: { query?: string }; session_id?: string };
  attributes: Record<string, unknown>;
  final_response?: { route_reasons?: string[] };
  error?: { type: string; message: string; traceback: string };
  pii_audit_status?: { is_compliant: boolean; violations: string[] };
  langfuse_url?: string | null;
  scores?: Score[];
};

type Segment = {
  span_id: string; name: string; category: string; depth: number; latency_ms: number; start_offset_ms: number;
  left_pct: number; width_pct: number; tokens: { in: number; out: number }; level?: string | null;
  error?: { type: string; message: string; traceback: string } | null;
  input?: unknown; output?: unknown; attributes: Record<string, unknown>;
};

function Json({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null || (typeof value === "object" && Object.keys(value as object).length === 0)) return null;
  return (
    <div className="mt-2">
      <div className="text-[10px] uppercase tracking-[0.15em] text-champagne-muted">{label}</div>
      <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-sm bg-cherry-950 p-2 font-mono text-[11px] leading-snug text-champagne/90">
        {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

function SettingsDrawer({ open, focusTrace, sessionId, onClose }: { open: boolean; focusTrace: string | null; sessionId: string; onClose: () => void }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [scope, setScope] = useState<"session" | "all">("session");
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<TraceRow | null>(null);
  const [segments, setSegments] = useState<Segment[] | null>(null);
  const [openSpan, setOpenSpan] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    setSelected(focusTrace);
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, focusTrace, onClose]);

  useEffect(() => {
    if (!open) return;
    setLoadError(null);
    const filter = scope === "session" ? `&session_id=${sessionId}` : "";
    Promise.all([
      fetch(`${API_BASE}/api/capstone/traces/stats?name=rag_chat`).then((r) => r.json()),
      fetch(`${API_BASE}/api/capstone/traces?name=rag_chat&limit=30${filter}`).then((r) => r.json()),
    ])
      .then(([s, t]) => { setStats(s); setTraces(t.traces); })
      .catch(() => setLoadError(`Couldn't load traces from ${API_BASE}. Is the backend running?`));
  }, [open, scope, sessionId]);

  useEffect(() => {
    setSegments(null);
    setDetail(null);
    setOpenSpan(null);
    if (!selected) return;
    fetch(`${API_BASE}/api/capstone/traces/${selected}`).then((r) => (r.ok ? r.json() : null)).then(setDetail).catch(() => {});
    fetch(`${API_BASE}/api/capstone/traces/waterfall/${selected}`)
      .then((r) => (r.ok ? r.json() : { segments: [] }))
      .then((w) => setSegments(w.segments))
      .catch(() => setSegments([]));
  }, [selected]);

  const lf = stats?.langfuse_status;
  const turn = detail?.attributes?.turn as number | undefined;

  return (
    <>
      <div
        onClick={onClose}
        className={`fixed inset-0 bg-black/50 transition-opacity ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
        aria-hidden
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        inert={!open}
        className={`fixed inset-y-0 right-0 flex w-full max-w-xl flex-col border-l border-cherry-700 bg-cherry-900 transition-transform duration-300 ${open ? "translate-x-0" : "translate-x-full"}`}
      >
        <div className="flex items-center justify-between border-b border-cherry-800 px-6 py-4">
          <h2 className="font-display text-xl italic">Settings</h2>
          <button ref={closeRef} onClick={onClose} aria-label="Close settings" className="rounded-sm p-1.5 text-champagne-muted hover:bg-cherry-800 hover:text-champagne">
            <X size={18} strokeWidth={1.6} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          <h3 className="font-mono text-[11px] uppercase tracking-[0.2em] text-rose">Observability</h3>

          {loadError && <p className="mt-4 text-sm text-rose">{loadError}</p>}

          {lf && (
            <p className="mt-4 text-sm leading-relaxed text-champagne-muted">
              {lf.is_active ? (
                <>Sending traces to <span className="text-champagne">Langfuse</span> at {lf.host.replace(/^https?:\/\//, "")}, and keeping every one locally.</>
              ) : (
                <>Every trace is kept on this server. Add <code className="font-mono text-xs text-champagne">LANGFUSE_PUBLIC_KEY</code> and <code className="font-mono text-xs text-champagne">LANGFUSE_SECRET_KEY</code> to <code className="font-mono text-xs text-champagne">.env</code> to also send them to Langfuse.</>
              )}
              {lf.release && <span className="font-mono text-[11px]"> Build {lf.release}.</span>}
            </p>
          )}

          {stats && (
            <>
              <dl className="mt-6 grid grid-cols-3 gap-px overflow-hidden rounded-sm border border-cherry-800 bg-cherry-800 text-center">
                {[
                  ["Questions", stats.total_queries.toString()],
                  ["Median", `${Math.round(stats.p50_latency_ms)} ms`],
                  ["p95", `${Math.round(stats.p95_latency_ms)} ms`],
                  ["Tokens in", stats.total_tokens_in.toLocaleString()],
                  ["Tokens out", stats.total_tokens_out.toLocaleString()],
                  ["PII clean", `${stats.pii_compliance_rate_pct}%`],
                ].map(([k, v]) => (
                  <div key={k} className="bg-cherry-900 px-2 py-3">
                    <dt className="text-[11px] text-champagne-muted">{k}</dt>
                    <dd className="mt-1 font-mono text-sm text-champagne">{v}</dd>
                  </div>
                ))}
              </dl>

              <div className="mt-4 grid grid-cols-2 gap-6 text-xs">
                <div>
                  <div className="text-champagne-muted">Routes taken</div>
                  <ul className="mt-1.5 space-y-1">
                    {Object.entries(stats.route_distribution).map(([r, n]) => (
                      <li key={r} className="flex justify-between"><span>{ROUTE_LABEL[r] ?? r}</span><span className="font-mono">{n}</span></li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="text-champagne-muted">Outcome labels</div>
                  <ul className="mt-1.5 space-y-1">
                    {Object.entries(stats.failure_taxonomy).map(([l, n]) => (
                      <li key={l} className="flex justify-between"><span>{l.replaceAll("_", " ").toLowerCase()}</span><span className="font-mono">{n}</span></li>
                    ))}
                    {stats.score_averages.citation_grounding !== undefined && (
                      <li className="flex justify-between"><span>citations grounded</span><span className="font-mono">{Math.round(stats.score_averages.citation_grounding * 100)}%</span></li>
                    )}
                  </ul>
                </div>
              </div>
            </>
          )}

          {selected && (
            <section className="mt-8 rounded-sm border border-cherry-700 p-4">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm text-champagne">{detail?.request.input?.query ?? "Loading…"}</p>
                <button onClick={() => setSelected(null)} aria-label="Close trace" className="text-champagne-muted hover:text-champagne">
                  <X size={14} />
                </button>
              </div>
              {detail && (
                <>
                  <p className="mt-1 font-mono text-[11px] text-champagne-muted">
                    {detail.trace_id} · {Math.round(detail.total_latency_ms)} ms{turn ? ` · turn ${turn}` : ""}
                  </p>
                  {detail.route && (
                    <div className="mt-3 text-xs">
                      <span className="text-rose">{ROUTE_LABEL[detail.route] ?? detail.route}.</span>{" "}
                      <span className="text-champagne-muted">{detail.final_response?.route_reasons?.join(" ")}</span>
                    </div>
                  )}
                  {!!detail.scores?.length && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {detail.scores.map((s, i) => (
                        <span key={i} title={s.comment} className="rounded-sm border border-cherry-700 px-1.5 py-0.5 font-mono text-[10px] text-champagne-muted">
                          {s.name} <span className="text-champagne">{Number.isInteger(s.value) ? s.value : s.value.toFixed(3)}</span>
                          {s.source === "user" && " · you"}
                        </span>
                      ))}
                    </div>
                  )}
                  {detail.pii_audit_status && !detail.pii_audit_status.is_compliant && (
                    <p className="mt-3 text-xs text-rose">PII found in telemetry: {detail.pii_audit_status.violations.join(", ")}</p>
                  )}
                  {detail.error && <Json label="Error" value={detail.error.traceback} />}
                </>
              )}

              <ul className="mt-4 space-y-1">
                {segments === null && <li className="text-xs text-champagne-muted">Loading steps…</li>}
                {segments?.map((s) => (
                  <li key={s.span_id}>
                    <button
                      onClick={() => setOpenSpan(openSpan === s.span_id ? null : s.span_id)}
                      aria-expanded={openSpan === s.span_id}
                      className="w-full rounded-sm px-1 py-1 text-left hover:bg-cherry-800/60"
                      style={{ paddingLeft: `${s.depth * 14 + 4}px` }}
                    >
                      <div className="flex justify-between gap-3 text-xs">
                        <span className={s.level === "ERROR" || s.error ? "text-rose" : s.level === "WARNING" ? "text-rose/80" : "text-champagne/90"}>
                          {s.category === "event" ? "◆ " : ""}{spanLabel(s.name)}
                        </span>
                        <span className="shrink-0 font-mono text-champagne-muted">
                          {s.tokens.in + s.tokens.out > 0 && `${s.tokens.in}→${s.tokens.out} tok · `}
                          {s.category === "event" ? `@${s.start_offset_ms.toFixed(1)}` : s.latency_ms < 1 ? s.latency_ms.toFixed(2) : Math.round(s.latency_ms)} ms
                        </span>
                      </div>
                      {s.category !== "event" && (
                        <div className="relative mt-1 h-1 rounded-full bg-cherry-800">
                          <div
                            className={`absolute inset-y-0 rounded-full ${s.category === "guardrail" || s.category === "evaluator" ? "bg-champagne-muted" : "bg-rose-deep"}`}
                            style={{ left: `${s.left_pct}%`, width: `${s.width_pct}%` }}
                          />
                        </div>
                      )}
                    </button>
                    {openSpan === s.span_id && (
                      <div className="mb-2 mt-1 border-l border-cherry-700 pl-3" style={{ marginLeft: `${s.depth * 14 + 4}px` }}>
                        <div className="font-mono text-[10px] text-champagne-muted">{s.name} · {s.category} · starts at {s.start_offset_ms} ms</div>
                        <Json label="Input" value={s.input} />
                        <Json label="Output" value={s.output} />
                        <Json label="Details" value={s.attributes} />
                        {s.error && <Json label="Error" value={s.error.traceback} />}
                      </div>
                    )}
                  </li>
                ))}
              </ul>

              {detail && (
                <details className="mt-4 text-xs">
                  <summary className="cursor-pointer text-champagne-muted hover:text-champagne">Request details</summary>
                  <Json label="Pipeline config and client" value={detail.attributes} />
                  <Json label="Session" value={detail.request.session_id} />
                </details>
              )}
              {detail?.langfuse_url && (
                <a href={detail.langfuse_url} target="_blank" rel="noreferrer" className="mt-4 inline-flex items-center gap-1.5 text-xs text-rose hover:text-champagne">
                  Open in Langfuse <ExternalLink size={12} />
                </a>
              )}
            </section>
          )}

          <div className="mt-8 flex items-center justify-between">
            <h4 className="text-sm text-champagne">Recent questions</h4>
            <div className="flex gap-3 text-xs" role="group" aria-label="Which questions">
              {(["session", "all"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setScope(s)}
                  aria-pressed={scope === s}
                  className={scope === s ? "text-rose" : "text-champagne-muted hover:text-champagne"}
                >
                  {s === "session" ? "This conversation" : "All"}
                </button>
              ))}
            </div>
          </div>
          {traces.length === 0 && !loadError ? (
            <p className="mt-2 text-sm text-champagne-muted">
              {scope === "session" ? "Nothing asked in this conversation yet." : "No questions traced yet. Ask one and it appears here."}
            </p>
          ) : (
            <ul className="mt-2 divide-y divide-cherry-800 border-y border-cherry-800">
              {traces.map((t) => {
                const fb = t.scores?.find((s) => s.name === "user_feedback");
                return (
                  <li key={t.trace_id}>
                    <button
                      onClick={() => setSelected(t.trace_id)}
                      className={`w-full py-2.5 text-left text-sm transition-colors hover:text-rose ${t.trace_id === selected ? "text-rose" : "text-champagne/90"}`}
                    >
                      <span className="line-clamp-1">{t.request.input?.query ?? t.trace_id}</span>
                      <span className="mt-0.5 flex flex-wrap gap-x-3 font-mono text-[11px] text-champagne-muted">
                        <span>{new Date(t.timestamp_start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                        <span>{Math.round(t.total_latency_ms)} ms</span>
                        {t.route && <span>{t.route.replaceAll("_", " ")}</span>}
                        {t.status !== "VERIFIED" && <span className="text-rose">{STATUS_LABEL[t.status] ?? t.status}</span>}
                        {fb && <span>{fb.value ? "helpful" : "not helpful"}</span>}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="mt-6 flex gap-4 text-xs">
            {(["json", "jsonl"] as const).map((f) => (
              <a key={f} href={`${API_BASE}/api/capstone/traces/export/download?format=${f}`} download={`traces.${f}`} className="inline-flex items-center gap-1.5 text-champagne-muted hover:text-champagne">
                <Download size={12} /> Download {f.toUpperCase()}
              </a>
            ))}
          </div>
        </div>
      </aside>
    </>
  );
}
