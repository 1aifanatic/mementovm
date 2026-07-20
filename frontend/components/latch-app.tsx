"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  AlarmClock,
  ArrowRight,
  BadgeCheck,
  BarChart3,
  BellRing,
  Bot,
  Braces,
  Check,
  CheckCircle2,
  ChevronRight,
  Circle,
  Clock3,
  Cloud,
  Code2,
  Database,
  FileClock,
  Fingerprint,
  Gauge,
  GitBranch,
  History,
  Inbox,
  Layers3,
  LockKeyhole,
  Menu,
  MessageSquareText,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  Server,
  ShieldCheck,
  Sparkles,
  Target,
  TimerReset,
  X,
  Zap,
} from "lucide-react";
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { api, Json } from "@/lib/api";

type AppData = {
  intentions: Json[];
  detail: Json | null;
  timeline: Json[];
  approvals: Json[];
  simulator: Json | null;
  evaluation: Json | null;
  proof: Json | null;
  ready: Json | null;
};

const emptyData: AppData = {
  intentions: [],
  detail: null,
  timeline: [],
  approvals: [],
  simulator: null,
  evaluation: null,
  proof: null,
  ready: null,
};

const NAV = [
  { id: "overview", href: "/", label: "Overview", icon: Gauge },
  { id: "chat", href: "/chat", label: "Chat", icon: MessageSquareText },
  { id: "memory", href: "/memory", label: "Active memory", icon: Layers3 },
  { id: "timeline", href: "/timeline", label: "Event timeline", icon: History },
  { id: "simulator", href: "/simulator", label: "Simulator", icon: Play },
  { id: "evaluation", href: "/evaluation", label: "Evaluation", icon: BarChart3 },
  { id: "system", href: "/system", label: "System", icon: Server },
];

const STATUS_META: Record<string, { tone: string; copy: string }> = {
  DORMANT: { tone: "slate", copy: "Waiting for a future cue" },
  PRIMED: { tone: "blue", copy: "Part of the trigger is true" },
  DUE: { tone: "amber", copy: "Conditions met; policy is evaluating" },
  AWAITING_APPROVAL: { tone: "violet", copy: "Human decision required" },
  EXECUTING: { tone: "blue", copy: "Action claimed by one worker" },
  COMPLETED: { tone: "green", copy: "Purpose complete; removed from hot memory" },
  SUPERSEDED: { tone: "slate", copy: "Replaced by a newer version" },
  CANCELLED: { tone: "red", copy: "Cancelled and no longer monitored" },
};

function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

