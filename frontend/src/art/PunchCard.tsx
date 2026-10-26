/**
 * Tarjeta perforada del screener: una fila por empresa, una columna por criterio. Un agujero
 * lleno es un criterio que se cumple; un anillo, uno que no; un guion, un dato que falta. La
 * forma general de la tarjeta dice de un vistazo qué empresas pasan el filtro completo.
 */
export interface PunchRow {
  symbol: string;
  cells: (boolean | null)[];
}

const COL = 30;
const ROW = 22;
const LEFT = 70;
const TOP = 16;

export default function PunchCard({ rows, columns, label }: { rows: PunchRow[]; columns: string[]; label: string }) {
  if (rows.length === 0 || columns.length === 0) return null;
  const w = LEFT + columns.length * COL + 16;
  const h = TOP + rows.length * ROW + 8;

  return (
    <svg className="punch" viewBox={`0 0 ${w} ${h}`} style={{ maxWidth: w * 1.4 }} role="img" aria-label={label}>
      <rect className="punch-card" x={2} y={2} width={w - 4} height={h - 4} rx={8} />
      {rows.map((r, i) => {
        const y = TOP + i * ROW + ROW / 2;
        const all = r.cells.every((c) => c === true);
        return (
          <g key={r.symbol} className={all ? "punch-row pass" : "punch-row"}>
            <text x={14} y={y} dominantBaseline="middle">
              {r.symbol}
            </text>
            {r.cells.map((c, j) => {
              const x = LEFT + j * COL + COL / 2;
              const tip = `${r.symbol} · ${columns[j]}: ${c === null ? "sin dato" : c ? "cumple" : "no cumple"}`;
              return c === null ? (
                <line key={j} className="punch-none" x1={x - 4} x2={x + 4} y1={y} y2={y}>
                  <title>{tip}</title>
                </line>
              ) : (
                <circle key={j} className={c ? "punch-hole" : "punch-miss"} cx={x} cy={y} r={6}>
                  <title>{tip}</title>
                </circle>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}
