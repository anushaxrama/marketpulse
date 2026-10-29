"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  Clock3,
  Code2,
  Database,
  FlaskConical,
  GitBranch,
  Layers3,
  LoaderCircle,
  Menu,
  Moon,
  Radio,
  RefreshCw,
  Search,
  ShieldCheck,
  Sun,
  Terminal,
  TriangleAlert,
  X,
  Zap,
} from "lucide-react";
import { chartPoints, completeRatio } from "../lib/chart.mjs";
import type {
  Overview,
  Bar,
  Operations,
  Run,
  Catalog,
  SymbolRow,
} from "../lib/types";
const nav = [
  ["overview", "Overview", Activity],
  ["symbols", "Symbol explorer", BarChart3],
  ["operations", "Streaming operations", Radio],
  ["lab", "Replay & reliability", FlaskConical],
  ["catalog", "Data catalog", Database],
  ["architecture", "Architecture", GitBranch],
] as const;
const names: Record<string, string> = {
  BTCUSDT: "Bitcoin",
  ETHUSDT: "Ethereum",
  SOLUSDT: "Solana",
};
const short = (s: string) => s.replace("USDT", "");
const count = (n: unknown, d = 0) =>
  n == null
    ? "Unavailable"
    : Number(n).toLocaleString("en-US", { maximumFractionDigits: d });
const price = (n: unknown) =>
  n == null
    ? "Unavailable"
    : Number(n).toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
const utc = (s: string | null | undefined) =>
  s
    ? new Date(s).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "UTC",
        hour12: false,
      }) + " UTC"
    : "Not recorded";
const percent = (n: unknown) =>
  n == null
    ? "Unavailable"
    : `${Number(n) >= 0 ? "+" : ""}${Number(n).toFixed(2)}%`;