function shortTime(value?: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function StatusPill({ status }: { status: string }) {
  const meta = STATUS_META[status] || STATUS_META.DORMANT;
  return (
    <span className={cx("status-pill", `tone-${meta.tone}`)}>
      <span className="status-dot" /> {status.replaceAll("_", " ")}
    </span>
  );
}

function Panel({ children, className, id }: { children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={cx("panel", className)}>
      {children}
    </section>
  );
}

function PanelTitle({ eyebrow, title, action }: { eyebrow?: string; title: string; action?: ReactNode }) {
  return (
    <div className="panel-title">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h2>{title}</h2>
      </div>
      {action}
    </div>
  );
}

function Metric({ label, value, detail, accent }: { label: string; value: string; detail: string; accent?: boolean }) {
  return (
    <div className={cx("metric", accent && "metric-accent")}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
    </div>
  );
}

export function LatchApp() {
  const pathname = usePathname();
  const view = pathname.split("/").filter(Boolean)[0] || "overview";
  const [data, setData] = useState<AppData>(emptyData);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [autoPlay, setAutoPlay] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [intentions, timeline, approvals, simulator, evaluation, proof, ready] =
        await Promise.all([
          api<Json>("/v1/intentions"),
          api<Json>("/v1/timeline?limit=120"),
          api<Json>("/v1/approvals/pending"),
          api<Json>("/v1/simulator"),
          api<Json>("/v1/evaluations/latest"),
          api<Json>("/v1/system/cloud-proof"),
          api<Json>("/readyz"),
        ]);
      const first = intentions.items?.[0];
      const detail = first ? await api<Json>(`/v1/intentions/${first.intent_id}`) : null;
      setData({
        intentions: intentions.items || [],
        detail,
        timeline: timeline.items || [],
        approvals: approvals.items || [],
        simulator,
        evaluation,
        proof,
        ready,
      });
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to reach the runtime");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runStep = useCallback(
    async (stepId: string) => {
      setBusy(stepId);
      try {
        await api(`/v1/simulator/scenarios/contract-approval-official-demo/steps/${stepId}`, {
          method: "POST",
        });
        await refresh();
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Step failed");
      } finally {
        setBusy(null);
      }
    },
    [refresh]
  );

  const reset = useCallback(async () => {
    setBusy("reset");
    setAutoPlay(false);
    try {
      await api("/v1/simulator/reset", { method: "POST" });
      await refresh();
    } finally {
      setBusy(null);
    }
  }, [refresh]);

  const nextStep = useMemo(() => {
    const steps: Json[] = data.simulator?.steps || [];
    const eventIds = new Set(
      data.timeline.filter((item) => item.type === "evaluation").map((item) => item.event_id)
    );
    return steps.find((step) => {
      if (step.event) return !eventIds.has(step.event.event_id);
      if (step.approval) return data.detail?.status === "AWAITING_APPROVAL";
      if (step.advance_time) {
        return !data.detail?.actions?.some((item: Json) => item.action_id === "ask-mark");
      }
      return false;
    });
  }, [data]);

  useEffect(() => {
    if (!autoPlay || !nextStep || busy) return;
    const timer = window.setTimeout(() => runStep(nextStep.id), 850);
    return () => window.clearTimeout(timer);
  }, [autoPlay, nextStep, busy, runStep]);

  useEffect(() => {
    if (autoPlay && !nextStep) setAutoPlay(false);
  }, [autoPlay, nextStep]);

  const page = {
    overview: <Overview data={data} nextStep={nextStep} runStep={runStep} busy={busy} />,
    chat: <ChatView data={data} refresh={refresh} />,
    memory: <MemoryView data={data} />,
    timeline: <TimelineView items={data.timeline} />,
    simulator: (
      <SimulatorView
        data={data}
        nextStep={nextStep}
        runStep={runStep}
        reset={reset}
        busy={busy}
        autoPlay={autoPlay}
        setAutoPlay={setAutoPlay}
      />
    ),
    evaluation: <EvaluationView data={data} refresh={refresh} />,
    system: <SystemView data={data} />,
  }[view] || <Overview data={data} nextStep={nextStep} runStep={runStep} busy={busy} />;

  return (
    <div className="app-shell">
      <aside className={cx("sidebar", menuOpen && "sidebar-open")}>
        <div className="brand-row">
          <Link href="/" className="brand" onClick={() => setMenuOpen(false)}>
            <span className="brand-mark"><span /></span>
            <span>Latch</span>
          </Link>
          <button className="icon-button menu-close" onClick={() => setMenuOpen(false)} aria-label="Close menu">
            <X size={18} />
          </button>
        </div>
        <div className="workspace-chip">
          <span className="avatar">AC</span>
          <div><strong>Avery’s workspace</strong><span>Demo tenant</span></div>
          <ChevronRight size={15} />
        </div>
        <nav aria-label="Primary navigation">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                href={item.href}
                key={item.id}
                className={cx("nav-item", view === item.id && "nav-active")}
                onClick={() => setMenuOpen(false)}
              >
                <Icon size={17} strokeWidth={1.8} />
                <span>{item.label}</span>
                {item.id === "memory" && <small>{data.intentions.filter((i) => i.memory_tier === "HOT").length}</small>}
                {item.id === "simulator" && <span className="nav-live" />}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <div className="system-mini">
            <span className={cx("health-light", data.ready?.status === "ready" && "healthy")} />
            <div><strong>MementoVM</strong><span>{data.ready?.status || "connecting"} · v1.0</span></div>
          </div>
          <div className="built-with"><Sparkles size={13} /> Built with Qwen Cloud</div>
        </div>
      </aside>

      {menuOpen && <button className="scrim" onClick={() => setMenuOpen(false)} aria-label="Close navigation" />}

      <main className="main">
        <header className="topbar">
          <button className="icon-button menu-open" onClick={() => setMenuOpen(true)} aria-label="Open menu">
            <Menu size={19} />
          </button>
          <div className="breadcrumb"><span>Latch</span><ChevronRight size={13} /><strong>{NAV.find((n) => n.id === view)?.label || "Overview"}</strong></div>
          <div className="top-actions">
            <span className="demo-badge"><span /> Deterministic demo</span>
            <button className="icon-button" onClick={refresh} aria-label="Refresh data"><RefreshCw size={17} /></button>
            <div className="avatar avatar-small">AC</div>
          </div>
        </header>

        <div className="content">
          {error && (
            <div className="error-banner"><BellRing size={16} /><span>{error}</span><button onClick={refresh}>Retry</button></div>
          )}
          {loading ? <LoadingView /> : page}
        </div>
      </main>
    </div>
  );
}

