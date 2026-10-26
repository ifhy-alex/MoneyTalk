/**
 * Regla vernier grabada para el panel lateral de un instrumento (ChartDrawer).
 * Ubica el precio actual frente a su máximo de 52 semanas, el recorrido de los últimos 3 meses
 * (spark) y su régimen frente a la media móvil de 200 sesiones (MM200).
 */
const W = 520;
const H = 68;
const LEFT = 28;
const RIGHT = 492;

export default function RangeRuler({
  last,
  from52wHigh,
  spark,
  aboveSma200,
  volatility1m,
  label,
}: {
  last: number;
  from52wHigh: number | null;
  spark: number[];
  aboveSma200: boolean | null;
  volatility1m: number | null;
  label: string;
}) {
  // Estimamos el techo de 52 semanas desde from52wHigh (que es <= 0, ej. -0.12 = 12 % debajo del máximo)
  const high52 =
    from52wHigh !== null && from52wHigh > -0.95 ? last / (1 + Math.min(0, from52wHigh)) : Math.max(last, ...spark);
  const sparkMin = spark.length > 0 ? Math.min(last, ...spark) : last * 0.85;
  const sparkMax = spark.length > 0 ? Math.max(last, ...spark) : high52;
  // Escala desde un piso razonable (el menor entre sparkMin y -35 % del máximo 52s) hasta el máximo de 52s
  const floor = Math.min(sparkMin * 0.98, high52 * 0.72);
  const span = Math.max(0.0001, high52 - floor);
  const xOf = (v: number) => LEFT + Math.max(0, Math.min(1, (v - floor) / span)) * (RIGHT - LEFT);

  const xLast = xOf(last);
  const xMin3m = xOf(sparkMin);
  const xMax3m = xOf(sparkMax);
  const ticks = 32;
  const volTicks = Math.max(1, Math.min(8, Math.round((volatility1m ?? 0.18) * 18)));

  return (
    <svg className="range-ruler" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      {/* Riel base y graduaciones de regla grabada */}
      <line className="ruler-rail" x1={LEFT} x2={RIGHT} y1={34} y2={34} />
      {Array.from({ length: ticks + 1 }, (_, i) => {
        const x = LEFT + (i / ticks) * (RIGHT - LEFT);
        const major = i % 8 === 0;
        const mid = i % 4 === 0;
        const h = major ? 9 : mid ? 6 : 3.5;
        return <line key={i} className={major ? "ruler-tick major" : "ruler-tick"} x1={x} x2={x} y1={34 - h} y2={34 + h} />;
      })}

      {/* Banda sombreada del rango de los últimos 3 meses */}
      <rect className="ruler-band-3m" x={xMin3m} y={26} width={Math.max(4, xMax3m - xMin3m)} height={16} rx={2} />

      {/* Ecos de volatilidad alrededor del cursor actual */}
      {Array.from({ length: volTicks }, (_, k) => {
        const dx = (k + 1) * 3.2;
        return (
          <g key={k} className="ruler-vol-echo" style={{ opacity: 0.45 - k * 0.05 }}>
            <line x1={Math.max(LEFT, xLast - dx)} x2={Math.max(LEFT, xLast - dx)} y1={24} y2={44} />
            <line x1={Math.min(RIGHT, xLast + dx)} x2={Math.min(RIGHT, xLast + dx)} y1={24} y2={44} />
          </g>
        );
      })}

      {/* Cursor del precio actual (diamante grabado) */}
      <polygon
        className={`ruler-cursor ${aboveSma200 === false ? "down" : "up"}`}
        points={`${xLast},19 ${xLast + 6},34 ${xLast},49 ${xLast - 6},34`}
      />

      {/* Etiquetas de los extremos */}
      <text x={LEFT} y={14} className="ruler-lbl">
        Mín. 3M ({sparkMin.toLocaleString("es-CR", { maximumFractionDigits: 2 })})
      </text>
      <text x={RIGHT} y={14} textAnchor="end" className="ruler-lbl">
        Máx. 52 sem. ({high52.toLocaleString("es-CR", { maximumFractionDigits: 2 })})
      </text>
      <text x={xLast} y={62} textAnchor={xLast > RIGHT - 70 ? "end" : xLast < LEFT + 70 ? "start" : "middle"} className="ruler-now">
        Hoy {from52wHigh !== null ? (from52wHigh > -0.005 ? "(en máximos)" : `(${(from52wHigh * 100).toFixed(1).replace(".", ",")} % vs máx.)`) : ""}
        {aboveSma200 !== null ? ` · ${aboveSma200 ? "▲ sobre MM200" : "▼ bajo MM200"}` : ""}
      </text>
    </svg>
  );
}
