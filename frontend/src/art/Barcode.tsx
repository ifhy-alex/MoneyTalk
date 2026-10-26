/**
 * El mes como código de barras: un trazo grabado por movimiento. La posición es el día, el
 * largo es el monto en escala logarítmica (un café, un súper y un alquiler se leen los tres). Los ingresos suben
 * desde la línea media y los gastos bajan; lo que falta categorizar va en dorado.
 */
export interface Mark {
  date: string; // YYYY-MM-DD
  amount: number; // en colones; positivo = ingreso
  pending: boolean;
}

const W = 1000;
const H = 90;
const MID = H * 0.42; // los ingresos son pocos y grandes: más lugar para los gastos

export default function Barcode({ marks, label }: { marks: Mark[]; label: string }) {
  if (marks.length === 0) return null;
  const days = marks.map((m) => Date.parse(m.date));
  const first = Math.min(...days);
  const last = Math.max(...days);
  // Al menos un mes de ancho, aunque haya pocos días con datos.
  const span = Math.max(last - first, 29 * 86_400_000);
  // Ingresos y gastos se escalan cada uno contra su máximo: dos salarios no achican todo el resto.
  const mag = (v: number) => Math.log10(1 + Math.abs(v));
  const peak = (sign: number) => Math.max(1, ...marks.filter((m) => Math.sign(m.amount) === sign).map((m) => mag(m.amount)));
  const maxIn = peak(1);
  const maxOut = peak(-1);
  // Varios movimientos el mismo día se abren en abanico dentro de su franja.
  const perDay = new Map<number, number>();

  const lines = marks.map((m, i) => {
    const t = Date.parse(m.date);
    const nth = perDay.get(t) ?? 0;
    perDay.set(t, nth + 1);
    const dayWidth = (86_400_000 / span) * (W - 20);
    const x = 10 + ((t - first) / span) * (W - 20) + ((nth % 6) - 2.5) * Math.min(3.2, dayWidth / 6);
    const max = m.amount >= 0 ? maxIn : maxOut;
    const len = Math.max(5, (mag(m.amount) / max) ** 3 * (m.amount >= 0 ? MID - 6 : H - MID - 6));
    const y2 = m.amount >= 0 ? MID - len : MID + len;
    const tone = m.pending ? "pending" : m.amount >= 0 ? "in" : "out";
    return <line key={i} className={`bar-${tone}`} x1={x} x2={x} y1={MID} y2={y2} />;
  });

  return (
    <svg className="barcode" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={label}>
      <line className="barcode-axis" x1={0} x2={W} y1={MID} y2={MID} />
      {lines}
    </svg>
  );
}