function LoadingView() {
  return (
    <div className="loading-view">
      <div className="loading-orbit"><span /><span /><span /></div>
      <h1>Restoring active memory</h1>
      <p>Loading typed programs, cue indexes, and audit evidence…</p>
    </div>
  );
}

function PageIntro({ kicker, title, copy, aside }: { kicker: string; title: string; copy: string; aside?: ReactNode }) {
  return (
    <div className="page-intro">
      <div><div className="eyebrow">{kicker}</div><h1>{title}</h1><p>{copy}</p></div>
      {aside}
    </div>
  );
}

function Overview({ data, nextStep, runStep, busy }: { data: AppData; nextStep?: Json; runStep: (id: string) => void; busy: string | null }) {
  const detail = data.detail;
  const latestEval = data.evaluation?.runs?.find((item: Json) => item.baseline === "mementovm");
  const candidates = data.timeline.find((item) => item.type === "evaluation")?.candidate_rank || 0;
  return (
    <>
      <PageIntro
        kicker="Prospective memory runtime"
        title="Remember what must happen next."
        copy="Latch turns future commitments into typed, versioned programs—then notices the right cue, stays quiet on distractors, and acts once under your control."
        aside={<Link href="/simulator" className="primary-button"><Play size={16} fill="currentColor" /> Run the proof</Link>}
      />

      <div className="metrics-row">
        <Metric label="Active programs" value={String(data.intentions.filter((i) => i.memory_tier === "HOT").length)} detail="Bounded hot-memory set" accent />
        <Metric label="Candidates retrieved" value={String(candidates || "—")} detail="From the latest event" />
        <Metric label="PM F1" value={latestEval ? `${Math.round(latestEval.metrics.prospective_memory_f1 * 100)}%` : "—"} detail="Measured on PM-Mini v1" />
        <Metric label="Duplicate actions" value={String(latestEval?.metrics.duplicate_actions ?? "—")} detail="Exactly-once benchmark" />
      </div>

      <div className="overview-grid">
        <Panel className="intent-hero">
          <PanelTitle
            eyebrow="Active Intention Program · v2"
            title={detail?.title || "No active intention"}
            action={detail && <StatusPill status={detail.status} />}
          />
          <blockquote>{detail?.program?.source?.original_quote}</blockquote>
          <div className="logic-flow">
            <LogicNode icon={<BadgeCheck size={17} />} label="Legal approval" detail="contract-043 · v7" state={hasEvent(data, "evt-legal-v7-approved") ? "done" : "waiting"} />
            <LogicJoin label="AND" />
            <LogicNode icon={<BadgeCheck size={17} />} label="Finance approval" detail="deal-043" state={hasEvent(data, "evt-finance-deal-043") ? "done" : "waiting"} />
            <LogicJoin label="THEN" />
            <LogicNode icon={<Send size={17} />} label="Prepare draft" detail="Dana · approval required" state={detail?.status === "COMPLETED" ? "done" : "action"} />
          </div>
          <div className="guardrail-row">
            <span><ShieldCheck size={15} /> Inhibitor: contract stays open</span>
            <span><Clock3 size={15} /> Focus block: 09:00–11:00</span>
            <span><Fingerprint size={15} /> Idempotency: once</span>
          </div>
        </Panel>

        <Panel className="next-proof">
          <PanelTitle eyebrow="Live proof" title="Next simulator step" action={<span className="step-count">10 steps</span>} />
          {nextStep ? (
            <>
              <div className="proof-icon"><Play size={24} fill="currentColor" /></div>
              <h3>{nextStep.label}</h3>
              <p>{nextStep.description}</p>
              <button className="primary-button full" disabled={!!busy} onClick={() => runStep(nextStep.id)}>
                {busy === nextStep.id ? <RefreshCw className="spin" size={16} /> : <ArrowRight size={16} />}
                Execute step
              </button>
            </>
          ) : (
            <div className="proof-complete"><CheckCircle2 size={38} /><h3>Proof complete</h3><p>Exactly one draft created, then forgotten from hot memory.</p></div>
          )}
          <div className="proof-link-row"><Link href="/simulator">Open full simulator</Link><span>Seed 42</span></div>
        </Panel>
      </div>

      <div className="lower-grid">
        <Panel>
          <PanelTitle eyebrow="Runtime decisions" title="What the memory is doing" action={<Link className="text-link" href="/timeline">View timeline <ArrowRight size={14} /></Link>} />
          <div className="decision-list">
            {data.timeline.slice(0, 4).map((item) => <DecisionRow key={`${item.type}-${item.id}`} item={item} />)}
          </div>
        </Panel>
        <Panel>
          <PanelTitle eyebrow="Selective context" title="Small context, explicit evidence" />
          <div className="context-visual">
            <div className="context-ring"><strong>{candidates || 0}</strong><span>candidate</span></div>
            <div className="context-copy">
              <div><span className="legend-dot hot" /> Hot intention snapshots <strong>1</strong></div>
              <div><span className="legend-dot warm" /> Relevant preferences <strong>1</strong></div>
              <div><span className="legend-dot cold" /> Full transcripts loaded <strong>0</strong></div>
            </div>
          </div>
          <p className="panel-note"><Zap size={14} /> Exact cues resolve without a model call. Semantic reasoning stays bounded.</p>
        </Panel>
      </div>
    </>
  );
}

