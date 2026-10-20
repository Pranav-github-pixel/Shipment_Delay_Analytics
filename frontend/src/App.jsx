import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  Activity,
  Database,
  BarChart3,
  ShieldCheck,
  Code2,
  Truck,
  Play,
  RefreshCw,
  ArrowUpRight,
} from "lucide-react";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "/api",
  timeout: 120000,
});
const tabs = [
  ["Overview", Activity],
  ["Data Quality", ShieldCheck],
  ["Delay Analytics", BarChart3],
  ["Model Evaluation", Database],
  ["SQL Analytics", Code2],
];
const num = (n) =>
  n == null
    ? "—"
    : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
const pct = (n) => (n == null ? "—" : `${(n * 100).toFixed(1)}%`);
const errorText = (e) => {
  const d = e.response?.data?.detail;
  return typeof d === "string"
    ? d
    : Array.isArray(d)
      ? d.map((x) => `${x.loc.slice(1).join(".")}: ${x.msg}`).join("; ")
      : e.message;
};
const title = (s) =>
  s.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());

function Empty({ children }) {
  return <div className="empty">{children}</div>;
}
function Metric({ label, value, hint, accent }) {
  return (
    <div className={`metric ${accent ? "accent" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </div>
  );
}
function Rates({ name, rows = [] }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{name}</h2>
        <span className="muted">Delay rate · order count</span>
      </div>
      {!rows.length ? (
        <Empty>No orders match these filters.</Empty>
      ) : (
        <div className="rate-list">
          {rows.map((r) => (
            <div className="rate-row" key={r.label}>
              <div>
                <strong>{r.label}</strong>
                <small>
                  {num(r.total_orders)} orders
                  {r.total_orders < 30 ? " · small sample" : ""}
                </small>
              </div>
              <div className="track">
                <div style={{ width: `${r.delay_rate * 100}%` }} />
              </div>
              <b>{pct(r.delay_rate)}</b>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
function Table({ columns, rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{title(c)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c}>{r[c] == null ? "—" : String(r[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <Empty>No rows.</Empty>}
    </div>
  );
}

function SqlConsole({ ready }) {
  const [saved, setSaved] = useState([]),
    [name, setName] = useState(""),
    [sql, setSql] = useState(
      "SELECT region, COUNT(*) AS orders, AVG(delayed) AS delay_rate FROM shipments GROUP BY region",
    );
  const [result, setResult] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  async function load() {
    try {
      setSaved((await api.get("/queries")).data.queries);
    } catch (e) {
      setError(errorText(e));
    }
  }
  useEffect(() => {
    load();
  }, []);
  async function action(kind, qname) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (kind === "run") {
        setResult(null);
        setResult((await api.post("/query", { query: sql })).data);
      }
      if (kind === "save") {
        await api.post("/queries", { name, query: sql });
        setNotice("Query saved.");
        await load();
      }
      if (kind === "delete") {
        await api.delete(`/queries/${encodeURIComponent(qname)}`);
        setNotice("Query deleted.");
        await load();
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Spark SQL workspace</h2>
        <span className="badge">Read only</span>
      </div>
      <p className="muted">
        Query the full processed dataset. Dashboard filters do not apply here.
        Single SELECT queries on shipments; up to 100 displayed rows.
      </p>
      <details>
        <summary>Available columns</summary>
        <p className="schema">
          order_id, order_date, order_month, market, region, shipping_mode,
          customer_segment, payment_type, scheduled_days, actual_days, delayed,
          delay_days, item_count, quantity, sales, net_sales, day_of_week, month
        </p>
      </details>
      <div className="sql-layout">
        <aside className="saved">
          <h3>Saved queries</h3>
          {saved.map((q) => (
            <div key={q.name}>
              <button
                className="text-button"
                disabled={busy}
                onClick={() => {
                  setName(q.name);
                  setSql(q.query);
                  setResult(null);
                }}
              >
                {q.name}
              </button>
              <button
                className="remove"
                disabled={busy}
                aria-label={`Delete ${q.name}`}
                onClick={() => action("delete", q.name)}
              >
                ×
              </button>
            </div>
          ))}
          {!saved.length && <p>No saved queries.</p>}
        </aside>
        <div>
          <label>
            Query name
            <input
              value={name}
              maxLength={80}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            SQL
            <textarea
              aria-label="SQL"
              spellCheck="false"
              value={sql}
              onChange={(e) => setSql(e.target.value)}
            />
          </label>
          <div className="actions">
            <button
              disabled={busy || !ready || !sql.trim()}
              onClick={() => action("run")}
            >
              <Play size={15} /> {busy ? "Working…" : "Run query"}
            </button>
            <button
              className="secondary"
              disabled={busy || !name.trim() || !sql.trim()}
              onClick={() => action("save")}
            >
              Save query
            </button>
          </div>
        </div>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      {result && (
        <>
          <p className="muted">
            {result.data.length} rows shown
            {result.truncated ? " · result truncated at 100 rows" : ""}
          </p>
          <Table columns={result.columns} rows={result.data} />
        </>
      )}
    </section>
  );
}

function Prediction({ available }) {
  const [values, setValues] = useState({
    order_date: "",
    scheduled_days: "",
    quantity: "",
    net_sales: "",
    item_count: "",
    market: "",
    region: "",
    customer_segment: "",
    payment_type: "",
  });
  const [result, setResult] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const payload = { ...values };
      ["scheduled_days", "quantity", "net_sales", "item_count"].forEach(
        (k) => (payload[k] = Number(payload[k])),
      );
      setResult((await api.post("/predict", payload)).data);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <h2>Assess a new order</h2>
      <p className="muted">
        Enter values known when the order is placed. Predictions are conditional
        on shipment proceeding. The model was evaluated on historical DataCo
        data, not current operations.
      </p>
      <form onSubmit={submit}>
        <div className="form-grid">
          {Object.entries(values).map(([k, v]) => {
            const numeric = [
              "scheduled_days",
              "quantity",
              "net_sales",
              "item_count",
            ].includes(k);
            return (
              <label key={k}>
                {title(k)}
                <input
                  required
                  type={
                    k === "order_date"
                      ? "datetime-local"
                      : numeric
                        ? "number"
                        : "text"
                  }
                  min={
                    numeric
                      ? k === "quantity" || k === "item_count"
                        ? 1
                        : 0
                      : undefined
                  }
                  step={
                    k === "net_sales" || k === "scheduled_days"
                      ? "any"
                      : undefined
                  }
                  value={v}
                  onChange={(e) => {
                    setValues({ ...values, [k]: e.target.value });
                    setResult(null);
                  }}
                />
              </label>
            );
          })}
        </div>
        <button disabled={!available || busy}>
          {busy ? "Assessing…" : "Predict delay risk"}{" "}
          <ArrowUpRight size={16} />
        </button>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {result && (
        <div className="prediction" role="status">
          <strong>{pct(result.delay_probability)} estimated delay risk</strong>
          <p>
            {result.predicted_delayed
              ? "Predicted delayed"
              : "Predicted on time"}{" "}
            at a 50% threshold.
          </p>
          <small>{result.scope}</small>
        </div>
      )}
    </section>
  );
}

function Model({ report }) {
  if (!report || report.state === "unavailable")
    return (
      <Empty>
        {report?.message || "Model unavailable. Process data first."}
      </Empty>
    );
  const m = report.metrics,
    cm = report.confusion_matrix;
  return (
    <>
      <div className="section-intro">
        <div>
          <h2>{report.model}</h2>
          <p>{report.split}</p>
        </div>
        <span className="badge">
          {report.state === "loaded" ? "Loaded artifact" : "Newly trained"}
        </span>
      </div>
      <div className="metrics">
        {["precision", "recall", "f1", "roc_auc"].map((k) => (
          <Metric
            key={k}
            label={title(k)}
            value={pct(m[k])}
            hint="Chronological test set"
          />
        ))}
      </div>
      <div className="two-col">
        <section className="panel">
          <h2>Confusion matrix</h2>
          <p className="muted">
            Rows: actual · columns: predicted · threshold 50%
          </p>
          <table className="matrix">
            <thead>
              <tr>
                <th></th>
                <th>On time</th>
                <th>Delayed</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th>On time</th>
                <td>{num(cm[0][0])}</td>
                <td>{num(cm[0][1])}</td>
              </tr>
              <tr>
                <th>Delayed</th>
                <td>{num(cm[1][0])}</td>
                <td>{num(cm[1][1])}</td>
              </tr>
            </tbody>
          </table>
          <p>
            Accuracy <b>{pct(m.accuracy)}</b> · training-majority baseline{" "}
            <b>{pct(report.majority_baseline_accuracy)}</b>
          </p>
        </section>
        <section className="panel">
          <h2>Evaluation context</h2>
          <dl>
            <dt>Training orders / available</dt>
            <dd>
              {num(report.train_rows)} / {num(report.available_train_rows)}
            </dd>
            <dt>Test orders / available</dt>
            <dd>
              {num(report.test_rows)} / {num(report.available_test_rows)}
            </dd>
            <dt>Training period</dt>
            <dd>
              {report.train_start} → {report.train_end}
            </dd>
            <dt>Test period</dt>
            <dd>
              {report.test_start} → {report.test_end}
            </dd>
            <dt>Training / test delay rate</dt>
            <dd>
              {pct(report.train_delay_rate)} / {pct(report.test_delay_rate)}
            </dd>
          </dl>
          <p className="muted">
            Numeric predictors stay numeric. No actual shipping duration or
            delivery status enters the model.
          </p>
        </section>
      </div>
      <section className="panel">
        <h2>What the model relies on</h2>
        <p className="muted">
          Permutation importance: decrease in test ROC-AUC after shuffling each
          feature. Three repeats on {num(report.explanation_rows)} held-out
          orders. Negative values indicate no reliable benefit; correlated
          features may share importance. These are predictive associations, not
          causes.
        </p>
        <Table
          columns={["feature", "mean_auc_decrease", "standard_deviation"]}
          rows={report.explanations.map((x) => ({
            feature: title(x.feature),
            mean_auc_decrease: x.importance.toFixed(4),
            standard_deviation: x.std.toFixed(4),
          }))}
        />
      </section>
      <Prediction available={true} />
    </>
  );
}

export default function App() {
  const [tab, setTab] = useState("Overview"),
    [status, setStatus] = useState(null),
    [data, setData] = useState(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [starting, setStarting] = useState(false);
  const [filters, setFilters] = useState({
      region: "",
      shipping_mode: "",
      start: "",
      end: "",
    }),
    [draft, setDraft] = useState(filters),
    [hdfs, setHdfs] = useState(null),
    [checking, setChecking] = useState(false);
  const requestId = useRef(0);
  const [connectionError, setConnectionError] = useState("");
  async function refresh() {
    try {
      setStatus((await api.get("/status")).data);
      setConnectionError("");
    } catch (e) {
      setConnectionError(`Backend unavailable: ${errorText(e)}`);
    }
  }
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 2500);
    return () => clearInterval(timer);
  }, []);
  const running = status?.job.state === "running",
    ready = status?.data_ready && !running;
  useEffect(() => {
    const id = ++requestId.current;
    if (!ready) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    api
      .get("/analytics", {
        params: Object.fromEntries(
          Object.entries(filters).filter(([, v]) => v),
        ),
      })
      .then((r) => {
        if (id === requestId.current) setData(r.data);
      })
      .catch((e) => {
        if (id === requestId.current) {
          setError(errorText(e));
          setData(null);
        }
      })
      .finally(() => {
        if (id === requestId.current) setLoading(false);
      });
    return () => {
      requestId.current++;
    };
  }, [ready, status?.job.id, filters]);
  async function ingest(force = false) {
    setStarting(true);
    setError("");
    try {
      const r = await api.post(`/ingest?force_retrain=${force}`);
      setStatus((s) => ({ ...s, job: r.data.job }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setStarting(false);
    }
  }
  async function checkHdfs() {
    setChecking(true);
    try {
      setHdfs((await api.get("/hdfs-status")).data);
    } catch (e) {
      setHdfs({ status: "disconnected", message: errorText(e) });
    } finally {
      setChecking(false);
    }
  }
  const q = status?.quality,
    overview = data?.overview;
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <Truck />
          <div>
            Transit<span>SHIPMENT INTELLIGENCE</span>
          </div>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {tabs.map(([name, Icon]) => (
            <button
              key={name}
              className={tab === name ? "active" : ""}
              onClick={() => setTab(name)}
            >
              <Icon size={19} />
              {name}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className={`dot ${status ? "online" : ""}`} />
          {status
            ? `${status.mode.toUpperCase()} storage mode`
            : "Connecting to backend"}
          <small>PySpark · HDFS · Scikit-learn</small>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <span className="eyebrow">LOGISTICS OPERATIONS</span>
            <h1>{tab}</h1>
          </div>
          <button
            className="secondary"
            onClick={refresh}
            aria-label="Refresh system status"
          >
            <RefreshCw size={16} /> Refresh
          </button>
        </header>
        <div className="content">
          <section className="hero">
            <div>
              <span className="eyebrow">FROM ORDERS TO INSIGHT</span>
              <h2>
                Understand delays.
                <br />
                Make informed decisions.
              </h2>
              <p>Real order-level analytics, backed by Spark.</p>
            </div>
            <div className="hero-actions">
              <span className="badge">
                {status?.job.stage || "Connecting…"}
              </span>
              <button
                disabled={!status || running || starting}
                onClick={() => ingest(false)}
              >
                <Play size={16} />
                {running || starting
                  ? "Processing…"
                  : status?.data_ready
                    ? "Reprocess dataset"
                    : "Process dataset"}
              </button>
              {status?.data_ready && (
                <button
                  className="hero-link"
                  disabled={running || starting}
                  onClick={() => ingest(true)}
                >
                  Reprocess and retrain model
                </button>
              )}
            </div>
          </section>
          {connectionError && (
            <div className="error" role="alert">
              {connectionError}
            </div>
          )}
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          {status?.job.error && (
            <div className="error" role="alert">
              {status.job.error}
            </div>
          )}
          {running && (
            <div className="notice" role="status">
              {status.job.stage}. This can take several minutes. Progress
              updates automatically.
            </div>
          )}
          {(tab === "Overview" || tab === "Delay Analytics") && (
            <>
              <form
                className="filters"
                onSubmit={(e) => {
                  e.preventDefault();
                  setFilters({ ...draft });
                }}
              >
                <label>
                  Region
                  <select
                    aria-label="Region"
                    value={draft.region}
                    onChange={(e) =>
                      setDraft({ ...draft, region: e.target.value })
                    }
                  >
                    <option value="">All regions</option>
                    {data?.options.region.map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Shipping mode
                  <select
                    aria-label="Shipping mode"
                    value={draft.shipping_mode}
                    onChange={(e) =>
                      setDraft({ ...draft, shipping_mode: e.target.value })
                    }
                  >
                    <option value="">All modes</option>
                    {data?.options.shipping_mode.map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </label>
                <label>
                  From
                  <input
                    type="date"
                    value={draft.start}
                    max={draft.end || undefined}
                    onChange={(e) =>
                      setDraft({ ...draft, start: e.target.value })
                    }
                  />
                </label>
                <label>
                  Through
                  <input
                    type="date"
                    value={draft.end}
                    min={draft.start || undefined}
                    onChange={(e) =>
                      setDraft({ ...draft, end: e.target.value })
                    }
                  />
                </label>
                <button disabled={!ready || loading}>Apply</button>
                <button
                  type="button"
                  className="secondary"
                  disabled={!ready || loading}
                  onClick={() => {
                    const f = {
                      region: "",
                      shipping_mode: "",
                      start: "",
                      end: "",
                    };
                    setDraft(f);
                    setFilters(f);
                  }}
                >
                  Reset
                </button>
              </form>
              {loading ? (
                <Empty>Calculating analytics…</Empty>
              ) : !data || !ready ? (
                <Empty>
                  {running
                    ? "Analytics will refresh when processing completes."
                    : "Process the dataset to explore shipment performance."}
                </Empty>
              ) : (
                <>
                  <p className="muted">{data.definition}</p>
                  <div className="metrics">
                    <Metric
                      label="Eligible orders"
                      value={num(overview.total_orders)}
                      hint="Shipment proxy"
                      accent
                    />
                    <Metric
                      label="Delayed orders"
                      value={num(overview.delayed_orders)}
                      hint={`${pct(overview.delay_rate)} delay rate`}
                    />
                    <Metric
                      label="On-time rate"
                      value={pct(overview.on_time_rate)}
                      hint="Includes early delivery"
                    />
                    <Metric
                      label="Average shipping"
                      value={`${num(overview.average_shipping_days)} days`}
                      hint={`${num(overview.average_scheduled_days)} days scheduled`}
                    />
                  </div>
                  <div className="two-col">
                    <Rates
                      name="Shipping mode performance"
                      rows={data.views.shipping}
                    />
                    <Rates
                      name="Customer segments"
                      rows={data.views.segmentation}
                    />
                  </div>
                  {tab === "Delay Analytics" && (
                    <>
                      <Rates
                        name="Regional performance"
                        rows={data.views.regional}
                      />
                      <Rates
                        name="Monthly delay trend"
                        rows={data.views.temporal}
                      />
                    </>
                  )}
                </>
              )}
            </>
          )}
          {tab === "Overview" && (
            <section className="panel">
              <h2>System status</h2>
              <dl>
                <dt>Storage</dt>
                <dd>{status?.mode || "Unavailable"}</dd>
                <dt>Dataset</dt>
                <dd className="source">{status?.source || "Unavailable"}</dd>
                <dt>Model</dt>
                <dd>{status?.model.state || "Unavailable"}</dd>
              </dl>
              <button
                className="secondary"
                disabled={running || checking}
                onClick={checkHdfs}
              >
                {checking ? "Checking HDFS…" : "Check HDFS connection"}
              </button>
              {hdfs && (
                <p className={hdfs.status === "connected" ? "notice" : "error"}>
                  {hdfs.message}
                  {hdfs.status === "connected"
                    ? ` · Dataset ${hdfs.dataset_exists ? "present" : "not found"}`
                    : ""}
                </p>
              )}
            </section>
          )}
          {tab === "Data Quality" &&
            (!q ? (
              <Empty>Process a dataset to inspect its quality.</Empty>
            ) : (
              <>
                <p className="muted">
                  Dataset-wide quality counts, independent of dashboard filters.
                  Row counts and order counts are shown separately.
                </p>
                <div className="metrics">
                  <Metric label="Raw item rows" value={num(q.raw_rows)} />
                  <Metric
                    label="Exact duplicates"
                    value={num(q.exact_duplicate_rows)}
                  />
                  <Metric
                    label="Deduplicated rows"
                    value={num(q.deduplicated_rows)}
                  />
                  <Metric
                    label="Eligible orders"
                    value={num(q.eligible_orders)}
                    accent
                  />
                </div>
                <div className="two-col">
                  <section className="panel">
                    <h2>Validation and exclusions</h2>
                    <Table
                      columns={["check", "count"]}
                      rows={[
                        "invalid_rows",
                        "invalid_order_dates",
                        "conflicting_item_ids",
                        "invalid_or_conflicting_item_orders",
                        "inconsistent_orders",
                        "cancelled_orders",
                        "target_mismatch_orders",
                      ].map((k) => ({ check: title(k), count: q[k] }))}
                    />
                    <p className="muted">
                      Invalid-row diagnostics overlap. An invalid or conflicting
                      item excludes its whole order. Missing dimensions use
                      another consistent value from the same order, otherwise
                      Unknown.
                    </p>
                  </section>
                  <section className="panel">
                    <h2>Missing source values</h2>
                    <p className="muted">
                      Required analytical columns, after exact deduplication and
                      before cleaning.
                    </p>
                    <Table
                      columns={["column", "missing_rows"]}
                      rows={Object.entries(q.missing_values).map(
                        ([column, missing_rows]) => ({ column, missing_rows }),
                      )}
                    />
                  </section>
                </div>
              </>
            ))}
          {tab === "Model Evaluation" && <Model report={status?.model} />}
          {tab === "SQL Analytics" && (
            <SqlConsole key={status?.job.id} ready={ready} />
          )}
          <footer>
            Historical DataCo supply chain analysis · Counts represent orders,
            not independently tracked physical shipments.
          </footer>
        </div>
      </main>
    </div>
  );
}
