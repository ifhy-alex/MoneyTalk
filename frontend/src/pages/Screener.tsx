import { Fragment, useEffect, useState } from "react";

import { api } from "../api";
import { Disclaimer, ErrorNotice } from "../components/ui";
import { num, pct } from "../format";
import { useApi } from "../hooks";

type Op = ">=" | "<=" | ">" | "<" | "between";
interface Criterion {
  metric: string;
  op: Op;
  value: number;
  value_max?: number | null;
}
interface Preset {
  id: number;
  name: string;
  criteria: Criterion[];
  universe: string[];
}
interface Result {
  metric: string;
  label: string;
  description: string;
  actual: number | null;
  passed: boolean | null;
  source: string;
}
interface Row {
  symbol: string;
  name?: string;
  sector?: string;
  passed?: number;
  failed?: number;
  missing?: number;
  total?: number;
  meets_all?: boolean;
  error?: string;
  results: Result[];
}
type Metrics = Record<string, { label: string; format: "pct" | "ratio" | "money" }>;

function fmt(value: number | null, format: string | undefined) {
  if (value === null) return "sin dato";
  if (format === "pct") return pct(value);
  if (format === "money") return new Intl.NumberFormat("es-CR", { notation: "compact", maximumFractionDigits: 1 }).format(value);
  return num(value);
}

export default function Screener() {
  const metrics = useApi<Metrics>("/investments/metrics");
  const presets = useApi<Preset[]>("/investments/screener/presets");
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [universe, setUniverse] = useState("");
  const [name, setName] = useState("");
  const [useSec, setUseSec] = useState(true);
  const [rows, setRows] = useState<Row[]>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [open, setOpen] = useState<string>();

  useEffect(() => {
    const first = presets.data?.[0];
    if (first && criteria.length === 0) load(first);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presets.data]);

  function load(p: Preset) {
    setCriteria(p.criteria);
    setUniverse(p.universe.join(", "));
    setName(p.name);
  }

  const symbols = () =>
    universe
      .split(/[\s,;]+/)
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

  async function run() {
    setBusy(true);
    setError(undefined);
    try {
      const res = await api.post<{ rows: Row[] }>("/investments/screener/run", {
        criteria,
        universe: symbols(),
        use_sec: useSec,
      });
      setRows(res.rows);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function savePreset() {
    try {
      await api.post("/investments/screener/presets", { name, criteria, universe: symbols() });
      presets.reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const update = (i: number, patch: Partial<Criterion>) =>
    setCriteria(criteria.map((c, j) => (j === i ? { ...c, ...patch } : c)));

  const m = metrics.data ?? {};

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Screener fundamental</h1>
          <div className="muted">Filtros explícitos; cada resultado muestra qué criterio cumplió, con qué valor y de dónde salió.</div>
        </div>
      </div>
      <Disclaimer />
      <ErrorNotice error={error} />

      <div className="card">
        <div className="row">
          <b>Plantillas:</b>
          {presets.data?.map((p) => (
            <button key={p.id} onClick={() => load(p)}>
              {p.name}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>Criterios</h2>
        <div className="small muted" style={{ marginBottom: 8 }}>
          Porcentajes como fracción: 15 % = 0.15. Deuda/patrimonio como cociente: 1 = 100 %.
        </div>
        {criteria.map((c, i) => (
          <div className="row" key={i} style={{ marginBottom: 6 }}>
            <select value={c.metric} onChange={(e) => update(i, { metric: e.target.value })}>
              {Object.entries(m).map(([k, v]) => (
                <option key={k} value={k}>
                  {v.label}
                </option>
              ))}
            </select>
            <select value={c.op} onChange={(e) => update(i, { op: e.target.value as Op })}>
              {[">=", "<=", ">", "<", "between"].map((o) => (
                <option key={o} value={o}>
                  {o === "between" ? "entre" : o}
                </option>
              ))}
            </select>
            <input type="number" step="any" style={{ width: 110 }} value={c.value} onChange={(e) => update(i, { value: Number(e.target.value) })} />
            {c.op === "between" && (
              <input
                type="number"
                step="any"
                style={{ width: 110 }}
                value={c.value_max ?? ""}
                onChange={(e) => update(i, { value_max: Number(e.target.value) })}
              />
            )}
            <button className="link small" onClick={() => setCriteria(criteria.filter((_, j) => j !== i))}>
              Quitar
            </button>
          </div>
        ))}
        <button onClick={() => setCriteria([...criteria, { metric: "pe", op: "<=", value: 20 }])}>+ Criterio</button>

        <label className="field" style={{ marginTop: 14 }}>
          Universo (símbolos separados por coma)
          <textarea rows={2} value={universe} onChange={(e) => setUniverse(e.target.value)} />
        </label>
        <div className="row" style={{ marginTop: 10 }}>
          <label className="row small">
            <input type="checkbox" checked={useSec} onChange={(e) => setUseSec(e.target.checked)} />
            Usar estados financieros oficiales de la SEC cuando existan
          </label>
          <span className="spacer" />
          <input placeholder="Nombre de plantilla" value={name} onChange={(e) => setName(e.target.value)} />
          <button onClick={savePreset} disabled={!name || criteria.length === 0}>
            Guardar plantilla
          </button>
          <button className="primary" onClick={run} disabled={busy || criteria.length === 0}>
            {busy ? "Evaluando…" : "Evaluar"}
          </button>
        </div>
      </div>

      {rows && (
        <div className="card table-wrap">
          <table>
            <thead>
              <tr>
                <th>Símbolo</th>
                <th>Empresa</th>
                <th>Sector</th>
                <th>Criterios</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Fragment key={r.symbol}>
                  <tr>
                    <td>
                      <b>{r.symbol}</b>
                    </td>
                    <td>{r.error ? <span className="neg small">{r.error}</span> : r.name}</td>
                    <td className="small muted">{r.sector}</td>
                    <td>
                      {!r.error && (
                        <>
                          <span className={`badge ${r.meets_all ? "ok" : r.failed ? "" : "warn"}`}>
                            {r.passed}/{r.total} cumplidos
                          </span>{" "}
                          {!!r.missing && <span className="badge warn">{r.missing} sin dato</span>}
                        </>
                      )}
                    </td>
                    <td>
                      {!r.error && (
                        <button className="link small" onClick={() => setOpen(open === r.symbol ? undefined : r.symbol)}>
                          {open === r.symbol ? "Ocultar" : "Ver evidencia"}
                        </button>
                      )}
                    </td>
                  </tr>
                  {open === r.symbol && (
                    <tr>
                      <td colSpan={5} style={{ background: "var(--surface-2)" }}>
                        <table>
                          <tbody>
                            {r.results.map((x) => (
                              <tr key={x.metric}>
                                <td style={{ width: 24 }}>
                                  {x.passed === true ? <span className="check">✓</span> : x.passed === false ? <span className="cross">✗</span> : "?"}
                                </td>
                                <td>{x.description}</td>
                                <td className="num">{fmt(x.actual, m[x.metric]?.format)}</td>
                                <td className="small muted">{x.source}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