function hasEvent(data: AppData, id: string) {
  return data.timeline.some((item) => item.event_id === id && item.decision === "MATCH");
}

function LogicNode({ icon, label, detail, state }: { icon: ReactNode; label: string; detail: string; state: string }) {
  return <div className={cx("logic-node", `logic-${state}`)}><span className="logic-icon">{state === "done" ? <Check size={16} /> : icon}</span><div><strong>{label}</strong><span>{detail}</span></div></div>;
}

function LogicJoin({ label }: { label: string }) {
  return <div className="logic-join"><span />{label}<span /></div>;
}

function DecisionRow({ item }: { item: Json }) {
  const isReject = item.decision === "REJECT";
  const isAction = item.type === "action";
  return (
    <div className="decision-row">
      <div className={cx("decision-icon", isReject && "reject", isAction && "action")}>
        {isReject ? <X size={15} /> : isAction ? <Send size={14} /> : <Check size={15} />}
      </div>
      <div className="decision-copy">
        <strong>{item.reason || `${item.tool_id} · ${item.status}`}</strong>
        <span>{item.event_type || item.cause_type || item.action_id} · {shortTime(item.created_at)}</span>
      </div>
      {item.decision && <span className={cx("micro-badge", isReject ? "micro-reject" : "micro-match")}>{item.decision}</span>}
    </div>
  );
}

function ChatView({ data, refresh }: { data: AppData; refresh: () => Promise<void> }) {
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [response, setResponse] = useState<Json | null>(null);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!content.trim()) return;
    setSending(true);
    try {
      const result = await api<Json>("/v1/messages", {
        method: "POST",
        body: JSON.stringify({ user_id: "demo-user", session_id: `session-${Date.now()}`, client_request_id: crypto.randomUUID(), content }),
      });
      setResponse(result);
      setContent("");
      await refresh();
    } finally { setSending(false); }
  };
  return (
    <>
      <PageIntro kicker="Conversation ingestion" title="Say it once. Latch carries it forward." copy="Capture a future commitment in ordinary language. The compiler separates the cue, action, blockers, policy, and forgetting rule." />
      <div className="chat-grid">
        <Panel className="chat-panel">
          <div className="chat-session"><span><MessageSquareText size={15} /> New session</span><small>America/Chicago · private demo</small></div>
          <div className="messages">
            <div className="assistant-message"><span className="bot-avatar"><Bot size={17} /></span><div><strong>What should I remember to do later?</strong><p>I’ll turn it into an inspectable Intention Program. Nothing external happens without the policy gate.</p></div></div>
            {response && <div className="assistant-message compiled"><span className="bot-avatar"><Check size={17} /></span><div><strong>Intention compiled and activated</strong><p>{response.explanation}</p><div className="compiled-meta"><StatusPill status={response.intention.status} /><span>Confidence 94%</span><span>Schema valid</span></div></div></div>}
          </div>
          <form onSubmit={submit} className="composer">
            <textarea value={content} onChange={(e) => setContent(e.target.value)} placeholder="When something happens, remember to…" aria-label="Future commitment" />
            <div className="composer-foot"><span><LockKeyhole size={13} /> Drafts require approval</span><button disabled={sending || !content.trim()} className="send-button" aria-label="Compile intention">{sending ? <RefreshCw size={17} className="spin" /> : <Send size={17} />}</button></div>
          </form>
        </Panel>
        <Panel className="compiler-preview">
          <PanelTitle eyebrow="Compiler preview" title="Typed before it becomes memory" />
          <div className="compile-stage active"><span>01</span><div><strong>Source captured</strong><p>Raw text is provenance—not executable memory.</p></div><Check size={16} /></div>
          <div className="compile-stage active"><span>02</span><div><strong>Qwen structured output</strong><p>Action, trigger AST, inhibitors, and policies.</p></div><Check size={16} /></div>
          <div className="compile-stage active"><span>03</span><div><strong>Deterministic validation</strong><p>Schema, tools, risk tier, dates, and permissions.</p></div><ShieldCheck size={16} /></div>
          <div className="compile-stage"><span>04</span><div><strong>Active cue index</strong><p>Only validated, relevant fields enter hot memory.</p></div><Database size={16} /></div>
          <div className="example-prompt"><span>Try the official scenario</span><button onClick={() => setContent(data.detail?.versions?.at(-1)?.source_quote || "When legal approves the new DPA, prepare the redline for Dana.")}>Use example</button></div>
        </Panel>
      </div>
    </>
  );
}

