/**
 * Rosa de los vientos del trimestre: un rayo por métrica. El anillo punteado del medio es
 * "igual que hace un año"; el rayo sale hacia afuera si la métrica creció y se mete hacia el
 * centro si cayó. La forma completa resume el trimestre de un vistazo.
 */
export interface Spoke {
  label: string;
  change: number | null; // variación interanual (0.12 = +12 %)
}

const C = 150;
const BASE = 72; // radio del anillo "sin cambios"
const REACH = 52; // cuánto se aleja un cambio de ±50 % o más

export default function Compass({
  spokes,
  label,
  latent = false,
}: {
  spokes: Spoke[];
  label: string;
  latent?: boolean;
}) {
  const usable = latent ? spokes : spokes.filter((s) => s.change !== null);
  if (usable.length < 3) return null;
  const n = usable.length;
  const pts = usable.map((s, i) => {
    const a = -Math.PI / 2 + (i / n) * Math.PI * 2;
    const changeVal = s.change ?? 0;
    const c = Math.max(-0.5, Math.min(0.5, changeVal)) / 0.5;
    const r = BASE + c * REACH;
    return { a, r, up: changeVal >= 0, s, changeVal };
  });
  const poly = pts.map((p) => `${(C + p.r * Math.cos(p.a)).toFixed(1)},${(C + p.r * Math.sin(p.a)).toFixed(1)}`).join(" ");

  return (
    // Margen a los costados: las etiquetas de los rayos horizontales salen del círculo.
    <svg className={`compass${latent ? " latent" : ""}`} viewBox="-56 -6 412 312" role="img" aria-label={label}>
      {[BASE - REACH, BASE - REACH / 2, BASE + REACH / 2, BASE + REACH].map((r) => (
        <circle key={r} className="compass-guide" cx={C} cy={C} r={r} />
      ))}
      <circle className="compass-zero" cx={C} cy={C} r={BASE} />
      <polygon className="compass-shape" points={poly} />
      {pts.map((p) => {
        const x0 = C + BASE * Math.cos(p.a), y0 = C + BASE * Math.sin(p.a);
        const x1 = C + p.r * Math.cos(p.a), y1 = C + p.r * Math.sin(p.a);
        const lx = C + (BASE + REACH + 16) * Math.cos(p.a), ly = C + (BASE + REACH + 16) * Math.sin(p.a);
        const pct = latent ? p.s.label : `${p.up ? "+" : "−"}${Math.abs(p.changeVal * 100).toFixed(0)} %`;
        return (
          <g key={p.s.label} className={latent ? "compass-spoke latent" : p.up ? "compass-spoke up" : "compass-spoke down"}>
            <title>{latent ? `${p.s.label} (en espera de consulta)` : `${p.s.label}: ${pct} frente a hace un año`}</title>
            <line x1={latent ? C + 18 * Math.cos(p.a) : x0} y1={latent ? C + 18 * Math.sin(p.a) : y0} x2={x1} y2={y1} />
            <circle cx={x1} cy={y1} r={latent ? 2.6 : 3.4} />
            <text
              x={lx}
              y={ly}
              textAnchor={Math.abs(Math.cos(p.a)) < 0.2 ? "middle" : Math.cos(p.a) > 0 ? "start" : "end"}
              dominantBaseline="middle"
            >
              {pct}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