async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch("/api/" + path, { signal, cache: "no-store" });
  const body = await r.json();
  if (!r.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${r.status}). Check the selected parameters.`,
    );
  return body;
}
function Badge({
  children,
  tone = "muted",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return (
    <span className={"badge " + tone}>
      <i />
      {children}
    </span>
  );
}
function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="empty">
      <Database size={24} />
      <p>{children}</p>
    </div>
  );
}
function Metric({
  label,
  value,
  note,
  icon: Icon,
  tone = "",
}: {
  label: string;
  value: React.ReactNode;
  note: string;
  icon: typeof Activity;
  tone?: string;
}) {
  return (
    <article className={"metric " + tone}>
      <div className="metric-label">
        {label}
        <Icon size={15} />
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-note">{note}</div>
    </article>
  );
}
function Section({
  title,
  note,
  children,
  action,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>{title}</h2>
          {note && <p>{note}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
function Sparkline({ bars }: { bars: Bar[] }) {
  const p = chartPoints(
    bars.map((b) => Number(b.close)),
    130,
    35,
    2,
  );
  return (
    <svg
      viewBox="0 0 130 35"
      className="sparkline"
      role="img"
      aria-label="Observed closing price trend"
    >
      <path d={p.path} fill="none" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  );
}
function PriceChart({ bars, symbol }: { bars: Bar[]; symbol: string }) {
  const [point, setPoint] = useState<number | null>(null);
  const [ma, setMa] = useState(false);
  const id = symbol.toLowerCase();
  if (!bars.length) return <Empty>No bars match this selection.</Empty>;
  const p = chartPoints(
    bars.map((b) => Number(b.close)),
    900,
    260,
    20,
  );
  const safePoint = point === null ? null : Math.min(point, bars.length - 1);
  const last = bars[safePoint ?? bars.length - 1];
  const x = (i: number) => 20 + (i / Math.max(bars.length - 1, 1)) * 860;
  const y = (v: number) => 20 + ((p.max - v) / (p.max - p.min)) * 220;
  const maPath = bars
    .map((b, i) =>
      b.moving_average_20
        ? `${i && bars[i - 1].moving_average_20 ? "L" : "M"}${x(i)},${y(Number(b.moving_average_20))}`
        : "",
    )
    .join(" ");
  const indices = [
    ...new Set([
      0,
      Math.floor((bars.length - 1) / 3),
      Math.floor((2 * (bars.length - 1)) / 3),
      bars.length - 1,
    ]),
  ];
  const chunks = Array.from({ length: Math.min(90, bars.length) }, (_, i) => {
    const start = Math.floor((i * bars.length) / Math.min(90, bars.length));
    const end = Math.floor(((i + 1) * bars.length) / Math.min(90, bars.length));
    const items = bars.slice(start, end);
    return {
      volume: items.reduce((s, b) => s + Number(b.volume), 0),
      up: Number(items.at(-1)?.close) >= Number(items[0]?.open),
    };
  });
  const maxVol = Math.max(...chunks.map((c) => c.volume), 1);
  return (
    <div className="chart-block">
      <div className="price-readout">
        <div>
          <span className="asset-letter">{short(symbol).slice(0, 1)}</span>
          <div>
            <span>
              {names[symbol]} <b>{short(symbol)} / USDT</b>
            </span>
            <strong>
              {price(last.close)} <small>USDT</small>
            </strong>
          </div>
        </div>
        <div className="chart-legend">
          <span>
            <i />
            1-minute close
          </span>
          <button
            className={ma ? "selected" : ""}
            aria-pressed={ma}
            onClick={() => setMa(!ma)}
          >
            <i className="ma-dot" />
            20-bar average
          </button>
        </div>
      </div>
      <div className="chart-inspection" aria-live="polite">
        {utc(last.event_time)}{" "}
        <span>
          O {price(last.open)} <b>H {price(last.high)}</b> L {price(last.low)}
        </span>
      </div>
      <div className="price-plot">
        <svg
          viewBox="0 0 960 300"
          role="img"
          aria-label={`${symbol} historical one-minute close price chart`}
        >
          <defs>
            <linearGradient id={"fill-" + id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--lime)" stopOpacity=".16" />
              <stop offset="100%" stopColor="var(--lime)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[0, 1, 2, 3, 4].map((i) => {
            const v = p.min + ((p.max - p.min) * i) / 4;
            return (
              <g key={i}>
                <line
                  x1="20"
                  x2="880"
                  y1={y(v)}
                  y2={y(v)}
                  className="chart-grid"
                />
                <text x="900" y={y(v) + 4}>
                  {price(v)}
                </text>
              </g>
            );
          })}
          <path d={p.path + ` L880,260 L20,260Z`} fill={`url(#fill-${id})`} />
          <path d={p.path} fill="none" stroke="var(--lime)" strokeWidth="1.8" />
          {ma && (
            <path
              d={maPath}
              fill="none"
              stroke="var(--blue)"
              strokeWidth="1.5"
            />
          )}
          {bars
            .filter(
              (b) =>
                b.anomaly_score && Math.abs(Number(b.anomaly_score)) >= 3.5,
            )
            .map((b) => {
              const i = bars.indexOf(b);
              return (
                <circle
                  key={b.event_id}
                  cx={x(i)}
                  cy={y(Number(b.close))}
                  r="3"
                  className="anomaly-dot"
                >
                  <title>Exploratory return flag · {utc(b.event_time)}</title>
                </circle>
              );
            })}
          {safePoint !== null && (
            <g>
              <line
                x1={x(safePoint)}
                x2={x(safePoint)}
                y1="20"
                y2="260"
                className="crosshair"
              />
              <circle
                cx={x(safePoint)}
                cy={y(Number(last.close))}
                r="4"
                fill="var(--lime)"
              />
            </g>
          )}
          {indices.map((i) => (
            <text
              key={i}
              x={x(i)}
              y="290"
              textAnchor={i === bars.length - 1 ? "end" : "start"}
            >
              {new Date(bars[i].event_time).toLocaleTimeString("en-US", {
                hour: "2-digit",
                minute: "2-digit",
                hour12: false,
                timeZone: "UTC",
              })}
            </text>
          ))}
          <rect
            x="20"
            y="15"
            width="860"
            height="250"
            fill="transparent"
            onPointerMove={(e) => {
              const box = e.currentTarget.getBoundingClientRect();
              setPoint(
                Math.min(
                  bars.length - 1,
                  Math.max(
                    0,
                    Math.round(
                      ((e.clientX - box.left) / box.width) * (bars.length - 1),
                    ),
                  ),
                ),
              );
            }}
            onPointerLeave={() => setPoint(null)}
          />
        </svg>
      </div>
      <label className="chart-slider">
        Inspect bar{" "}
        <input
          type="range"
          min="0"
          max={bars.length - 1}
          value={safePoint ?? bars.length - 1}
          onChange={(e) => setPoint(Number(e.target.value))}
          aria-label="Inspect historical price bar"
        />
        <span>
          {safePoint === null
            ? "Use arrow keys or hover"
            : `${(safePoint ?? 0) + 1} / ${bars.length}`}
        </span>
      </label>
      <div className="volume-heading">
        <span>
          EXECUTED BAR VOLUME <b>{short(symbol)} units</b>
        </span>
        <span>Bars combined for display</span>
      </div>
      <svg
        className="volume-chart"
        viewBox="0 0 960 64"
        role="img"
        aria-label={`${short(symbol)} executed base-asset volume`}
      >
        {chunks.map((c, i) => (
          <rect
            key={i}
            x={20 + (i * 860) / chunks.length}
            y={58 - (c.volume / maxVol) * 48}
            width={Math.max(1, 860 / chunks.length - 3)}
            height={(c.volume / maxVol) * 48}
            fill={c.up ? "var(--volume-up)" : "var(--volume-down)"}
            rx="1"
          />
        ))}
      </svg>
      <div className="chart-foot">
        <span>
          <i />
          Binance Vision · historical replay
        </span>
        <span>Exploratory flags are not trading signals</span>
      </div>
    </div>
  );
}
function Pipeline({
  overview,
  ops,
  onNavigate,
}: {
  overview: Overview;
  ops: Operations | null;
  onNavigate: (s: string) => void;
}) {
  const run = overview.run;
  const r = run?.result;
  const steps = [
    ["Source archive", "SHA-256 verified · 1m OHLCV", Database],
    ["Kafka transport", `${count(r?.delivered)} raw deliveries`, Radio],
    [
      "Spark event time",
      `${run?.window_minutes ?? 5}m windows · ${run?.watermark_minutes ?? 10}m watermark`,
      Zap,
    ],
    ["Local warehouse", `${count(r?.windows)} observed windows`, Layers3],
  ] as const;
  const ratio =
    r?.accepted && r?.expected_unique
      ? completeRatio(r.accepted, r.expected_unique)
      : null;
  return (
    <Section
      title="Pipeline health"
      note="The context behind every data point"
      action={
        <Badge tone={r?.reconciled ? "green" : "muted"}>
          {r?.reconciled ? "Reconciled" : "Pending"}
        </Badge>
      }
    >
      <div className="pipeline-steps">
        {steps.map(([title, note, Icon], i) => (
          <div className="pipeline-step" key={title}>
            <span className="step-icon">
              <Icon size={17} />
            </span>
            <div>
              <strong>{title}</strong>
              <small>{note}</small>
            </div>
            {r?.reconciled ? (
              <Check size={14} className="good" />
            ) : (
              <Clock3 size={14} />
            )}
          </div>
        ))}
      </div>
      <div className="completion">
        <div>
          <span>Curated completeness</span>
          <strong>
            {ratio === null ? "Unavailable" : ratio.toFixed(0) + "%"}
          </strong>
        </div>
        <div className="progress-track">
          <i style={{ width: (ratio ?? 0) + "%" }} />
        </div>
        <small>
          {count(r?.accepted)} / {count(r?.expected_unique)} expected unique
          bars
        </small>
      </div>
      <div className="optional-note">
        <Database size={14} />
        <div>
          <strong>Snowflake connector</strong>
          <small>Optional path · account execution unverified</small>
        </div>
        <span className="tiny-tag">OPTIONAL</span>
      </div>
      <button className="text-link" onClick={() => onNavigate("operations")}>
        Inspect streaming operations <ArrowUpRight size={13} />
      </button>
    </Section>
  );
}
export default function Dashboard() {
  const [page, setPage] = useState("overview");
  const [theme, setTheme] = useState("dark");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [ops, setOps] = useState<Operations | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [series, setSeries] = useState<Record<string, Bar[]>>({});
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [hours, setHours] = useState(24);
  const [runId, setRunId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [search, setSearch] = useState("");
  const [menu, setMenu] = useState(false);
  const title = nav.find((n) => n[0] === page)?.[1] || "Overview";
  const navigate = useCallback((next: string) => {
    setPage(next);
    location.hash = next;
    setMenu(false);
    window.scrollTo({ top: 0 });
  }, []);
  useEffect(() => {
    const change = () => {
      const hash = location.hash.slice(1);
      setPage(nav.some((n) => n[0] === hash) ? hash : "overview");
    };
    change();
    window.addEventListener("hashchange", change);
    const stored = localStorage.getItem("marketpulse-theme");
    if (stored === "light") setTheme("light");
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("marketpulse-theme", theme);
  }, [theme]);
  useEffect(() => {
    const c = new AbortController();
    setLoading(true);
    setError("");
    const suffix = runId ? "?run_id=" + runId : "";
    (async () => {
      try {
        const [o, r, cat] = await Promise.all([
          api<Overview>("overview" + suffix, c.signal),
          api<Run[]>("runs?limit=30", c.signal),
          api<Catalog>("catalog", c.signal),
        ]);
        setOverview(o);
        setRuns(r);
        setCatalog(cat);
        if (o.run) {
          const id = o.run.id;
          const [op, ...bars] = await Promise.all([
            api<Operations>("operations?run_id=" + id, c.signal),
            ...["BTCUSDT", "ETHUSDT", "SOLUSDT"].map((s) =>
              api<Bar[]>(
                `series?run_id=${id}&symbol=${s}&hours=${hours}`,
                c.signal,
              ),
            ),
          ]);
          setOps(op);
          setSeries(
            Object.fromEntries(
              ["BTCUSDT", "ETHUSDT", "SOLUSDT"].map((s, i) => [
                s,
                bars[i] as Bar[],
              ]),
            ),
          );
        }
      } catch (e) {
        if (!c.signal.aborted)
          setError(e instanceof Error ? e.message : "Request failed");
      } finally {
        if (!c.signal.aborted) setLoading(false);
      }
    })();
    return () => c.abort();
  }, [runId, hours, refresh]);
  useEffect(() => {
    const timer = setInterval(() => setRefresh((n) => n + 1), 15000);
    return () => clearInterval(timer);
  }, []);
  const pick = (s: string) => {
    setSymbol(s);
    setSearch("");
    navigate("symbols");
  };
  const bars = series[symbol] || [];
  const result = overview?.run?.result;
  const active = overview?.run;
  const filteredSymbols = (overview?.symbols || []).filter((s) =>
    (s.symbol + " " + names[s.symbol])
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const subtitles: Record<string, string> = {
    overview: "Market movement and data reliability, in the same view.",
    symbols: "Follow observed bars, returns, and the gaps between them.",
    operations: "Inspect what moved through the pipeline, and what did not.",
    lab: "Replay the same market day. Change the delivery conditions.",
    catalog: "Trace the data from its source archive to its serving model.",
    architecture: "A small streaming system with explicit failure boundaries.",
  };
  function exportCSV() {
    const body = [
      "event_time_utc,symbol,open,high,low,close,base_volume",
      ...bars.map((b) =>
        [b.event_time, symbol, b.open, b.high, b.low, b.close, b.volume].join(
          ",",
        ),
      ),
    ].join("\r\n");
    const url = URL.createObjectURL(new Blob([body], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `marketpulse-${symbol}-${hours}h-historical.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <>
      <a className="skip" href="#main">
        Skip to dashboard
      </a>
      <aside className={"sidebar " + (menu ? "open" : "")}>
        <a
          href="#overview"
          className="brand"
          onClick={() => navigate("overview")}
        >
          <span className="brandmark">
            <Activity size={23} />
          </span>
          Market<span>Pulse</span>
          <small>MP</small>
        </a>
        <div className="workspace">
          <span className="workspace-symbol">
            <Layers3 size={17} />
          </span>
          <div>
            Market intelligence<small>Local development workspace</small>
          </div>
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {nav.map(([key, label, Icon], i) => (
            <a
              href={"#" + key}
              key={key}
              className={page === key ? "active" : ""}
              aria-current={page === key ? "page" : undefined}
              onClick={() => navigate(key)}
            >
              <Icon size={17} />
              <span>{label}</span>
              {key === "lab" ? (
                <span className="nav-lab">LAB</span>
              ) : page === key ? (
                <ChevronRight size={13} />
              ) : null}
            </a>
          ))}
        </nav>
        <div className="rail-card">
          <div>
            <ShieldCheck size={16} />
            <span>RELIABILITY FIRST</span>
          </div>
          <strong>
            A price is only as useful
            <br />
            as the data behind it.
          </strong>
          <p>
            Provenance, event time, and replay behavior are part of the product.
          </p>
          <button onClick={() => navigate("architecture")}>
            How it works <ArrowUpRight size={13} />
          </button>
        </div>
        <div className="rail-footer">
          <span className="small-dot" />
          Historical replay environment
          <button
            aria-label={
              "Switch to " + (theme === "dark" ? "light" : "dark") + " theme"
            }
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </aside>
      <div className="app">
        <header>
          <div className="breadcrumb">
            <button
              className="mobile-menu"
              aria-label="Open navigation"
              aria-expanded={menu}
              onClick={() => setMenu(!menu)}
            >
              <Menu size={19} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={12} />
            <strong>{title}</strong>
          </div>
          <div className="header-actions">
            <span className="environment">
              <i />
              LOCAL
            </span>
            <a
              href="http://127.0.0.1:8030/docs"
              target="_blank"
              rel="noopener"
              aria-label="Open API documentation"
            >
              <Code2 size={16} />
            </a>
            <button
              aria-label="Refresh warehouse data"
              onClick={() => setRefresh((n) => n + 1)}
            >
              <RefreshCw size={15} className={loading ? "spin" : ""} />
            </button>
            <span className="avatar">AR</span>
          </div>
        </header>
        <main id="main">
          <div className="page-title">
            <div className="eyebrow">
              MARKET INTELLIGENCE /{" "}
              {page === "lab"
                ? "CONTROLLED EXPERIMENTS"
                : "OBSERVE & UNDERSTAND"}
            </div>
            <div className="title-row">
              <div>
                <h1>{title === "Overview" ? "Market overview" : title}</h1>
                <p>{subtitles[page]}</p>
              </div>
              <Badge tone="amber">Historical replay</Badge>
            </div>
          </div>
          <div className="dataset-toolbar">
            <div className="dataset-name">
              <Database size={14} />
              <span>
                {overview?.dataset?.day || "Preparing dataset"}
                <small>1-minute spot bars · USDT quoted</small>
              </span>
              <ChevronDown size={12} />
            </div>
            <label className="run-select">
              Replay run
              <select
                aria-label="Replay run"
                value={runId || active?.id || ""}
                onChange={(e) => setRunId(e.target.value)}
              >
                <option value="">Latest baseline</option>
                {runs
                  .filter((r) => r.status === "completed")
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.scenario} · {r.window_minutes}m/{r.watermark_minutes}m
                      · {r.id.slice(0, 6)}
                    </option>
                  ))}
              </select>
            </label>
            <span className="dataset-update">
              <Clock3 size={13} />
              {active?.finished_at
                ? "Processed " + utc(active.finished_at)
                : "Waiting for completed replay"}
            </span>
          </div>
          {error ? (
            <div className="error" role="alert">
              <TriangleAlert size={20} />
              <div>
                <strong>This view could not be loaded</strong>
                <p>{error}</p>
              </div>
              <button onClick={() => setRefresh((n) => n + 1)}>
                Try again
              </button>
            </div>
          ) : null}
          {loading && !overview ? (
            <div className="loading" role="status">
              <LoaderCircle className="spin" />
              Connecting to the local warehouse…
            </div>
          ) : null}
          {overview && !error && (
            <div
              className={loading ? "view refreshing" : "view"}
              aria-busy={loading}
            >
              {(page === "overview" || page === "symbols") && (
                <>
                  <div className="metrics-grid">
                    <Metric
                      label="Tracked symbols"
                      value={count(overview.symbols.length)}
                      note="BTC, ETH, SOL · Binance spot"
                      icon={Layers3}
                    />
                    <Metric
                      label="Curated bars"
                      value={count(result?.accepted)}
                      note={`${count(result?.expected_unique)} expected from source archives`}
                      icon={BarChart3}
                      tone="featured"
                    />
                    <Metric
                      label="Window coverage"
                      value={
                        result?.accepted
                          ? (
                              ((result.window_bars ?? 0) / result.accepted) *
                              100
                            ).toFixed(1) + "%"
                          : "Unavailable"
                      }
                      note="Curated bars represented in Spark windows"
                      icon={ShieldCheck}
                    />
                    <Metric
                      label="Late to watermark"
                      value={count(result?.late_dropped_from_windows)}
                      note="Retained in facts; excluded from stream windows"
                      icon={Clock3}
                    />
                  </div>
                  <div className="overview-grid">
                    <Section
                      title={
                        page === "symbols"
                          ? "Symbol explorer"
                          : "Price & volume"
                      }
                      note="Observed closing prices. Source time is historical."
                      action={
                        <button
                          className="icon-button"
                          aria-label="Export selected bars"
                          onClick={exportCSV}
                          disabled={!bars.length}
                        >
                          <ArrowDownToLine size={15} />
                        </button>
                      }
                    >
                      <div className="chart-controls">
                        <div className="asset-tabs" aria-label="Select symbol">
                          {["BTCUSDT", "ETHUSDT", "SOLUSDT"].map((s) => (
                            <button
                              key={s}
                              aria-pressed={symbol === s}
                              className={symbol === s ? "selected" : ""}
                              onClick={() => setSymbol(s)}
                            >
                              {short(s)}
                              <span>/ USDT</span>
                            </button>
                          ))}
                        </div>
                        <div
                          className="time-tabs"
                          aria-label="Chart time range"
                        >
                          {[1, 6, 24].map((h) => (
                            <button
                              key={h}
                              aria-pressed={hours === h}
                              className={hours === h ? "selected" : ""}
                              onClick={() => {
                                if (h !== hours) {
                                  setLoading(true);
                                  setHours(h);
                                }
                              }}
                            >
                              {h}H
                            </button>
                          ))}
                        </div>
                      </div>
                      <PriceChart bars={bars} symbol={symbol} />
                    </Section>
                    {page === "overview" ? (
                      <Pipeline
                        overview={overview}
                        ops={ops}
                        onNavigate={navigate}
                      />
                    ) : (
                      <Section
                        title="Reading this symbol"
                        note="Definitions are part of the result"
                      >
                        <div className="method-list">
                          <div>
                            <span>RETURN</span>
                            <p>
                              Log return between adjacent one-minute closes.
                              Gaps are not filled.
                            </p>
                          </div>
                          <div>
                            <span>VOLATILITY</span>
                            <p>
                              Unannualized standard deviation in a contiguous
                              20-bar window.
                            </p>
                          </div>
                          <div>
                            <span>ANOMALIES</span>
                            <p>
                              Absolute z-score of at least 3.5 against 20
                              preceding returns. Exploratory flags only.
                            </p>
                          </div>
                          <div>
                            <span>SESSION</span>
                            <p>
                              Crypto spot trades 24/7. This dataset does not use
                              an equity exchange calendar.
                            </p>
                          </div>
                        </div>
                      </Section>
                    )}
                  </div>
                  {page === "symbols" && (
                    <Section
                      title="Exploratory return flags"
                      note="Sparse history and multiple comparisons can produce false positives."
                    >
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>UTC bar time</th>
                              <th>Close · USDT</th>
                              <th>Log return</th>
                              <th>Prior-baseline z-score</th>
                            </tr>
                          </thead>
                          <tbody>
                            {bars
                              .filter(
                                (b) =>
                                  b.anomaly_score &&
                                  Math.abs(Number(b.anomaly_score)) >= 3.5,
                              )
                              .slice(0, 20)
                              .map((b) => (
                                <tr key={b.event_id}>
                                  <td>{utc(b.event_time)}</td>
                                  <td>{price(b.close)}</td>
                                  <td>{Number(b.log_return).toFixed(6)}</td>
                                  <td>{Number(b.anomaly_score).toFixed(2)}</td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                        {!bars.some(
                          (b) =>
                            b.anomaly_score &&
                            Math.abs(Number(b.anomaly_score)) >= 3.5,
                        ) && <Empty>No flags in this selected interval.</Empty>}
                      </div>
                    </Section>
                  )}
                  <Section
                    title="Tracked markets"
                    note="Captured source-day context. Returns compare the first and last observed close."
                    action={
                      <label className="symbol-search">
                        <Search size={14} />
                        <input
                          placeholder="Find a symbol…"
                          aria-label="Find a symbol"
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                        />
                      </label>
                    }
                  >
                    <div className="table-wrap">
                      <table className="market-table">
                        <thead>
                          <tr>
                            <th>Asset / market</th>
                            <th>Last close · USDT</th>
                            <th>Observed return</th>
                            <th>Base-asset volume</th>
                            <th>Bars</th>
                            <th>Price trend</th>
                            <th>Source</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredSymbols.map((s) => (
                            <tr key={s.symbol}>
                              <td>
                                <button
                                  className="asset-link"
                                  onClick={() => pick(s.symbol)}
                                >
                                  <span
                                    className={
                                      "coin " + short(s.symbol).toLowerCase()
                                    }
                                  >
                                    {short(s.symbol).slice(0, 1)}
                                  </span>
                                  <span>
                                    <strong>{names[s.symbol]}</strong>
                                    <small>{short(s.symbol)} / USDT</small>
                                  </span>
                                </button>
                              </td>
                              <td>{price(s.last_close)}</td>
                              <td
                                className={
                                  Number(s.return_pct) >= 0
                                    ? "positive"
                                    : "negative"
                                }
                              >
                                {percent(s.return_pct)}
                              </td>
                              <td>
                                {count(s.base_volume, 2)}{" "}
                                <small>{short(s.symbol)}</small>
                              </td>
                              <td>{count(s.bars)}</td>
                              <td>
                                <Sparkline bars={series[s.symbol] || []} />
                              </td>
                              <td>
                                <Badge>Replay</Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {filteredSymbols.length === 0 && (
                        <Empty>No symbols match this search.</Empty>
                      )}
                    </div>
                  </Section>
                </>
              )}
              {page === "operations" && <OperationsView ops={ops} />}{" "}
              {page === "lab" && (
                <Lab
                  catalog={catalog}
                  runs={runs}
                  onRefresh={() => setRefresh((n) => n + 1)}
                  onSelect={(id) => {
                    setRunId(id);
                    navigate("operations");
                  }}
                />
              )}
              {page === "catalog" && <CatalogView catalog={catalog} />}{" "}
              {page === "architecture" && <Architecture />}
              <div className="source-disclosure">
                <ShieldCheck size={14} />
                <p>
                  Historical one-minute bars from Binance Vision. USDT is not a
                  USD conversion. Recently processed data is not a live exchange
                  feed. No orders or investment recommendations.
                </p>
                <button onClick={() => navigate("catalog")}>
                  Source & methodology <ArrowUpRight size={12} />
                </button>
              </div>
            </div>
          )}
          <footer>
            <div>
              <span className="footer-brand">
                MarketPulse<span>.</span>
              </span>
              <span>Market data, with context.</span>
            </div>
            <div>
              <a
                href="https://github.com/binance/binance-public-data"
                target="_blank"
                rel="noopener"
              >
                Source documentation <ArrowUpRight size={11} />
              </a>
              <span>Non-commercial research · CC BY-NC-SA 4.0</span>
            </div>
          </footer>
        </main>
      </div>
    </>
  );
}
function OperationsView({ ops }: { ops: Operations | null }) {
  if (!ops?.run) return <Empty>No completed stream execution yet.</Empty>;
  const r = ops.run.result;
  const ps = ops.progress.filter((p) => p.stage === "windows");
  return (
    <>
      <div className="metrics-grid">
        <Metric
          label="Raw deliveries"
          value={count(r.delivered)}
          note="Audited Kafka records for this replay"
          icon={Radio}
        />
        <Metric
          label="Duplicate deliveries"
          value={count(r.duplicates)}
          note="Suppressed by durable event identity"
          icon={Layers3}
        />
        <Metric
          label="Invalid / conflict"
          value={count((r.invalid ?? 0) + (r.conflicts ?? 0))}
          note="Quarantined with dead-letter outbox records"
          icon={TriangleAlert}
        />
        <Metric
          label="p95 curation delay"
          value={
            r.lag_p95_seconds == null
              ? "Unavailable"
              : r.lag_p95_seconds.toFixed(2) + "s"
          }
          note="Ingestion timestamp to PostgreSQL fact commit"
          icon={Clock3}
        />
      </div>
      <div className="overview-grid">
        <Section
          title="Spark micro-batches"
          note="Measured window-query processing rate. Includes local execution overhead."
        >
          <div className="batch-chart">
            {ps.map((p) => (
              <div key={p.batch_id}>
                <span>{count(p.processed_rate, 1)} /s</span>
                <i
                  style={{
                    height: Math.max(
                      3,
                      (p.processed_rate /
                        Math.max(...ps.map((x) => x.processed_rate), 1)) *
                        150,
                    ),
                  }}
                />
                <small>#{p.batch_id}</small>
              </div>
            ))}
          </div>
          <div className="chart-foot">
            <span>{ps.length} recorded window-query batches</span>
            <span>Actual Spark progress events</span>
          </div>
        </Section>
        <Section
          title="Reconciliation"
          note="Keep delivery counts separate from unique market bars."
        >
          <dl className="ledger">
            {[
              ["Expected unique", r.expected_unique],
              ["Curated unique", r.accepted],
              ["In stream windows", r.window_bars],
              ["Late window drops", r.late_dropped_from_windows],
              ["Pending outbox", ops.outbox_pending],
            ].map(([k, v]) => (
              <div key={k as string}>
                <dt>{k}</dt>
                <dd>{count(v)}</dd>
              </div>
            ))}
          </dl>
          <div className="reconciled">
            <CheckCheck size={16} />
            {r.reconciled
              ? "Expected and observed counts reconcile"
              : "Reconciliation unavailable"}
          </div>
          <p className="caption">
            Curated bars = window bars + measured watermark drops. Late records
            remain auditable.
          </p>
        </Section>
      </div>
      <Section
        title="Event-time & checkpoint ledger"
        note="Watermarks are historical UTC event-time boundaries, not wall-clock freshness."
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Stage</th>
                <th>Batch</th>
                <th>Input rows</th>
                <th>Dropped by watermark</th>
                <th>Observed watermark</th>
                <th>Trigger time</th>
              </tr>
            </thead>
            <tbody>
              {ops.progress.map((p) => (
                <tr key={p.stage + p.batch_id}>
                  <td>{p.stage}</td>
                  <td>{p.batch_id}</td>
                  <td>{count(p.input_rows)}</td>
                  <td>{count(p.dropped_by_watermark)}</td>
                  <td>{p.watermark ? utc(p.watermark) : "Not applicable"}</td>
                  <td>{count(p.duration_ms)} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      {ops.quality.length > 0 && (
        <Section
          title="Quarantined deliveries"
          note="Rejected messages do not become prices or volume."
        >
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Count</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {ops.quality.map((q, i) => (
                  <tr key={i}>
                    <td>{q.status}</td>
                    <td>{q.count}</td>
                    <td className="wrap-cell">{q.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </>
  );
}
function Lab({
  catalog,
  runs,
  onRefresh,
  onSelect,
}: {
  catalog: Catalog | null;
  runs: Run[];
  onRefresh: () => void;
  onSelect: (id: string) => void;
}) {
  const [scenario, setScenario] = useState("duplicate");
  const [window, setWindow] = useState(5);
  const [watermark, setWatermark] = useState(10);
  const [speed, setSpeed] = useState(0);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const completed = runs.filter((r) => r.status === "completed");
  const first =
    completed.find((r) => r.id === a) ||
    completed.find((r) => r.scenario === "baseline");
  const second =
    completed.find((r) => r.id === b) ||
    completed.find((r) => r.scenario !== "baseline");
  const descriptions: Record<string, string> = {
    baseline: "Publish source bars in chronological order.",
    duplicate:
      "Deliver an extra copy of every 100th event. The raw ledger should show duplicates; curated identity counts should stay stable.",
    late: "Hold the first bar of each symbol until the end. Spark should exclude them from closed windows while the audit retains them.",
    reorder:
      "Shuffle each three-minute block with seed 42. Events stay within the default watermark tolerance.",
    outage:
      "Pause the local producer for one second before delivery. This is controlled producer unavailability, not a claimed upstream outage.",
    restart:
      "Interrupt the first window sink acknowledgement after its database commit, then restart from the same Spark checkpoint.",
    warehouse_retry:
      "Repeat a committed window batch after an injected acknowledgement failure. The transactional batch ledger should prevent double writes.",
    poison:
      "Append an invalid schema/price envelope labeled synthetic test. It must be isolated from all financial metrics.",
  };
  async function launch() {
    setBusy(true);
    setMessage("");
    try {
      const r = await fetch("/api/lab/replays", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dataset_id: catalog?.datasets[0]?.id,
          scenario,
          window_minutes: window,
          watermark_minutes: watermark,
          speed,
        }),
      });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail);
      setMessage(
        "Queued replay " +
          body.run_id.slice(0, 8) +
          ". The ledger below will show its actual outcome.",
      );
      dialog.current?.close();
      onRefresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Replay could not start");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="lab-banner">
        <FlaskConical size={21} />
        <div>
          <strong>Same source data. Different delivery conditions.</strong>
          <p>
            Deterministic replay identity · isolated checkpoints · bounded local
            experiments
          </p>
        </div>
        <Badge tone="blue">LOCAL LAB</Badge>
      </div>
      <div className="overview-grid">
        <Section
          title="Configure a replay"
          note="Faults change delivery behavior, never the historical price payload."
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setConfirm(false);
              dialog.current?.showModal();
            }}
            className="lab-form"
          >
            <label>
              Historical dataset
              <select
                aria-label="Historical dataset"
                disabled={!catalog?.datasets.length}
              >
                {catalog?.datasets.map((d) => (
                  <option key={d.id}>
                    {d.day} · 3 symbols · {d.events} one-minute bars
                  </option>
                ))}
              </select>
            </label>
            <label>
              Delivery scenario
              <select
                aria-label="Delivery scenario"
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
              >
                {(catalog?.scenarios || []).map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <p className="scenario-help">{descriptions[scenario]}</p>
            <div className="form-pair">
              <label>
                Aggregation window
                <select
                  value={window}
                  onChange={(e) => setWindow(Number(e.target.value))}
                >
                  {[1, 5, 15].map((v) => (
                    <option key={v} value={v}>
                      {v} minutes
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Watermark tolerance
                <select
                  value={watermark}
                  onChange={(e) => setWatermark(Number(e.target.value))}
                >
                  {[2, 10, 30].map((v) => (
                    <option key={v} value={v}>
                      {v} minutes
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Publish speed
              <select
                value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))}
              >
                {[0, 100, 500, 1000].map((v) => (
                  <option key={v} value={v}>
                    {v === 0
                      ? "As fast as the local producer permits"
                      : v + " messages / second"}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="primary"
              disabled={
                !catalog?.lab_enabled || !catalog.datasets.length || busy
              }
            >
              Review replay <ArrowRight size={15} />
            </button>
            {!catalog?.lab_enabled && (
              <p className="caption">
                Lab launch is disabled. Enable MP_LAB_ENABLED=true for the local
                Compose demo.
              </p>
            )}
          </form>
          {message && (
            <p role="status" className="action-message">
              {message}
            </p>
          )}
        </Section>
        <Section
          title="Compare observed runs"
          note="Reproducibility is checked against the same source identities."
        >
          <div className="form-pair compare-selects">
            {[
              [a, setA, "First run"],
              [b, setB, "Second run"],
            ].map(([v, set, label]) => (
              <label key={label as string}>
                {label as string}
                <select
                  aria-label={label as string}
                  value={v as string}
                  onChange={(e) => (set as (v: string) => void)(e.target.value)}
                >
                  <option value="">Suggested run</option>
                  {completed.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.scenario} · {r.id.slice(0, 6)}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          {first && second ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Measure</th>
                    <th>{first.scenario}</th>
                    <th>{second.scenario}</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["Expected unique", "expected_unique"],
                    ["Accepted unique", "accepted"],
                    ["Duplicates", "duplicates"],
                    ["Invalid", "invalid"],
                    ["Late in windows", "late_dropped_from_windows"],
                    ["Window bars", "window_bars"],
                  ].map(([label, key]) => (
                    <tr key={key}>
                      <td>{label}</td>
                      <td>
                        {count(first.result[key as keyof typeof first.result])}
                      </td>
                      <td>
                        {count(
                          second.result[key as keyof typeof second.result],
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="comparison-result">
                <ShieldCheck size={16} />
                {first.result.event_id_fingerprint ===
                second.result.event_id_fingerprint
                  ? "Curated event identities match"
                  : "Event identities differ; inspect the run evidence"}
              </div>
            </div>
          ) : (
            <Empty>
              Complete a baseline and another scenario to compare measured
              results.
            </Empty>
          )}
          <p className="caption">
            Runs have separate instance IDs and checkpoints. Repeating a
            configuration produces the same deterministic replay ID, not a
            reused checkpoint.
          </p>
        </Section>
      </div>
      <Section
        title="Replay ledger"
        note="Recorded outcomes, including failures. No simulated progress percentages."
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Scenario / run</th>
                <th>Status</th>
                <th>Window / watermark</th>
                <th>Accepted</th>
                <th>Late drops</th>
                <th>Runtime</th>
                <th>Inspect</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td>
                    <strong>{r.scenario}</strong>
                    <small className="block">{r.id.slice(0, 8)}</small>
                  </td>
                  <td>
                    <Badge
                      tone={
                        r.status === "completed"
                          ? "green"
                          : r.status === "failed"
                            ? "red"
                            : "amber"
                      }
                    >
                      {r.status}
                    </Badge>
                  </td>
                  <td>
                    {r.window_minutes}m / {r.watermark_minutes}m
                  </td>
                  <td>{count(r.result.accepted)}</td>
                  <td>{count(r.result.late_dropped_from_windows)}</td>
                  <td>
                    {r.elapsed_seconds == null
                      ? "Running"
                      : r.elapsed_seconds.toFixed(2) + "s"}
                  </td>
                  <td>
                    <button
                      className="text-link"
                      disabled={r.status !== "completed"}
                      onClick={() => onSelect(r.id)}
                    >
                      Details <ArrowUpRight size={13} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <dialog ref={dialog} className="confirm-dialog">
        <div className="dialog-head">
          <FlaskConical size={22} />
          <button
            aria-label="Close replay confirmation"
            onClick={() => dialog.current?.close()}
          >
            <X size={19} />
          </button>
        </div>
        <h2>Run this local experiment?</h2>
        <p>
          This queues {catalog?.datasets[0]?.events.toLocaleString()} historical
          bars with the <strong>{scenario}</strong> scenario. Spark will use{" "}
          {window}-minute windows and a {watermark}-minute watermark tolerance.
          It uses local CPU and disk; it does not connect to Snowflake or place
          trades.
        </p>
        <label className="confirm-check">
          <input
            type="checkbox"
            checked={confirm}
            onChange={(e) => setConfirm(e.target.checked)}
          />
          I understand this launches a bounded local replay.
        </label>
        <button
          className="primary"
          disabled={!confirm || busy}
          onClick={launch}
        >
          {busy ? "Queueing…" : "Launch replay"}
          <ArrowRight size={15} />
        </button>
      </dialog>
    </>
  );
}
function CatalogView({ catalog }: { catalog: Catalog | null }) {
  return (
    <>
      <Section
        title="Source archives"
        note="Original data stays local. These checksums identify the downloaded files."
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Source rows</th>
                <th>Downloaded bytes</th>
                <th>SHA-256 / lineage</th>
              </tr>
            </thead>
            <tbody>
              {catalog?.datasets[0]?.manifest.sources.map((s) => (
                <tr key={s.symbol}>
                  <td>{s.symbol}</td>
                  <td>{count(s.rows)}</td>
                  <td>{count(s.bytes)}</td>
                  <td>
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener"
                      className="text-link"
                    >
                      Official archive <ArrowUpRight size={12} />
                    </a>
                    <small className="hash block">{s.sha256}</small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="caption">
          Binance Vision ·{" "}
          <a
            href={catalog?.datasets[0]?.manifest.license_url}
            target="_blank"
            rel="noopener"
          >
            Dataset terms and CC BY-NC-SA 4.0
          </a>
          . Derived market-data screenshots and reports retain those terms. This
          project is not endorsed by the source provider.
        </p>
      </Section>
      <div className="catalog-grid">
        {Object.entries(catalog?.definitions || {}).map(
          ([name, definition]) => (
            <article className="panel definition" key={name}>
              <div className="eyebrow">
                DATA CONTRACT / {name.replaceAll("_", " ")}
              </div>
              <h2>{name.replaceAll("_", " ")}</h2>
              <p>{definition}</p>
            </article>
          ),
        )}
      </div>
      <Section
        title="Canonical schema"
        note="Version 1. Decimal-safe storage and explicit data modes."
      >
        <div className="contract-code">
          <code>
            event_id · provider · provider_event_id · symbol · exchange
            <br />
            event_type · event_time_utc · ingestion_time_utc
            <br />
            price · volume · currency · source_mode · source_delay_minutes
            <br />
            schema_version · raw_payload_hash · open · high · low · lineage
          </code>
        </div>
        <p className="caption">
          One-minute bars require OHLC and executed base-asset volume. Quote
          volume is forbidden. Unsupported event types cannot enter the current
          bar warehouse.
        </p>
      </Section>
    </>
  );
}
function Architecture() {
  const [selected, setSelected] = useState(0);
  const parts = [
    [
      "Provider adapter",
      "Fetches official one-minute archives with bounded retries, checksum verification, and source attribution. Live adapters must supply their own licensed implementation.",
    ],
    [
      "Kafka raw topic",
      "Three partitions with fixed symbol assignments for this bounded registry. Raw delivery offsets are retained in the audit ledger. Replication factor one is for local development.",
    ],
    [
      "Spark audit query",
      "Validates event contracts and commits delivery decisions, unique bar facts, and an outbox in one PostgreSQL transaction. Restarting does not create a second fact.",
    ],
    [
      "Curated outbox",
      "Publishes only accepted identities to the curated Kafka topic. Publication is at least once; a crash before marking an outbox row can resend it.",
    ],
    [
      "Spark windows",
      "Uses event-time watermarks and a bounded per-window set of event identities. Identical curated deliveries cannot increase OHLCV totals. Late records remain in raw/curated facts.",
    ],
    [
      "Warehouse & API",
      "PostgreSQL is the local sink. Versioned SQL derives adjacent returns, moving averages, and exploratory anomalies. The optional Snowflake exporter uses staging/COPY/MERGE, but account execution is unverified.",
    ],
  ];
  return (
    <>
      <Section
        title="Follow an event"
        note="Select a component to inspect its responsibility and failure boundary."
      >
        <div className="architecture-flow">
          {parts.map(([name], i) => (
            <button
              key={name}
              className={selected === i ? "selected" : ""}
              onClick={() => setSelected(i)}
            >
              <span>{String(i + 1).padStart(2, "0")}</span>
              {name}
              <ChevronRight size={14} />
            </button>
          ))}
        </div>
        <div className="architecture-detail">
          <span className="step-icon">
            <GitBranch size={21} />
          </span>
          <div>
            <h3>{parts[selected][0]}</h3>
            <p>{parts[selected][1]}</p>
          </div>
        </div>
      </Section>
      <div className="catalog-grid">
        <Section title="At least once, with boundaries">
          <p className="body-copy">
            Kafka acknowledgements, Spark checkpoints, PostgreSQL transactions,
            and Snowflake commits are independent. Durable identities and batch
            ledgers make specific sink replays idempotent. There is no claim of
            end-to-end exactly-once delivery.
          </p>
        </Section>
        <Section title="Processing time is not market time">
          <p className="body-copy">
            January 2025 prices remain January 2025 prices even when replayed
            today. Curation delay measures current processing. The source-mode
            badge always identifies the data as historical.
          </p>
        </Section>
        <Section title="Versioned recovery">
          <p className="body-copy">
            Each replay instance owns its checkpoint. Changing a window,
            watermark, schema, or source creates a new run. The reliability lab
            interrupts a committed sink batch and restarts the same query from
            its existing checkpoint.
          </p>
        </Section>
        <Section title="Local and bounded">
          <p className="body-copy">
            The default run contains three crypto symbols for one day. Launch is
            disabled unless the local lab is explicitly enabled. The queue and
            event counts are capped. No paid warehouse is provisioned.
          </p>
        </Section>
      </div>
    </>
  );
}
