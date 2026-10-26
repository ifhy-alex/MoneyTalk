import { useState } from "react";

import { api } from "../api";
import Compass from "../art/Compass";
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

const LATENT_SPOKES = [
  { label: "Ingresos", change: 0 },
  { label: "Utilidad bruta", change: 0 },
  { label: "Utilidad op.", change: 0 },
  { label: "Utilidad neta", change: 0 },
  { label: "EPS diluido", change: 0 },
  { label: "Flujo op.", change: 0 },
  { label: "Efectivo", change: 0 },
  { label: "Deuda LP", change: 0 },
];

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

      {!report && (
        <figure className="card report-art">
          <Compass
            latent
            spokes={LATENT_SPOKES}
            label="Rosa de los vientos en reposo para reportes 10-Q"
          />
          <figcaption>
            <h2>Rosa de los vientos del 10-Q</h2>
            <p className="small muted">
              Ingresá un símbolo de EE. UU. arriba (por ejemplo <code>MSFT</code>, <code>AAPL</code> o <code>NVDA</code>)
              para trazar cómo cambiaron sus métricas frente al mismo trimestre del año pasado.
            </p>
            <p className="small muted">
              El anillo punteado representa variación cero: los rayos que crecen salen hacia afuera en verde y los que
              se contraen entran hacia el centro en bermellón.
            </p>
          </figcaption>
        </figure>
      )}

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
          {(() => {
            const moves = report.table.filter((r) => r.yoy !== null).sort((a, b) => b.yoy! - a.yoy!);
            if (moves.length < 3) return null;
            const best = moves[0]!, worst = moves[moves.length - 1]!;
            return (
              <figure className="card report-art">
                <Compass
                  spokes={report.table.map((r) => ({ label: r.label, change: r.yoy }))}
                  label={`Rosa de los vientos del trimestre de ${report.symbol}`}
                />
                <figcaption>
                  <h2>El trimestre de un vistazo</h2>
                  <p className="small">
                    Un rayo por métrica. El anillo punteado es «igual que hace un año»: el rayo sale hacia afuera si la
                    métrica creció y se mete hacia el centro si cayó. Pasá el mouse por un punto para ver cuál es.
                  </p>
                  <p className="small">
                    Lo que más creció: <b>{best.label}</b> <span className="pos">{pct(best.yoy, 0)}</span>.{" "}
                    {worst.yoy! < 0 ? (
                      <>
                        Lo que más cayó: <b>{worst.label}</b> <span className="neg">{pct(worst.yoy, 0)}</span>.
                      </>
                    ) : (
                      <>Ninguna métrica cayó frente a hace un año.</>
                    )}
                  </p>
                </figcaption>
              </figure>
            );
          })()}
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
