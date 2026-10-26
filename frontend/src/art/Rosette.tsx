import { useMemo } from "react";

import { hash, rng } from "./core";

interface Props {
  /** Semilla: cada meta tiene su propia roseta, estable entre sesiones. */
  seed: string;
  /** Avance 0…1 (o más). Cada anillo grabado es una parte del camino. */
  ratio: number;
  size?: number;
  emergency?: boolean;
  label: string;
}

const RINGS = 10;
const STEPS = 540;

/**
 * Roseta guilloché, como el sello de un billete. Los anillos grabados son lo ahorrado; los
 * punteados, lo que falta. Al llegar al 100 % la roseta entera se vuelve dorada.
 */
export default function Rosette({ seed, ratio, size = 168, emergency = false, label }: Props) {
  const rings = useMemo(() => {
    const r = rng(hash(seed));
    // El fondo de emergencia siempre tiene simetría de 8, como un escudo.
    const petals = emergency ? 8 : 5 + Math.floor(r() * 8);
    const twist = r() * Math.PI * 2;
    return Array.from({ length: RINGS }, (_, i) => {
      const base = 31 + i * 6.5; // el anillo interior deja lugar para el porcentaje
      const amp = 2.2 + i * 0.55;
      const loop = 1.6 + r() * 1.4;
      const k = petals * (i % 2 ? 3 : 2) + 1;
      const phase = twist + i * 0.35;
      let d = "";
      for (let s = 0; s <= STEPS; s++) {
        const a = (s / STEPS) * Math.PI * 2;
        const rad = base + amp * Math.sin(petals * a + phase);
        const x = 100 + rad * Math.cos(a) + loop * Math.cos(k * a);
        const y = 100 + rad * Math.sin(a) + loop * Math.sin(k * a);
        d += `${s ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
      }
      return d;
    });
  }, [seed, emergency]);

  const done = ratio >= 1;
  const engraved = Math.max(0, Math.min(1, ratio)) * RINGS;
  const pct = Math.round(Math.max(0, ratio) * 100);

  return (
    <svg
      className={`rosette${done ? " done" : ""}`}
      viewBox="0 0 200 200"
      width={size}
      height={size}
      role="img"
      aria-label={`${label}: ${pct} % ahorrado`}
    >
      {rings.map((d, i) => {
        const fill = Math.max(0, Math.min(1, engraved - i));
        return (
          <g key={i}>
            <path d={d} pathLength={1} className="rosette-guide" />
            {fill > 0 && (
              <path
                d={d}
                pathLength={1}
                className="rosette-ring"
                style={{ ["--len" as string]: fill, animationDelay: `${i * 70}ms` }}
              />
            )}
          </g>
        );
      })}
      <text x="100" y="104" textAnchor="middle" dominantBaseline="middle" className="rosette-pct">
        {pct}
        <tspan className="rosette-unit"> %</tspan>
      </text>
    </svg>
  );
}