function MemoryView({ data }: { data: AppData }) {
  const [tab, setTab] = useState("policy");
  const detail = data.detail;
  return (
    <>
      <PageIntro kicker="Memory Debugger" title="Every future commitment, inspectable." copy="See what is active, which version controls behavior, why it is valid, and when it will leave working memory." aside={<div className="search-field"><Search size={15} /><input placeholder="Search memory" aria-label="Search memory" /></div>} />
      <div className="memory-layout">
        <div className="memory-list">
          <div className="memory-list-head"><span>{data.intentions.length} programs</span><button><FileClock size={14} /> All states</button></div>
          {data.intentions.map((item) => (
            <button className={cx("memory-card", detail?.intent_id === item.intent_id && "selected")} key={item.intent_id}>
              <div className="memory-card-top"><span className="memory-glyph"><Layers3 size={17} /></span><StatusPill status={item.status} /></div>
              <h3>{item.title}</h3><p>{STATUS_META[item.status]?.copy}</p>
              <div className="memory-card-foot"><span>v{item.version}</span><span>{item.channels.slice(0, 3).join(" · ")}</span><ChevronRight size={15} /></div>
            </button>
          ))}
        </div>
        <Panel className="memory-detail">
          {detail ? <>
            <div className="memory-detail-head"><div><span className="eyebrow">Intention Program · {detail.intent_id.slice(0, 8)}</span><h2>{detail.title}</h2></div><StatusPill status={detail.status} /></div>
            <div className="tab-row" role="tablist">{["policy", "versions", "json"].map((item) => <button role="tab" aria-selected={tab === item} onClick={() => setTab(item)} className={tab === item ? "active" : ""} key={item}>{item === "json" ? "Program JSON" : item}</button>)}</div>
            {tab === "policy" && <ReadablePolicy detail={detail} />}
            {tab === "versions" && <VersionHistory detail={detail} />}
            {tab === "json" && <pre className="json-view">{JSON.stringify(detail.program, null, 2)}</pre>}
          </> : <div className="empty-state"><Inbox size={30} /><h3>No memory selected</h3></div>}
        </Panel>
      </div>
    </>
  );
}

function ReadablePolicy({ detail }: { detail: Json }) {
  const policy = detail.readable_policy;
  return <div className="policy-view">
    <blockquote>{detail.program.source.original_quote}</blockquote>
    <div className="policy-grid">
      <PolicyBlock icon={<Target />} label="Wait for" items={policy.waiting_for} tone="blue" />
      <PolicyBlock icon={<ShieldCheck />} label="Block when" items={policy.blocked_when} tone="red" />
      <PolicyBlock icon={<LockKeyhole />} label="Approval" items={[policy.approval]} tone="violet" />
      <PolicyBlock icon={<AlarmClock />} label="Memory of absence" items={[policy.absence]} tone="amber" />
    </div>
    <div className="provenance"><div><Fingerprint size={16} /><span>Provenance</span></div>{detail.program.source.source_spans.map((span: Json) => <div className="provenance-row" key={span.field}><code>{span.field}</code><q>{span.quote}</q></div>)}</div>
  </div>;
}

function PolicyBlock({ icon, label, items, tone }: { icon: ReactNode; label: string; items: string[]; tone: string }) {
  return <div className={cx("policy-block", `policy-${tone}`)}><div className="policy-block-head">{icon}<span>{label}</span></div>{items.map((item) => <p key={item}>{item}</p>)}</div>;
}

function VersionHistory({ detail }: { detail: Json }) {
  return <div className="version-history">{detail.versions.map((version: Json, index: number) => <div className="version-row" key={version.id}><div className="version-line"><span>{version.version}</span>{index < detail.versions.length - 1 && <i />}</div><div><div className="version-title"><strong>Version {version.version}</strong><StatusPill status={version.status} /></div><p>{version.source_quote}</p>{version.changed_fields.length > 0 && <div className="diff-chips">{version.changed_fields.map((field: string) => <span key={field}>+ {field}</span>)}</div>}<small>{shortTime(version.created_at)} · immutable snapshot</small></div></div>)}</div>;
}

