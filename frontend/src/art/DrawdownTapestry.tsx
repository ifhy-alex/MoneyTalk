/**
 * Tapiz de cosechas y reflejo de caída para Backtesting.
 * Arriba de la línea de flotación: cada año de rebalanceo es una columna tramada con su
 * rendimiento y las empresas elegidas, comparada con el punto del índice (SPY).
 * Debajo de la línea de flotación: el reflejo sumergido (drawdown desde el máximo previo)
 * de la estrategia frente al índice, grabado con líneas horizontales de agua.
 * Antes de ejecutar el backtest, se dibuja en estado latente (marca de agua) con los años y el universo.
 */
export interface TapestryPeriod {
  year: string;
  holdings: string[];
  strategyReturn: number | null;
  benchmarkReturn: number | null;
}

export interface TapestryPoint {
  date: string;
  strategy: number;
  benchmark: number;
}

const W = 1000;
const H = 196;
const LEFT = 48;
const RIGHT = 972;
const MID = 108; // línea de flotación (0 %)
const TOP = 18;
const BOT = 176;

function computeDrawdowns(vals: number[]): number[] {
  let peak = -Infinity;
  return vals.map((v) => {
    if (v > peak) peak = v;
    return peak > 0 ? (v - peak) / peak : 0; // <= 0
  });
}

export default function DrawdownTapestry({
  periods,
  curve,
  startYear,
  endYear,
  universeCount,
  label,
}: {
  periods?: TapestryPeriod[];
  curve?: TapestryPoint[];
  startYear: number;
  endYear: number;
  universeCount: number;
  label: string;
}) {
  const latent = !periods || periods.length === 0;

  if (latent) {
    const count = Math.max(2, Math.min(20, endYear - startYear + 1));
    const colW = (RIGHT - LEFT) / count;
    return (
      <svg className="tapestry latent" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
        <line className="tapestry-waterline" x1={LEFT} x2={RIGHT} y1={MID} y2={MID} />
        {Array.from({ length: count }, (_, i) => {
          const x = LEFT + i * colW + colW * 0.14;
          const bw = colW * 0.72;
          const h = 28 + ((i * 17) % 34);
          return (
            <g key={i} className="tapestry-col-latent">
              <rect x={x} y={MID - h} width={bw} height={h} rx={2} />
              <line x1={x} x2={x + bw} y1={MID + h * 0.45} y2={MID + h * 0.45} />
              <text x={x + bw / 2} y={H - 6} textAnchor="middle">
                {startYear + i}
              </text>
            </g>
          );
        })}
        <text x={(LEFT + RIGHT) / 2} y={MID - 44} textAnchor="middle" className="tapestry-watermark">
          {universeCount} empresas en el universo · {startYear}–{endYear} (ejecutá para grabar el recorrido)
        </text>
      </svg>
    );
  }

  const maxRet = Math.max(
    0.15,
    ...periods.flatMap((p) => [Math.abs(p.strategyReturn ?? 0), Math.abs(p.benchmarkReturn ?? 0)]),
  );
  const colW = (RIGHT - LEFT) / periods.length;
  const yRet = (r: number) => MID - (Math.max(-maxRet, Math.min(maxRet, r)) / maxRet) * (MID - TOP);

  const stratDD = curve && curve.length > 1 ? computeDrawdowns(curve.map((c) => c.strategy)) : [];
  const benchDD = curve && curve.length > 1 ? computeDrawdowns(curve.map((c) => c.benchmark)) : [];
  const maxDD = Math.max(0.08, ...stratDD.map(Math.abs), ...benchDD.map(Math.abs));
  const yDD = (dd: number) => MID + (Math.abs(dd) / maxDD) * (BOT - MID);

  const ddPath = (dds: number[]) =>
    dds
      .map((d, i) => `${i ? "L" : "M"}${(LEFT + (i / (dds.length - 1)) * (RIGHT - LEFT)).toFixed(1)},${yDD(d).toFixed(1)}`)
      .join("");

  const stratLine = stratDD.length > 1 ? ddPath(stratDD) : "";
  const benchLine = benchDD.length > 1 ? ddPath(benchDD) : "";

  return (
    <svg className="tapestry" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <text x={8} y={TOP + 8} className="tapestry-axis-lbl">
        +{Math.round(maxRet * 100)}%
      </text>
      <text x={8} y={MID + 4} className="tapestry-axis-lbl">
        0%
      </text>
      <text x={8} y={BOT} className="tapestry-axis-lbl">
        −{Math.round(maxDD * 100)}%
      </text>

      {/* Reflejo sumergido (drawdown) */}
      {benchLine && <path className="tapestry-dd-bench" d={benchLine} />}
      {stratLine && (
        <>
          <path className="tapestry-dd-fill" d={`${stratLine}L${RIGHT},${MID}L${LEFT},${MID}Z`} />
          {[3, 6].map((o) => (
            <path key={o} className="tapestry-dd-echo" d={stratLine} transform={`translate(0 ${o})`} />
          ))}
          <path className="tapestry-dd-line" d={stratLine} />
        </>
      )}

      <line className="tapestry-waterline" x1={LEFT} x2={RIGHT} y1={MID} y2={MID} />

      {/* Cosechas anuales (rebalanceos) */}
      {periods.map((p, i) => {
        const sr = p.strategyReturn ?? 0;
        const br = p.benchmarkReturn ?? 0;
        const beat = sr >= br;
        const x = LEFT + i * colW + colW * 0.16;
        const bw = Math.max(8, colW * 0.68);
        const yS = yRet(sr);
        const yB = yRet(br);
        const topY = Math.min(MID, yS);
        const barH = Math.max(2, Math.abs(MID - yS));
        const hatchCount = Math.max(2, Math.min(10, Math.round(barH / 5)));
        const sPct = `${sr >= 0 ? "+" : "−"}${Math.abs(sr * 100).toFixed(1).replace(".", ",")} %`;
        const bPct = `${br >= 0 ? "+" : "−"}${Math.abs(br * 100).toFixed(1).replace(".", ",")} %`;
        const list = p.holdings.length ? p.holdings.slice(0, 6).join(", ") + (p.holdings.length > 6 ? "…" : "") : "efectivo";
        return (
          <g key={p.year} className={`tapestry-col ${sr >= 0 ? "up" : "down"} ${beat ? "beat" : "lag"}`}>
            <title>{`${p.year}: Estrategia ${sPct} vs SPY ${bPct} (${p.holdings.length} activas: ${list})`}</title>
            <rect className="tapestry-bar" x={x} y={topY} width={bw} height={barH} rx={2} />
            {Array.from({ length: hatchCount }, (_, h) => {
              const hy = topY + ((h + 0.5) / hatchCount) * barH;
              return <line key={h} className="tapestry-hatch" x1={x + 2} x2={x + bw - 2} y1={hy} y2={hy} />;
            })}
            {/* Marca del SPY en ese periodo */}
            <line className="tapestry-spy" x1={x - 2} x2={x + bw + 2} y1={yB} y2={yB} />
            <circle className="tapestry-spy-dot" cx={x + bw / 2} cy={yB} r={2.4} />
            <text x={x + bw / 2} y={H - 5} textAnchor="middle" className="tapestry-year">
              {p.year}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
