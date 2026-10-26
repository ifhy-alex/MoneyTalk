/**
 * Hilorama de las reglas: cada regla es un clavo a la izquierda y cada categoría uno a la
 * derecha; un hilo los une. Las categorías que reciben muchos hilos se ven como haces densos:
 * ahí es donde la app ya sabe clasificar sola.
 */
export interface Thread {
  from: string; // patrón de la regla
  to: string; // categoría
  active: boolean;
}

const W = 800;
const LEFT = 24;
const RIGHT = 560;
// Nombres largos se recortan para que entren también en celular; el completo va en el tooltip.
const short = (name: string) => (name.length > 18 ? `${name.slice(0, 17)}…` : name);

export default function StringArt({ threads, label }: { threads: Thread[]; label: string }) {
  if (threads.length === 0) return null;
  const counts = new Map<string, number>();
  threads.forEach((t) => counts.set(t.to, (counts.get(t.to) ?? 0) + 1));
  const cats = [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([name]) => name);
  const h = Math.max(180, Math.min(420, cats.length * 26 + 30));
  const catY = new Map(cats.map((c, i) => [c, 20 + ((h - 40) * (i + 0.5)) / cats.length]));
  // Los clavos de la izquierda se ordenan por categoría para que los hilos no se crucen de más.
  const ordered = [...threads].sort((a, b) => cats.indexOf(a.to) - cats.indexOf(b.to));
  const step = (h - 20) / ordered.length;

  return (
    <svg className="strings" viewBox={`0 0 ${W} ${h}`} role="img" aria-label={label}>
      {ordered.map((t, i) => {
        const y1 = 10 + step * (i + 0.5);
        const y2 = catY.get(t.to)!;
        const mid = (LEFT + RIGHT) / 2;
        return (
          <g key={`${t.from}-${i}`} className={t.active ? "thread" : "thread off"}>
            <title>{`${t.from} → ${t.to}`}</title>
            <path d={`M${LEFT},${y1.toFixed(1)} C${mid},${y1.toFixed(1)} ${mid},${y2.toFixed(1)} ${RIGHT},${y2.toFixed(1)}`} />
            <circle cx={LEFT} cy={y1} r={1.6} />
          </g>
        );
      })}
      {cats.map((c) => (
        <g key={c} className="strings-cat">
          <title>{`${c}: ${counts.get(c)} reglas`}</title>
          <circle cx={RIGHT} cy={catY.get(c)} r={3.2} />
          <text x={RIGHT + 12} y={catY.get(c)} dominantBaseline="middle">
            {short(c)} <tspan className="strings-count">{counts.get(c)}</tspan>
          </text>
        </g>
      ))}
    </svg>
  );
}