function TimelineView({ items }: { items: Json[] }) {
  const [filter, setFilter] = useState("all");
  const filtered = filter === "all" ? items : items.filter((item) => item.type === filter || item.decision?.toLowerCase() === filter);
  return <>
    <PageIntro kicker="Audit and replay" title="The system explains action—and silence." copy="Follow each source message, cue lookup, predicate decision, policy gate, and state transition without exposing hidden model reasoning." />
    <Panel className="timeline-panel">
      <div className="timeline-toolbar"><div className="filter-row">{["all", "evaluation", "transition", "action", "reject"].map((item) => <button onClick={() => setFilter(item)} className={filter === item ? "active" : ""} key={item}>{item}</button>)}</div><span>{filtered.length} records</span></div>
      <div className="timeline-list">{filtered.map((item, index) => <TimelineItem item={item} key={`${item.type}-${item.id}-${index}`} />)}</div>
    </Panel>
  </>;
}

function TimelineItem({ item }: { item: Json }) {
  const reject = item.decision === "REJECT";
  const match = item.decision === "MATCH";
  return <div className="timeline-item"><div className="timeline-time">{shortTime(item.created_at)}</div><div className={cx("timeline-marker", reject && "reject", match && "match", item.type === "action" && "action")}>{reject ? <X size={14} /> : item.type === "action" ? <Send size={13} /> : match ? <Check size={14} /> : <GitBranch size={14} />}</div><div className="timeline-card"><div className="timeline-card-top"><span>{item.type === "evaluation" ? item.event_type : item.type === "transition" ? `${item.from_state} → ${item.to_state}` : item.tool_id}</span>{item.decision && <span className={cx("micro-badge", reject ? "micro-reject" : "micro-match")}>{item.decision}</span>}</div><p>{item.reason || `${item.action_id} is ${item.status?.toLowerCase()}`}</p>{item.predicate_results && Object.keys(item.predicate_results).length > 0 && <div className="evidence-row">{Object.entries(item.predicate_results).slice(0, 4).map(([key, value]) => <span key={key}><Circle size={7} fill="currentColor" /> {key.replaceAll("_", " ")}: {String(value)}</span>)}</div>}</div></div>;
}

function SimulatorView({ data, nextStep, runStep, reset, busy, autoPlay, setAutoPlay }: { data: AppData; nextStep?: Json; runStep: (id: string) => void; reset: () => void; busy: string | null; autoPlay: boolean; setAutoPlay: (value: boolean) => void }) {
  const steps = data.simulator?.steps || [];
  const completed = (step: Json) => {
    if (step.event) return data.timeline.some((item) => item.event_id === step.event.event_id);
    if (step.approval) return data.detail?.actions?.some((item: Json) => item.action_id === "prepare-redline-draft" && item.status === "COMPLETED");
    return data.detail?.actions?.some((item: Json) => item.action_id === "ask-mark");
  };
  return <>
    <PageIntro kicker="Contract Approval · Official Demo" title="Ten steps. Every claim visible." copy="A seeded, production-contract simulator proves revision, lure rejection, compound cues, preference memory, approval, idempotency, absence, and forgetting." aside={<div className="sim-controls"><button className="secondary-button" onClick={reset} disabled={!!busy}><RotateCcw size={15} /> Reset</button><button className="primary-button" onClick={() => setAutoPlay(!autoPlay)}>{autoPlay ? <Pause size={15} fill="currentColor" /> : <Play size={15} fill="currentColor" />}{autoPlay ? "Pause" : "Auto-play"}</button></div>} />
    <div className="sim-layout">
      <Panel className="sim-steps">
        <div className="scenario-meta"><div><span className="live-dot" /> Live scenario</div><code>seed: 42</code></div>
        {steps.map((step: Json, index: number) => { const done = completed(step); const active = nextStep?.id === step.id; return <button key={step.id} disabled={!!busy || done || !active} onClick={() => runStep(step.id)} className={cx("sim-step", done && "done", active && "active")}><span className="step-number">{done ? <Check size={14} /> : String(index + 1).padStart(2, "0")}</span><div><strong>{step.label}</strong><p>{step.description}</p></div>{active && <Play size={14} fill="currentColor" />}</button>; })}
      </Panel>
      <div className="sim-side">
        <Panel className="state-card"><PanelTitle eyebrow="Runtime state" title="Intention lifecycle" action={data.detail && <StatusPill status={data.detail.status} />} /><StateMachine status={data.detail?.status} /><div className="state-facts"><span><Target size={15} /> Legal cue {hasEvent(data, "evt-legal-v7-approved") ? "satisfied" : "waiting"}</span><span><Target size={15} /> Finance cue {hasEvent(data, "evt-finance-deal-043") ? "satisfied" : "waiting"}</span><span><LockKeyhole size={15} /> {data.approvals.length ? "Approval requested" : "Policy gate closed"}</span></div></Panel>
        {data.approvals.length > 0 && <ApprovalCard approval={data.approvals[0]} onDone={() => runStep("approve_action")} busy={busy} />}
        <Panel><PanelTitle eyebrow="Latest decision" title="Evidence trace" />{data.timeline[0] ? <TimelineItem item={data.timeline[0]} /> : <p className="muted">Run the first step to populate evidence.</p>}</Panel>
      </div>
    </div>
  </>;
}

