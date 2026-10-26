/**
 * Diapasón del presupuesto mensual: todas las categorías con presupuesto se tienden como
 * cuerdas paralelas en un mismo bastidor. Una aguja vertical dorada marca por dónde va el
 * calendario del mes; si la vibración grabada de una cuerda pasa a la derecha de la aguja,
 * esa categoría va gastando más rápido que el calendario.
 */
export interface HarpString {
  category: string;
  ratio: number; // gastado / presupuestado
}

const W = 1000;
const LEFT = 160;
const RIGHT = 930;
const ROW = 24;
const TOP = 22;

export default function BudgetHarp({
  strings,
  calendarRatio,
  label,
}: {
  strings: HarpString[];
  /** Fracción transcurrida del mes (0…1). */
  calendarRatio: number;
  label: string;
}) {
  if (strings.length === 0) return null;
  const h = TOP + strings.length * ROW + 18;
  const span = RIGHT - LEFT;
  const calX = LEFT + Math.max(0, Math.min(1, calendarRatio)) * span;

  return (
    <svg className="budget-harp" viewBox={`0 0 ${W} ${h}`} role="img" aria-label={label}>
      {/* Tope del 100 % y aguja del día del mes */}
      <line className="harp-limit" x1={RIGHT} x2={RIGHT} y1={TOP - 8} y2={h - 14} />
      <line className="harp-cal" x1={calX} x2={calX} y1={TOP - 10} y2={h - 12} />
      <circle className="harp-cal-dot" cx={calX} cy={TOP - 10} r={3} />
      <text x={calX} y={11} textAnchor="middle" className="harp-cal-lbl">
        hoy ({Math.round(calendarRatio * 100)} % del mes)
      </text>

      {strings.map((s, i) => {
        const y = TOP + i * ROW + ROW / 2;
        const r = Math.max(0, s.ratio);
        const clamped = Math.min(1, r);
        const endX = LEFT + clamped * span;
        const tone = r >= 1 ? "bad" : r >= 0.8 ? "warn" : r > calendarRatio + 0.1 ? "warn" : "ok";
        const amp = 0.8 + Math.min(1.5, r) ** 2 * 3.8;
        const freq = 4 + Math.min(1.5, r) * 14;

        const buildWave = (offsetY: number, ampScale: number) => {
          const steps = Math.max(8, Math.round((endX - LEFT) / 4));
          let d = "";
          for (let k = 0; k <= steps; k++) {
            const t = k / steps;
            const x = LEFT + (endX - LEFT) * t;
            const env = Math.sin(Math.PI * t);
            const wy = y + offsetY + amp * ampScale * env * Math.sin(t * freq * Math.PI * 2 + i);
            d += `${k ? "L" : "M"}${x.toFixed(1)},${wy.toFixed(2)}`;
          }
          return d;
        };

        return (
          <g key={s.category} className={`harp-row ${tone}`}>
            <title>{`${s.category}: ${Math.round(r * 100)} % usado`}</title>
            <text x={LEFT - 12} y={y} textAnchor="end" dominantBaseline="middle" className="harp-name">
              {s.category.length > 18 ? `${s.category.slice(0, 17)}…` : s.category}
            </text>
            <line className="harp-rest" x1={endX} x2={RIGHT} y1={y} y2={y} />
            {endX > LEFT && (
              <>
                <path className="harp-echo" d={buildWave(-2.2, 0.65)} />
                <path className="harp-echo" d={buildWave(2.2, 0.65)} />
                <path className="harp-ink" d={buildWave(0, 1)} />
              </>
            )}
            <circle className="harp-peg" cx={endX} cy={y} r={3} />
            <text x={RIGHT + 10} y={y} dominantBaseline="middle" className="harp-pct">
              {Math.round(r * 100)} %
            </text>
          </g>
        );
      })}
    </svg>
  );
}
