import { useState } from "react";

import { api } from "../api";
import { Disclaimer, ErrorNotice } from "../components/ui";
import { num, pct } from "../format";
import Help from "../components/Help";

interface Row {
  metric: string;
  label: string;
  current: number;
  previous_quarter: number | null;
  year_ago: number | null;
  qoq: number | null;
  yoy: number | null;
  source: string;
}
interface Report {
  symbol: string;
  period_end: string;
  ai_enabled: boolean;
  cached: boolean;
  table: Row[];
  summary: { summary: string; highlights: string[]; caveats: string[] } | null;
}

const big = (v: number | null, metric: string) =>
  v === null ? "—" : metric === "eps_diluted" ? `$${num(v, 2)}` : new Intl.NumberFormat("es-CR", { notation: "compact", maximumFractionDigits: 2 }).format(v);

export default function Reports() {
  const [symbol, setSymbol] = useState("");
  const [report, setReport] = useState<Report>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function load(summarize: boolean) {
    setBusy(true);
    setError(undefined);
    try {
      setReport(await api.post<Report>(`/investments/reports/${symbol}/quarterly?summarize=${summarize}`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <div className="title-row">
            <h1>Reportes trimestrales</h1>
            <Help topic="reportes" />
          </div>
          <div className="muted">
            Cambios del último 10-Q según la SEC. La IA solo redacta a partir de esta tabla.
          </div>
        </div>
        <div className="row">
          <input placeholder="Símbolo (ej. MSFT)" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
          <button disabled={!symbol || busy} onClick={() => load(false)}>
            Ver cambios
          </button>
          <button className="primary" disabled={!symbol || busy} onClick={() => load(true)}>
            {busy ? "Procesando…" : "Explicar con IA"}
          </button>
        </div>
      </div>
      <Disclaimer />
      <ErrorNotice error={error} />

      {report && (
        <>
          {report.summary ? (
            <div className="card">
              <h2>
                {report.symbol} · trimestre al {report.period_end} {report.cached && <span className="badge">guardado</span>}
              </h2>
              <p>{report.summary.summary}</p>
              <h3>Lo más relevante</h3>
              <ul>
                {report.summary.highlights.map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
              <h3>Precauciones</h3>
              <ul className="muted">
                {report.summary.caveats.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </div>
          ) : (
            !report.ai_enabled && (
              <div className="notice info small">Configurá ANTHROPIC_API_KEY para obtener la explicación en español.</div>
            )
          )}
          <div className="card table-wrap">
            <h2>Cifras (USD)</h2>
            <table>
              <thead>
                <tr>
                  <th>Métrica</th>
                  <th className="num">Trimestre</th>
                  <th className="num">Trim. anterior</th>
                  <th className="num">Hace un año</th>
                  <th className="num">Var. trim.</th>
                  <th className="num">Var. anual</th>
                  <th>Fuente</th>
                </tr>
              </thead>
              <tbody>
                {report.table.map((r) => (
                  <tr key={r.metric}>
                    <td>{r.label}</td>
                    <td className="num">{big(r.current, r.metric)}</td>
                    <td className="num">{big(r.previous_quarter, r.metric)}</td>
                    <td className="num">{big(r.year_ago, r.metric)}</td>
                    <td className={`num ${(r.qoq ?? 0) < 0 ? "neg" : "pos"}`}>{pct(r.qoq)}</td>
                    <td className={`num ${(r.yoy ?? 0) < 0 ? "neg" : "pos"}`}>{pct(r.yoy)}</td>
                    <td className="small muted">{r.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