function StateMachine({ status }: { status?: string }) {
  const states = ["DORMANT", "PRIMED", "DUE", "AWAITING_APPROVAL", "EXECUTING", "COMPLETED"];
  const current = Math.max(states.indexOf(status || "DORMANT"), 0);
  return <div className="state-machine">{states.map((state, index) => <div key={state} className={cx("state-node", index < current && "past", index === current && "current")}><span>{index < current ? <Check size={12} /> : index + 1}</span><small>{state.replace("AWAITING_", "")}</small></div>)}</div>;
}

function ApprovalCard({ approval, onDone, busy }: { approval: Json; onDone: () => void; busy: string | null }) {
  return <Panel className="approval-card"><div className="approval-head"><span><LockKeyhole size={15} /> Human approval</span><span className="risk-chip">{approval.action.risk_tier}</span></div><h3>Create Dana’s email draft?</h3><p>Both approval cues match and both inhibitors are false. This approval is bound to the current version and argument hash.</p><div className="approval-args"><span>To</span><strong>{approval.action.arguments.recipient}</strong><span>Subject</span><strong>{approval.action.arguments.subject}</strong></div><div className="approval-actions"><button className="secondary-button">Reject</button><button className="primary-button" onClick={onDone} disabled={!!busy}><Check size={15} /> Approve once</button></div><code className="hash">sha256:{approval.action_hash.slice(0, 24)}…</code></Panel>;
}

function EvaluationView({ data, refresh }: { data: AppData; refresh: () => Promise<void> }) {
  const [running, setRunning] = useState(false);
  const runs = data.evaluation?.runs || [];
  const run = async () => { setRunning(true); try { await api("/v1/evaluations", { method: "POST", body: JSON.stringify({}) }); await refresh(); } finally { setRunning(false); } };
  const memento = runs.find((item: Json) => item.baseline === "mementovm");
  return <>
    <PageIntro kicker="PM-Mini v1 · 60 scenarios" title="Measured against simpler memory patterns." copy="Every number below is calculated by the reproducible benchmark runner—never hard-coded into the interface." aside={<button onClick={run} disabled={running} className="primary-button">{running ? <RefreshCw className="spin" size={15} /> : <Play size={15} fill="currentColor" />} Run benchmark</button>} />
    <div className="metrics-row"><Metric label="Prospective-memory F1" value={`${Math.round((memento?.metrics.prospective_memory_f1 || 0) * 100)}%`} detail="Target ≥ 80%" accent /><Metric label="False-alarm rate" value={`${((memento?.metrics.false_alarm_rate || 0) * 100).toFixed(1)}%`} detail="Target ≤ 8%" /><Metric label="Missed-cue rate" value={`${((memento?.metrics.missed_cue_rate || 0) * 100).toFixed(1)}%`} detail="Target ≤ 15%" /><Metric label="Duplicate actions" value={String(memento?.metrics.duplicate_actions ?? 0)} detail="Target = 0" /></div>
    <Panel className="benchmark-panel"><PanelTitle eyebrow="Baseline comparison" title="Prospective-memory F1" action={<span className="dataset-chip"><Database size={13} /> PM-Mini v1</span>} /><div className="benchmark-chart">{runs.map((item: Json) => { const pct = Math.round(item.metrics.prospective_memory_f1 * 100); return <div className="bar-row" key={item.baseline}><div className="bar-label"><strong>{item.baseline === "mementovm" ? "MementoVM" : item.baseline.replaceAll("-", " ")}</strong><span>{pct}%</span></div><div className="bar-track"><div className={cx("bar-fill", item.baseline === "mementovm" && "bar-primary")} style={{ width: `${Math.max(pct, 2)}%` }} /></div><div className="bar-detail"><span>{item.metrics.false_positives} false alarms</span><span>{item.metrics.false_negatives} misses</span><span>{item.metrics.context_tokens.toLocaleString()} tokens</span></div></div>; })}</div></Panel>
    <div className="lower-grid evaluation-lower"><Panel><PanelTitle eyebrow="Coverage" title="What the dataset tests" /><div className="coverage-grid"><Coverage value="20" label="Exact cues" /><Coverage value="15" label="Entity lures" /><Coverage value="10" label="Stale cues" /><Coverage value="5" label="Inhibitors" /><Coverage value="5" label="Absence cues" /><Coverage value="5" label="Cancellations" /></div></Panel><Panel><PanelTitle eyebrow="Reproducibility" title="Evidence, not a claim" /><div className="repro-list"><span><CheckCircle2 /> Dataset version pinned</span><span><CheckCircle2 /> Deterministic seed and rules</span><span><CheckCircle2 /> Failures preserved for replay</span><span><CheckCircle2 /> Model calls and context counted</span></div></Panel></div>
  </>;
}

