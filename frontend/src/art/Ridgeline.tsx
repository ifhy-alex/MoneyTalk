/**
 * Relieve de líneas, como el sombreado grabado de un billete: cada cresta es una serie de
 * precios, apilada sobre la anterior y tapando a la de atrás. Las series se ordenan por
 * rendimiento (la peor atrás, la mejor adelante) y el color dice si subió o bajó.
 */
export interface Ridge {
  values: number[];
  label: string;
}

const W = 1000;

const change = (v: number[]) => (v[v.length - 1]! - v[0]!) / Math.abs(v[0] || 1);

export default function Ridgeline({
  ridges,
  height = 180,
  label,
  sort = true,
}: {
  ridges: Ridge[];
  height?: number;
  label: string;
  sort?: boolean;
}) {
  const usable = ridges.filter((r) => r.values.length > 1);
  if (usable.length === 0) return null;
  if (sort) usable.sort((a, b) => change(a.values) - change(b.values));
  const n = usable.length;
  const step = height / (n + 3.2);
  const lift = step * 3.2; // las crestas sobresalen sobre las de atrás y las tapan

  const paths = usable.map((r, i) => {
    const min = Math.min(...r.values), max = Math.max(...r.values), span = max - min || 1;
    const base = step * (i + 3.6);
    const pts = r.values.map((v, j) => [(j / (r.values.length - 1)) * W, base - ((v - min) / span) * lift] as const);
    const d = pts.map(([x, y], j) => `${j ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");
    // Ecos más tenues bajo la cresta: el sombreado de grabado.
    const echoes = [3, 6].map((o) => pts.map(([x, y], j) => `${j ? "L" : "M"}${x.toFixed(1)},${(y + o).toFixed(1)}`).join(""));
    const ch = change(r.values);
    const pct = `${ch >= 0 ? "+" : "−"}${Math.abs(ch * 100).toFixed(1).replace(".", ",")} %`;
    return { d, fill: `${d}L${W},${height}L0,${height}Z`, up: ch >= 0, echoes, key: r.label, title: `${r.label}: ${pct}` };
  });

  return (
    <svg
      className="ridgeline"
      viewBox={`0 0 ${W} ${height}`}
      preserveAspectRatio="none"
      style={{ height }}
      role="img"
      aria-label={label}
    >
      {paths.map((p) => (
        <g key={p.key} className={p.up ? "up" : "down"}>
          <title>{p.title}</title>
          <path className="ridge-mask" d={p.fill} />
          {p.echoes.map((e, k) => (
            <path key={k} className="ridge-echo" d={e} style={{ opacity: 0.4 - k * 0.15 }} />
          ))}
          <path className="ridge-line" d={p.d} />
        </g>
      ))}
    </svg>
  );
}
