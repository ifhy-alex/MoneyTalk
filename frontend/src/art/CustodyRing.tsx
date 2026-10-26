/**
 * Rueda de custodia guilloché: cada posición o segmento ocupa un arco proporcional a su peso
 * en el portafolio, relleno con ondas concéntricas grabadas como el borde de un billete.
 * En modo posiciones, el color y la frecuencia del grabado reflejan la ganancia o pérdida
 * no realizada; en modo distribución (sector, país, tipo), alterna densidades de tinta.
 */
export interface CustodySlice {
  label: string;
  sub?: string;
  weight: number; // 0…1
  change?: number | null; // ganancia/pérdida relativa (ej. 0.14 = +14 %)
}

const C = 130;
const R_IN = 46;
const R_OUT = 96;

function polar(r: number, a: number): [number, number] {
  return [C + r * Math.cos(a), C + r * Math.sin(a)];
}

/** Arco guilloché entre a0 y a1 al radio r, con ondulación radial. */
function wavyArc(r: number, a0: number, a1: number, amp: number, freq: number, phase: number): string {
  const span = Math.max(0.01, a1 - a0);
  const steps = Math.max(12, Math.round(span * 48));
  let d = "";
  for (let s = 0; s <= steps; s++) {
    const t = s / steps;
    const a = a0 + span * t;
    // Se suaviza en los bordes del segmento para que las ondas no se salgan del corte radial.
    const env = Math.sin(Math.PI * t);
    const rad = r + amp * env * Math.sin(freq * a + phase);
    const [x, y] = polar(rad, a);
    d += `${s ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
  }
  return d;
}

export default function CustodyRing({
  slices,
  totalLabel,
  centerTop,
  centerBottom,
  compact = false,
}: {
  slices: CustodySlice[];
  totalLabel: string;
  centerTop?: string;
  centerBottom?: string;
  compact?: boolean;
}) {
  const clean = slices.filter((s) => s.weight > 0).sort((a, b) => b.weight - a.weight);
  if (clean.length === 0) return null;
  const sum = clean.reduce((acc, s) => acc + s.weight, 0) || 1;
  const gap = clean.length > 1 ? 0.028 : 0;
  const avail = Math.PI * 2 - gap * clean.length;

  let cursor = -Math.PI / 2;
  const arcs = clean.map((s, idx) => {
    const span = Math.max(0.04, (s.weight / sum) * avail);
    const a0 = cursor + gap / 2;
    const a1 = a0 + span;
    cursor = a1 + gap / 2;
    const mid = (a0 + a1) / 2;
    const tone =
      s.change === undefined || s.change === null
        ? idx === 0
          ? "lead"
          : idx % 2 === 1
            ? "alt"
            : "ink"
        : s.change >= 0
          ? "up"
          : "down";
    const intensity = s.change !== undefined && s.change !== null ? Math.min(1, Math.abs(s.change) * 2.5) : 0.35;
    const rings = compact ? 5 : 7;
    const lines = Array.from({ length: rings }, (_, k) => {
      const r = R_IN + 5 + ((R_OUT - R_IN - 10) * k) / (rings - 1);
      const amp = (compact ? 1.1 : 1.5) + intensity * 1.6;
      const freq = 14 + (idx % 4) * 4 + (k % 2) * 6;
      return wavyArc(r, a0, a1, amp, freq, k * 0.9 + idx);
    });

    // Marco del sector
    const [ix0, iy0] = polar(R_IN, a0);
    const [ox0, oy0] = polar(R_OUT, a0);
    const [ox1, oy1] = polar(R_OUT, a1);
    const [ix1, iy1] = polar(R_IN, a1);
    const large = span > Math.PI ? 1 : 0;
    const border =
      clean.length === 1
        ? ""
        : `M${ix0.toFixed(2)},${iy0.toFixed(2)}L${ox0.toFixed(2)},${oy0.toFixed(2)}A${R_OUT},${R_OUT} 0 ${large} 1 ${ox1.toFixed(2)},${oy1.toFixed(2)}L${ix1.toFixed(2)},${iy1.toFixed(2)}A${R_IN},${R_IN} 0 ${large} 0 ${ix0.toFixed(2)},${iy0.toFixed(2)}Z`;

    const [lx, ly] = polar(R_OUT + (compact ? 14 : 18), mid);
    const pctText = `${Math.round((s.weight / sum) * 100)} %`;
    const chText =
      s.change !== undefined && s.change !== null
        ? ` · ${s.change >= 0 ? "+" : "−"}${Math.abs(s.change * 100).toFixed(1).replace(".", ",")} %`
        : "";

    return {
      s,
      idx,
      tone,
      lines,
      border,
      mid,
      lx,
      ly,
      pctText,
      title: `${s.label}${s.sub ? ` (${s.sub})` : ""}: ${pctText} del total${chText}`,
      showLabel: !compact ? s.weight / sum >= 0.06 || idx < 5 : s.weight / sum >= 0.12 || idx < 3,
    };
  });

  return (
    <svg
      className={`custody-ring${compact ? " compact" : ""}`}
      viewBox={compact ? "0 0 260 260" : "-36 -8 332 276"}
      role="img"
      aria-label={totalLabel}
    >
      <circle className="custody-guide" cx={C} cy={C} r={R_IN - 4} />
      <circle className="custody-guide" cx={C} cy={C} r={R_OUT + 4} />
      {clean.length === 1 && (
        <>
          <circle className="custody-border" cx={C} cy={C} r={R_IN} />
          <circle className="custody-border" cx={C} cy={C} r={R_OUT} />
        </>
      )}
      {arcs.map((a) => (
        <g key={a.s.label} className={`custody-slice ${a.tone}`}>
          <title>{a.title}</title>
          {a.border && <path className="custody-border" d={a.border} />}
          {a.lines.map((d, k) => (
            <path key={k} className="custody-wave" d={d} />
          ))}
          {a.showLabel && (
            <text
              x={a.lx}
              y={a.ly}
              textAnchor={Math.abs(Math.cos(a.mid)) < 0.22 ? "middle" : Math.cos(a.mid) > 0 ? "start" : "end"}
              dominantBaseline="middle"
              className="custody-label"
            >
              {a.s.label} <tspan className="custody-pct">{a.pctText}</tspan>
            </text>
          )}
        </g>
      ))}
      {centerTop && (
        <text x={C} y={centerBottom ? C - 5 : C + 2} textAnchor="middle" dominantBaseline="middle" className="custody-center-top">
          {centerTop}
        </text>
      )}
      {centerBottom && (
        <text x={C} y={C + 12} textAnchor="middle" dominantBaseline="middle" className="custody-center-sub">
          {centerBottom}
        </text>
      )}
    </svg>
  );
}
