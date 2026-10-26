/**
 * Abanico de opciones: todas salen del mismo punto (lo que ponés hoy) y cada una crece a su
 * rendimiento neto anual compuesto durante el plazo. Las que más rinden se abren más arriba;
 * una con rendimiento real negativo cae bajo la línea de partida.
 */
export interface Blade {
  label: string;
  rate: number; // rendimiento anual neto (0.05 = 5 %)
}

const W = 1000;
const H = 220;
const LEFT = 20;
const RIGHT = 760;

export default function Fan({
  blades,
  years = 5,
  label,
  latent = false,
}: {
  blades: Blade[];
  years?: number;
  label: string;
  latent?: boolean;
}) {
  if (blades.length === 0) return null;
  const finals = blades.map((b) => (1 + b.rate) ** years);
  const hi = Math.max(1.02, ...finals);
  const lo = Math.min(0.98, ...finals);
  const y = (v: number) => 14 + ((hi - v) / (hi - lo)) * (H - 28);
  const order = blades.map((b, i) => ({ b, f: finals[i]!, ly: 0 })).sort((a, b) => b.f - a.f);
  // Etiquetas al final de cada curva, separadas al menos 16 px para que no se encimen.
  order.forEach((o, i) => {
    o.ly = Math.max(y(o.f), i ? order[i - 1]!.ly + 16 : 0);
  });

  return (
    <svg className={`fan${latent ? " latent" : ""}`} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <line className="fan-base" x1={LEFT} x2={RIGHT} y1={y(1)} y2={y(1)} />
      {order.map(({ b, f, ly }) => {
        let d = "";
        for (let s = 0; s <= 40; s++) {
          const t = (s / 40) * years;
          d += `${s ? "L" : "M"}${(LEFT + (s / 40) * (RIGHT - LEFT)).toFixed(1)},${y((1 + b.rate) ** t).toFixed(1)}`;
        }
        const pct = `${b.rate >= 0 ? "+" : "−"}${Math.abs(b.rate * 100).toFixed(2).replace(".", ",")} % al año`;
        return (
          <g key={b.label} className={f >= 1 ? "blade up" : "blade down"}>
            <title>{`${b.label}: ${pct}`}</title>
            {/* Ecos tenues bajo la curva: el sombreado de grabado. */}
            {[3, 6].map((o) => (
              <path key={o} className="blade-echo" d={d} transform={`translate(0 ${o})`} />
            ))}
            <path className="blade-line" d={d} />
            <text x={RIGHT + 10} y={ly} dominantBaseline="middle">
              {b.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
