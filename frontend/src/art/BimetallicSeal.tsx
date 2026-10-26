/**
 * Sello bimetálico CRC ↔ USD: dos rosetas guilloché entrelazadas sobre un fiel de balanza.
 * El radio y el número de anillos grabados de cada moneda responden a su peso real en el gasto
 * del periodo (esmeralda/tinta para colones, dorado para dólares convertidos al tipo de cambio).
 */
export interface CurrencyShare {
  code: string;
  valueCrc: number;
  originalLabel: string;
}

function guillocheCircle(cx: number, cy: number, baseR: number, amp: number, petals: number, phase: number): string {
  const steps = 200;
  let d = "";
  for (let s = 0; s <= steps; s++) {
    const a = (s / steps) * Math.PI * 2;
    const r = baseR + amp * Math.sin(petals * a + phase) + 0.9 * Math.cos((petals * 2 + 1) * a);
    const x = cx + r * Math.cos(a);
    const y = cy + r * Math.sin(a);
    d += `${s ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
  }
  return `${d}Z`;
}

export default function BimetallicSeal({
  items,
  label,
}: {
  items: CurrencyShare[];
  label: string;
}) {
  const total = items.reduce((a, x) => a + x.valueCrc, 0);
  if (total <= 0) return null;

  const crcItem = items.find((i) => i.code === "CRC") ?? { code: "CRC", valueCrc: 0, originalLabel: "₡0" };
  const usdItem = items.find((i) => i.code === "USD") ?? { code: "USD", valueCrc: 0, originalLabel: "USD 0" };
  const crcShare = crcItem.valueCrc / total;
  const usdShare = usdItem.valueCrc / total;

  // El radio refleja la participación, con un mínimo para que la moneda menor siempre tenga presencia de sello.
  const rCrc = 28 + crcShare * 36;
  const rUsd = 28 + usdShare * 36;
  const cxCrc = 128;
  const cxUsd = 252;
  const cy = 92;

  // Inclinación leve de la barra de equilibrio según qué moneda pesa más.
  const tilt = (usdShare - crcShare) * 10;

  return (
    <svg className="bimetallic" viewBox="0 0 380 190" role="img" aria-label={label}>
      {/* Fiel y travesaño de la balanza */}
      <line className="bimet-axis" x1={40} x2={340} y1={cy - tilt} y2={cy + tilt} />
      <polygon className="bimet-fulcrum" points={`190,${cy - 8} 184,${cy + 8} 196,${cy + 8}`} />

      {/* Sello CRC (izquierda) */}
      <g className="bimet-coin crc">
        <title>{`CRC: ${Math.round(crcShare * 100)} % (${crcItem.originalLabel})`}</title>
        {[0, 1, 2, 3, 4].map((k) => {
          const r = rCrc * (0.42 + k * 0.14);
          return <path key={k} className="bimet-ring" d={guillocheCircle(cxCrc, cy - tilt * 0.35, r, 1.4 + k * 0.3, 8, k * 0.4)} />;
        })}
        <text x={cxCrc} y={cy - tilt * 0.35 - 2} textAnchor="middle" dominantBaseline="middle" className="bimet-sym">
          ₡
        </text>
        <text x={cxCrc} y={cy - tilt * 0.35 + 14} textAnchor="middle" dominantBaseline="middle" className="bimet-pct">
          {Math.round(crcShare * 100)} %
        </text>
        <text x={cxCrc} y={168} textAnchor="middle" className="bimet-caption">
          Colones · {crcItem.originalLabel}
        </text>
      </g>

      {/* Sello USD (derecha) */}
      <g className={`bimet-coin usd${usdShare === 0 ? " empty" : ""}`}>
        <title>{`USD: ${Math.round(usdShare * 100)} % (${usdItem.originalLabel})`}</title>
        {[0, 1, 2, 3, 4].map((k) => {
          const r = rUsd * (0.42 + k * 0.14);
          return <path key={k} className="bimet-ring" d={guillocheCircle(cxUsd, cy + tilt * 0.35, r, 1.4 + k * 0.3, 10, k * 0.5)} />;
        })}
        <text x={cxUsd} y={cy + tilt * 0.35 - 2} textAnchor="middle" dominantBaseline="middle" className="bimet-sym">
          $
        </text>
        <text x={cxUsd} y={cy + tilt * 0.35 + 14} textAnchor="middle" dominantBaseline="middle" className="bimet-pct">
          {Math.round(usdShare * 100)} %
        </text>
        <text x={cxUsd} y={168} textAnchor="middle" className="bimet-caption">
          Dólares · {usdItem.originalLabel}
        </text>
      </g>
    </svg>
  );
}