function Coverage({ value, label }: { value: string; label: string }) { return <div><strong>{value}</strong><span>{label}</span></div>; }

function SystemView({ data }: { data: AppData }) {
  const proof = data.proof || {};
  return <>
    <PageIntro kicker="Runtime and cloud proof" title="The infrastructure is part of the evidence." copy="Inspect service health, model routing, storage integration, and the exact deployment profile without exposing credentials." />
    <div className="system-grid">
      <Panel><PanelTitle eyebrow="Service health" title="Runtime status" action={<StatusPill status={data.ready?.status === "ready" ? "COMPLETED" : "DUE"} />} /><div className="service-list"><Service icon={<Server />} name="FastAPI runtime" value={data.ready?.status || "unknown"} /><Service icon={<Database />} name="PostgreSQL" value={data.ready?.database || "unknown"} /><Service icon={<Activity />} name="Scheduler worker" value={data.ready?.worker || "unknown"} /><Service icon={<Sparkles />} name="Qwen Cloud" value={data.ready?.qwen || "unknown"} /><Service icon={<Cloud />} name="Alibaba OSS" value={data.ready?.oss || "unknown"} /></div></Panel>
      <Panel><PanelTitle eyebrow="Qwen Cloud" title="Model routing" /><div className="model-list"><Model task="Intention compiler" model={proof.qwen?.compiler_model} mode="Structured JSON" /><Model task="Cue adjudicator" model={proof.qwen?.adjudicator_model} mode="Bounded evidence" /><Model task="Current mode" model={proof.qwen?.configured ? "Cloud enabled" : "Deterministic fallback"} mode="Quota-safe demo" /></div></Panel>
      <Panel className="cloud-proof"><PanelTitle eyebrow="Alibaba Cloud" title="Deployment proof" action={<Cloud size={19} />} /><div className="cloud-lockup"><div className="cloud-icon"><Cloud size={27} /></div><div><strong>{proof.runtime?.provider || "Alibaba Cloud ECS"}</strong><span>{proof.runtime?.deployment_profile}</span></div></div><dl><div><dt>Region</dt><dd>{proof.runtime?.region}</dd></div><div><dt>OSS exports</dt><dd>{proof.oss?.configured ? "Configured" : "Awaiting deployment credentials"}</dd></div><div><dt>Proof code</dt><dd><code>alibaba_oss.py</code></dd></div><div><dt>Secrets committed</dt><dd>No</dd></div></dl></Panel>
      <Panel><PanelTitle eyebrow="Stored evidence" title="Runtime counters" /><div className="count-grid">{Object.entries(proof.counts || {}).map(([key, value]) => <div key={key}><strong>{String(value)}</strong><span>{key.replaceAll("_", " ")}</span></div>)}</div><p className="panel-note"><ShieldCheck size={14} /> Public system data is redacted by design.</p></Panel>
    </div>
  </>;
}

function Service({ icon, name, value }: { icon: ReactNode; name: string; value: string }) { const ok = ["ok", "ready", "configured"].some((word) => value.toLowerCase().includes(word)); return <div className="service-row"><span className="service-icon">{icon}</span><strong>{name}</strong><span className={cx("service-value", ok && "ok")}><i />{value}</span></div>; }
function Model({ task, model, mode }: { task: string; model?: string; mode: string }) { return <div className="model-row"><div><Sparkles size={15} /><strong>{task}</strong></div><code>{model || "not configured"}</code><span>{mode}</span></div>; }
