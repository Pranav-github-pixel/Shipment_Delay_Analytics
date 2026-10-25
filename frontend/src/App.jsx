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
  ["Model Explainability", Activity],
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
  const [mode, setMode] = useState("direct"),
    [question, setQuestion] = useState(""),
    [generated, setGenerated] = useState(null);
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
  async function ask() {
    setBusy(true);
    setError("");
    setNotice("");
    setResult(null);
    setGenerated(null);
    try {
      const { data } = await api.post("/query/natural", { question });
      setGenerated(data);
      setSql(data.generated_sql);
      setResult(data);
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
      <div className="actions" role="group" aria-label="Query input mode">
        <button
          className={mode === "direct" ? "" : "secondary"}
          aria-pressed={mode === "direct"}
          disabled={busy}
          onClick={() => {
            setMode("direct");
            setError("");
            setResult(null);
          }}
        >
          Direct SQL
        </button>
        <button
          className={mode === "natural" ? "" : "secondary"}
          aria-pressed={mode === "natural"}
          disabled={busy}
          onClick={() => {
            setMode("natural");
            setError("");
            setResult(null);
          }}
        >
          Natural language
        </button>
      </div>
      {mode === "natural" && (
        <section className="summary">
          <label>
            Analytics question
            <textarea
              aria-label="Analytics question"
              maxLength={2000}
              value={question}
              disabled={busy}
              onChange={(e) => {
                setQuestion(e.target.value);
                setGenerated(null);
                setResult(null);
              }}
              placeholder="Which regions have the highest delay rate? Include order counts."
            />
          </label>
          <button
            disabled={busy || !ready || question.trim().length < 5}
            onClick={ask}
          >
            {busy ? "Generating and running…" : "Generate SQL and run"}
          </button>
          <p className="muted">
            Groq generates SQL against the actual shipments schema. The backend
            validates it and runs read-only Spark SQL; displayed results come
            from Spark.
          </p>
          {generated && (
            <>
              <h3>Generated SQL</h3>
              <pre className="schema">{generated.generated_sql}</pre>
              <small>Generated by Groq · {generated.assistant_model}</small>
              <button className="secondary" onClick={() => setMode("direct")}>
                Edit generated SQL
              </button>
            </>
          )}
        </section>
      )}
      <details>
        <summary>Available columns</summary>
        <p className="schema">
          order_id, order_date, order_month, market, region, shipping_mode,
          customer_segment, payment_type, scheduled_days, actual_days, delayed,
          delay_days, item_count, quantity, sales, net_sales, day_of_week, month
        </p>
      </details>
      {mode === "direct" && (
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
                    setMode("direct");
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
      )}
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

function DelayHeatmap({ cells = [] }) {
  const regions = [...new Set(cells.map((cell) => cell.region))].sort();
  const modes = [...new Set(cells.map((cell) => cell.shipping_mode))].sort();
  const lookup = new Map(
    cells.map((cell) => [
      JSON.stringify([cell.region, cell.shipping_mode]),
      cell,
    ]),
  );
  return (
    <section className="panel" aria-labelledby="heatmap-heading">
      <h2 id="heatmap-heading">Delay rate heatmap</h2>
      <p className="muted">
        Region by shipping mode · delayed eligible orders ÷ eligible orders in
        each cell. Current dashboard filters apply. Each cell shows the rate and
        order count; * marks fewer than 30 orders.
      </p>
      {!cells.length ? (
        <Empty>No eligible orders match these filters.</Empty>
      ) : (
        <>
          <div className="heatmap-legend">
            <span>0% delayed</span>
            <span className="heatmap-gradient" aria-hidden="true" />
            <span>100% delayed</span>
          </div>
          <div className="table-wrap">
            <table
              className="delay-heatmap"
              aria-label="Delay rates by region and shipping mode"
            >
              <thead>
                <tr>
                  <th scope="col">Destination region</th>
                  {modes.map((mode) => (
                    <th scope="col" key={mode}>
                      {mode}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {regions.map((region) => (
                  <tr key={region}>
                    <th scope="row">{region}</th>
                    {modes.map((mode) => {
                      const cell = lookup.get(JSON.stringify([region, mode]));
                      return (
                        <td
                          key={mode}
                          style={
                            cell
                              ? {
                                  backgroundColor: `hsl(12 75% ${96 - cell.delay_rate * 65}%)`,
                                  color:
                                    cell.delay_rate > 0.65 ? "#fff" : "#291b18",
                                }
                              : undefined
                          }
                          title={
                            cell
                              ? `${num(cell.delayed_orders)} delayed out of ${num(cell.total_orders)} eligible orders`
                              : "No eligible orders"
                          }
                        >
                          {cell ? (
                            <>
                              <strong>{pct(cell.delay_rate)}</strong>
                              <small>
                                n = {num(cell.total_orders)}
                                {cell.total_orders < 30 ? " *" : ""}
                              </small>
                            </>
                          ) : (
                            "—"
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">
            Darker cells indicate higher observed delay rates. Empty
            combinations show —. Historical associations do not establish causes
            or predict a specific order.
          </p>
        </>
      )}
    </section>
  );
}

function GeographicMap({ filters, datasetJobId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const { region, shipping_mode, start, end } = filters;
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setData(null);
    setError("");
    const params = Object.fromEntries(
      Object.entries({ region, shipping_mode, start, end }).filter(
        ([, value]) => value,
      ),
    );
    api
      .get("/analytics/map", { params, signal: controller.signal })
      .then(({ data: result }) => {
        if (!controller.signal.aborted) {
          if (result.dataset_job_id !== datasetJobId)
            throw new Error("Dataset changed. Refresh the dashboard.");
          setData(result);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorText(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [region, shipping_mode, start, end, datasetJobId, attempt]);
  return (
    <section className="panel" aria-labelledby="geographic-map-heading">
      <h2 id="geographic-map-heading">Late deliveries around the world</h2>
      <p className="muted">
        Historical delayed orders grouped by destination country. Circle area
        shows delayed-order count; hover for the delay rate and eligible count.
        Dashboard filters apply. Country reference points are approximate, not
        individual delivery locations.
      </p>
      {loading ? (
        <p role="status">Preparing geographic delivery analysis…</p>
      ) : error ? (
        <>
          <p className="error" role="alert">
            {error}
          </p>
          <button
            className="secondary"
            onClick={() => setAttempt((v) => v + 1)}
          >
            Retry map
          </button>
        </>
      ) : (
        data && (
          <>
            <p>
              <strong>{num(data.delayed_orders)} delayed</strong> out of{" "}
              {num(data.total_orders)} eligible orders
              {" · "}
              {num(data.countries.length)} mapped destinations.
            </p>
            {!data.total_orders ? (
              <Empty>No eligible orders match these filters.</Empty>
            ) : (
              <>
                <iframe
                  className="world-map"
                  title="World map of late deliveries by destination country"
                  sandbox=""
                  srcDoc={`<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><style>html,body{margin:0;background:#0a1d2b}svg{display:block;width:100%;height:auto}</style></head><body>${data.svg}</body></html>`}
                />
                {!data.delayed_orders && (
                  <p className="muted">
                    No delayed orders in this population. Hollow markers show
                    destinations with on-time orders.
                  </p>
                )}
              </>
            )}
            {data.unmapped_orders > 0 && (
              <p className="notice">
                {num(data.unmapped_orders)} eligible orders (
                {num(data.unmapped_delayed_orders)} delayed) have missing,
                conflicting or unmatched destination countries and are not
                plotted. They remain in the totals.
              </p>
            )}
            <details>
              <summary>Inspect destination counts and map coverage</summary>
              <Table
                columns={[
                  "country",
                  "eligible_orders",
                  "delayed_orders",
                  "delay_rate",
                ]}
                rows={data.countries.map((row) => ({
                  country: `${row.country} (${row.source_labels.join(", ")})${row.total_orders < 30 ? " *" : ""}`,
                  eligible_orders: num(row.total_orders),
                  delayed_orders: num(row.delayed_orders),
                  delay_rate: pct(row.delay_rate),
                }))}
              />
              {data.unmapped.length > 0 && (
                <Table
                  columns={[
                    "unmapped_destination",
                    "eligible_orders",
                    "delayed_orders",
                  ]}
                  rows={data.unmapped.map((row) => ({
                    unmapped_destination: row.country,
                    eligible_orders: num(row.total_orders),
                    delayed_orders: num(row.delayed_orders),
                  }))}
                />
              )}
            </details>
            <p className="muted">
              * Fewer than 30 eligible orders. Historical patterns do not
              establish causes or predict an individual order. Map rendered in
              Python with bundled{" "}
              <a
                href="https://www.naturalearthdata.com/"
                target="_blank"
                rel="noreferrer"
              >
                Natural Earth
              </a>{" "}
              public-domain boundaries and label points. Country outlines show
              cartographic boundaries; no live tracking or external map tiles
              are used.
            </p>
          </>
        )
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
  const [options, setOptions] = useState(null),
    [optionsLoading, setOptionsLoading] = useState(false);
  const [result, setResult] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState(null),
    [summaryError, setSummaryError] = useState(""),
    [summarizing, setSummarizing] = useState(false);
  useEffect(() => {
    let active = true;
    setOptionsLoading(true);
    setError("");
    api
      .get("/prediction-options")
      .then(({ data }) => {
        if (active) setOptions(data);
      })
      .catch((e) => {
        if (active) setError(errorText(e));
      })
      .finally(() => {
        if (active) setOptionsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  function change(key, value) {
    setValues((old) => ({
      ...old,
      [key]: value,
      ...(key === "market" ? { region: "" } : {}),
    }));
    setResult(null);
    setSummary(null);
    setSummaryError("");
  }
  function payload() {
    const data = { ...values };
    ["scheduled_days", "quantity", "net_sales", "item_count"].forEach((key) => {
      data[key] = Number(data[key]);
    });
    return data;
  }
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    setSummary(null);
    setSummaryError("");
    try {
      setResult((await api.post("/predict", payload())).data);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  async function generateSummary() {
    if (!result) return;
    setSummarizing(true);
    setSummary(null);
    setSummaryError("");
    try {
      const { data } = await api.post("/predict/summary", {
        ...payload(),
        expected_model_version: result.model_version,
      });
      if (data.model_version !== result.model_version)
        throw new Error("Model changed. Predict again.");
      setSummary(data);
    } catch (e) {
      setSummaryError(errorText(e));
    } finally {
      setSummarizing(false);
    }
  }
  return (
    <section className="panel">
      <h2>Assess a new order</h2>
      <p className="muted">
        Use values known when the order is placed. Scheduled days allow 0–7;
        other dropdown options come from eligible DataCo orders. Regions follow
        the selected market. Labels: late = actual duration exceeds the promise;
        on time includes early delivery. Canceled and suspected-fraud orders are
        excluded.
      </p>
      {optionsLoading && <p role="status">Loading supported input values…</p>}
      <form onSubmit={submit}>
        <div className="form-grid">
          {Object.entries(values).map(([key, value]) => {
            const typed = ["quantity", "item_count", "net_sales"].includes(key);
            const choices =
              key === "region" && values.market
                ? options?.regions_by_market[values.market] || []
                : options?.[key] || [];
            return (
              <label key={key}>
                {title(key)}
                {key === "order_date" || typed ? (
                  <input
                    aria-label={title(key)}
                    required
                    type={typed ? "number" : "datetime-local"}
                    min={key === "net_sales" ? 0 : typed ? 1 : undefined}
                    max={key === "net_sales" ? 1000000000 : undefined}
                    step={key === "net_sales" ? "any" : typed ? 1 : undefined}
                    value={value}
                    disabled={busy || summarizing}
                    onChange={(e) => change(key, e.target.value)}
                  />
                ) : (
                  <select
                    aria-label={title(key)}
                    required
                    value={value}
                    disabled={busy || summarizing || optionsLoading || !options}
                    onChange={(e) => change(key, e.target.value)}
                  >
                    <option value="">Select {title(key).toLowerCase()}</option>
                    {choices.map((choice) => (
                      <option key={String(choice)} value={String(choice)}>
                        {typeof choice === "number" ? num(choice) : choice}
                      </option>
                    ))}
                  </select>
                )}
              </label>
            );
          })}
        </div>
        <p className="muted">
          Enter net sales as a non-negative amount; decimals are supported. No
          currency is assumed.
        </p>
        <div className="actions">
          <button
            type="submit"
            disabled={
              !available || busy || summarizing || optionsLoading || !options
            }
          >
            {busy ? "Assessing…" : "Predict delay risk"}{" "}
            <ArrowUpRight size={16} />
          </button>
          <button
            type="button"
            className="secondary"
            onClick={generateSummary}
            disabled={!result || busy || summarizing}
          >
            {summarizing ? "Generating summary…" : "Generate summary"}
          </button>
        </div>
        <p className="muted">
          Groq is contacted only when you request a summary. Predict first;
          changing inputs clears the previous result and summary.
        </p>
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
            at a {pct(result.threshold)} threshold.
          </p>
          <small>{result.scope}</small>
          <h3>SHAP explanation</h3>
          <p>
            {result.model_name} · version {result.model_version}
          </p>
          <p>
            {result.local_explanation.method} · {result.local_explanation.scope}
          </p>
          <p>
            Reference base:{" "}
            {result.local_explanation.output_space === "probability"
              ? pct(result.local_explanation.base_value)
              : `${result.local_explanation.base_value.toFixed(4)} log odds`}
            . Positive values increase the model output; negative values
            decrease it.
          </p>
          <Table
            columns={["feature", "shap_contribution", "observed"]}
            rows={result.local_explanation.features.map((row) => ({
              feature: row.label,
              shap_contribution:
                result.local_explanation.output_space === "probability"
                  ? `${row.contribution >= 0 ? "+" : ""}${(row.contribution * 100).toFixed(2)} percentage points`
                  : `${row.contribution.toFixed(4)} log odds`,
              observed: Object.entries(row.observed_values)
                .map(([key, value]) => `${title(key)}: ${value}`)
                .join("; "),
            }))}
          />
          <p>{result.local_explanation.interpretation}</p>
          <small>{result.local_explanation.limitations}</small>
          <h3>Operator recommendations</h3>
          <p className="muted">
            Predefined review actions triggered by prediction and SHAP, not
            proven risk reductions.
          </p>
          {result.recommendations.map((row) => (
            <div className="recommendation" key={row.rule_id}>
              <h4>{row.title}</h4>
              <p>{row.action}</p>
              <small>{row.trigger}</small>
            </div>
          ))}
        </div>
      )}
      {summaryError && (
        <p className="error" role="alert">
          {summaryError}
        </p>
      )}
      {summary && (
        <section className="summary">
          <h3>Operator summary</h3>
          <p>{summary.summary}</p>
          <small>
            {summary.notice} · {summary.assistant_model}
          </small>
        </section>
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
      {report.selection && (
        <section className="panel">
          <h2>Model comparison</h2>
          <p>
            {report.selection.criterion}. The selected model powers predictions.
          </p>
          <p className="muted">
            Candidates use the same two forward validation windows (
            {num(report.selection.validation_rows)} orders). The selected model
            fits {num(report.selection.fit_rows)} development orders; a separate
            explanation block and the final test set remain excluded.
          </p>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Feature variant</th>
                  <th>Mean fold ROC-AUC</th>
                  <th>Validation ROC-AUC</th>
                  <th>Precision</th>
                  <th>Recall</th>
                  <th>F1</th>
                  <th>Accuracy</th>
                  <th>Selection</th>
                </tr>
              </thead>
              <tbody>
                {report.selection.comparison.map((row) => (
                  <tr key={row.model}>
                    <th>{row.model}</th>
                    <td>{row.variant}</td>
                    <td>{pct(row.mean_roc_auc)}</td>
                    {["roc_auc", "precision", "recall", "f1", "accuracy"].map(
                      (key) => (
                        <td key={key}>{pct(row.metrics[key])}</td>
                      ),
                    )}
                    <td>{row.selected ? "Selected" : "Not selected"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">
            Validation period: {report.selection.validation_start} →{" "}
            {report.selection.validation_end}. Metrics below use the separate
            final test set.
          </p>
          <p>
            Decision threshold: {pct(report.threshold)}.{" "}
            {report.selection.threshold_selection?.metric}
          </p>
          {report.selection.threshold_selection && (
            <Table
              columns={[
                "validation_policy",
                "accuracy",
                "precision",
                "recall",
                "f1",
              ]}
              rows={[
                [
                  "Threshold 50%",
                  report.selection.threshold_selection.default_metrics,
                ],
                [
                  `Selected threshold ${pct(report.threshold)}`,
                  report.selection.threshold_selection.selected_metrics,
                ],
              ].map(([policy, metrics]) => ({
                validation_policy: policy,
                ...Object.fromEntries(
                  ["accuracy", "precision", "recall", "f1"].map((key) => [
                    key,
                    pct(metrics[key]),
                  ]),
                ),
              }))}
            />
          )}
          <details>
            <summary>Search and feature experiments</summary>
            <Table
              columns={[
                "model",
                "variant",
                "parameters",
                "mean_fold_auc",
                "retention",
              ]}
              rows={(report.selection.trials || []).map((row) => ({
                model: row.model,
                variant: row.variant,
                parameters: JSON.stringify(row.parameters),
                mean_fold_auc: row.mean_roc_auc.toFixed(4),
                retention: row.selected
                  ? "Selected"
                  : row.retention_reason || "Compared",
              }))}
            />
          </details>
        </section>
      )}
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
            Rows: actual · columns: predicted · threshold{" "}
            {pct(report.threshold)}
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
      <p className="muted">
        Open Model Explainability for global validation importance and local
        prediction explanations.
      </p>
      <Prediction key={report.model_version} available={true} />
    </>
  );
}

function Explainability({ report }) {
  const [explanation, setExplanation] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setExplanation(null);
    setError("");
    if (!report?.model_version)
      return () => {
        active = false;
      };
    setLoading(true);
    api
      .get("/model/explanations")
      .then(({ data }) => {
        if (!active) return;
        if (
          data.model_version !== report.model_version ||
          data.dataset_fingerprint !== report.fingerprint
        )
          throw new Error("The active model changed. Refresh the explanation.");
        setExplanation(data);
      })
      .catch((e) => {
        if (active) setError(errorText(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [report?.model_version, report?.fingerprint, refresh]);
  if (!report || report.state === "unavailable")
    return (
      <Empty>
        {report?.message ||
          "Model explanations unavailable. Process a dataset first."}
      </Empty>
    );
  return (
    <>
      <section className="panel">
        <h2>Global SHAP importance</h2>
        <button onClick={() => setRefresh(refresh + 1)} disabled={loading}>
          Refresh explanation
        </button>
        {loading && <p role="status">Loading explanation…</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {explanation && (
          <>
            <p>
              {explanation.model_name} · version {explanation.model_version}
            </p>
            <p className="muted">
              Dataset fingerprint: {explanation.dataset_fingerprint}
            </p>
            <p>
              {explanation.shap.method} · {explanation.shap.scope}.{" "}
              {num(explanation.shap.rows)} explained orders ·{" "}
              {explanation.shap.reference_rows} training-reference orders.
            </p>
            <p>
              Encoded categories and derived features are summed into original
              input groups. Output space: {explanation.shap.output_space}.{" "}
              {explanation.shap.variation}.
            </p>
            <p>
              Mean absolute SHAP measures the typical magnitude of a group's
              contribution. Higher values indicate more influence; use local
              signed SHAP to see whether a factor raises or lowers a particular
              prediction.
            </p>
            {explanation.shap.features.length ? (
              <Table
                columns={[
                  "feature_group",
                  "mean_absolute_shap",
                  "variation_across_orders",
                  "inputs",
                ]}
                rows={explanation.shap.features.map((row) => ({
                  feature_group: row.label,
                  inputs: row.columns.map(title).join(", "),
                  mean_absolute_shap:
                    explanation.shap.output_space === "probability"
                      ? `${(row.importance * 100).toFixed(2)} pp`
                      : `${row.importance.toFixed(4)} log odds`,
                  variation_across_orders:
                    explanation.shap.output_space === "probability"
                      ? `${(row.std * 100).toFixed(2)} pp`
                      : row.std.toFixed(4),
                }))}
              />
            ) : (
              <Empty>No global importance values available.</Empty>
            )}
            <p className="muted">{explanation.shap.limitations}</p>
            <details>
              <summary>Validation permutation diagnostic</summary>
              <p>
                Separate ROC-AUC decrease after grouped shuffling;{" "}
                {explanation.repeats} repeats on {num(explanation.rows)}{" "}
                held-out validation orders. This is not SHAP.
              </p>
              <Table
                columns={[
                  "feature",
                  "mean_auc_decrease",
                  "repeat_standard_deviation",
                ]}
                rows={explanation.features.map((row) => ({
                  feature: row.label,
                  mean_auc_decrease: row.importance.toFixed(4),
                  repeat_standard_deviation: row.std.toFixed(4),
                }))}
              />
            </details>
          </>
        )}
      </section>
      <Prediction key={report.model_version} available={Boolean(explanation)} />
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
                      <DelayHeatmap cells={data.heatmap} />
                      <GeographicMap
                        filters={filters}
                        datasetJobId={status?.job.id}
                      />
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
          {tab === "Model Evaluation" && (
            <Model key={status?.model.model_version} report={status?.model} />
          )}
          {tab === "Model Explainability" && (
            <Explainability
              key={status?.model.model_version}
              report={status?.model}
            />
          )}
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
