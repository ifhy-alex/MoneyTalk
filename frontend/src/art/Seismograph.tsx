import { useMemo } from "react";

import { hash, rng } from "./core";

/**
 * Sismógrafo del gasto: cada día es un temblor cuya amplitud es lo que se gastó. Los días en
 * que MoneyTalk detectó algo raro llevan una marca dorada, como un evento registrado.
 */
const W = 1000;
const H = 110;
const MID = H / 2;
const SAMPLES = 14; // oscilaciones por día

export default function Seismograph({
  days,
  marks,
  label,
}: {
  days: { date: string; spend: number }[];
  marks: string[]; // fechas YYYY-MM-DD con alertas
  label: string;
}) {
  const trace = useMemo(() => {
    if (days.length === 0) return "";
    const r = rng(hash(days.map((d) => d.date).join()));
    const max = Math.sqrt(Math.max(...days.map((d) => d.spend), 1));
    const step = W / (days.length * SAMPLES);
    let d = `M0,${MID}`;
    days.forEach((day, i) => {
      const amp = (Math.sqrt(day.spend) / max) * (MID - 8);
      for (let s = 0; s < SAMPLES; s++) {
        // Envolvente: el temblor crece y se apaga dentro del día.
        const env = Math.sin((Math.PI * (s + 0.5)) / SAMPLES);
        const dir = s % 2 ? 1 : -1;
        const y = MID + dir * amp * env * (0.55 + r() * 0.45);
        d += `L${((i * SAMPLES + s + 1) * step).toFixed(1)},${y.toFixed(1)}`;
      }
    });
    return d;
  }, [days]);

  if (days.length === 0) return null;
  const marked = new Set(marks);
  const dayW = W / days.length;

  return (
    <svg className="seismo" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={label}>
      {days.map((d, i) =>
        marked.has(d.date) ? <rect key={d.date} className="seismo-event" x={i * dayW} y={0} width={dayW} height={H} /> : null,
      )}
      <line className="seismo-axis" x1={0} x2={W} y1={MID} y2={MID} />
      <path className="seismo-trace" d={trace} />
      {days.map((d, i) =>
        marked.has(d.date) ? (
          <line key={`m${d.date}`} className="seismo-mark" x1={(i + 0.5) * dayW} x2={(i + 0.5) * dayW} y1={2} y2={14} />
        ) : null,
      )}
    </svg>
  );
}
