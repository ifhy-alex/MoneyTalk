/**
 * Avance de un presupuesto como grabado de líneas. Mientras hay margen, las líneas corren
 * tranquilas; al acercarse al tope se aprietan y se agitan, y al pasarse se vuelven bermellón.
 * Sigue siendo una barra de progreso: lo grabado es lo gastado, lo tenue es lo disponible.
 */
const W = 240;
const H = 26;
const LINES = 5;

export default function TensionWave({ ratio, label }: { ratio: number; label: string }) {
  const r = Math.max(0, ratio);
  const tone = r >= 1 ? "bad" : r >= 0.8 ? "warn" : "ok";
  const filled = Math.min(1, r) * W;
  const amp = 0.6 + 4.2 * Math.min(1.4, r) ** 2;
  const freq = 2.5 + 10 * Math.min(1.4, r);
  const gap = H / (LINES + 1);

  const line = (i: number, from: number, to: number, wavy: boolean) => {
    let d = "";
    const steps = Math.max(2, Math.round((to - from) / 2));
    for (let s = 0; s <= steps; s++) {
      const x = from + ((to - from) * s) / steps;
      // La agitación crece hacia la derecha: la presión se siente al final del mes.
      const y = gap * (i + 1) + (wavy ? amp * (x / W) * Math.sin((x / W) * freq * Math.PI * 2 + i * 0.9) : 0);
      d += `${s ? "L" : "M"}${x.toFixed(1)},${y.toFixed(2)}`;
    }
    return d;
  };

  return (
    <svg className={`tension ${tone}`} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={label}>
      {Array.from({ length: LINES }, (_, i) => (
        <g key={i}>
          {filled < W && <path className="tension-rest" d={line(i, filled, W, false)} />}
          {filled > 0 && <path className="tension-ink" d={line(i, 0, filled, true)} />}
        </g>
      ))}
    </svg>
  );
}
