import { useMemo } from "react";

import { hash, rng } from "./core";

export type SealTone = "ok" | "bad" | "warn" | "muted";

/**
 * Sello grabado, como los de un timbre fiscal: borde dentado y una roseta propia que sale de
 * la semilla (cada documento tiene la suya). El color dice cómo terminó su lectura.
 */
export default function Seal({ seed, tone, size = 56, title }: { seed: string; tone: SealTone; size?: number; title: string }) {
  const paths = useMemo(() => {
    const r = rng(hash(seed));
    const petals = 5 + Math.floor(r() * 7);
    const twist = r() * Math.PI * 2;
    const ring = (base: number, amp: number, k: number, phase: number, loop: number) => {
      let d = "";
      for (let s = 0; s <= 240; s++) {
        const a = (s / 240) * Math.PI * 2;
        const rad = base + amp * Math.sin(k * a + phase);
        const x = 50 + rad * Math.cos(a) + loop * Math.cos((k * 3 + 1) * a);
        const y = 50 + rad * Math.sin(a) + loop * Math.sin((k * 3 + 1) * a);
        d += `${s ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
      }
      return `${d}Z`;
    };
    return {
      // Borde dentado: 32 dientes, como un sello postal.
      edge: ring(46, 1.6, 32, 0, 0),
      rings: [0, 1, 2, 3].map((i) => ring(14 + i * 7, 2 + i * 0.6, petals, twist + i * 0.5, 1.1 + r())),
    };
  }, [seed]);

  return (
    <svg className={`seal ${tone}`} viewBox="0 0 100 100" width={size} height={size} role="img" aria-label={title}>
      <title>{title}</title>
      <path className="seal-edge" d={paths.edge} />
      {paths.rings.map((d, i) => (
        <path key={i} className="seal-ring" d={d} />
      ))}
    </svg>
  );
}
