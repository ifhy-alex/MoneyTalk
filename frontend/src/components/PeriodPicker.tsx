// Selector de periodo propio: nunca queda vacío (el <input type="month"> nativo permite
// "borrar" y eso mandaba un periodo inválido a la API).

const MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

export type Granularity = "month" | "year";

export function currentPeriod(g: Granularity): string {
  const d = new Date();
  return g === "year" ? String(d.getFullYear()) : `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function shift(period: string, delta: number): string {
  if (period.length === 4) return String(Number(period) + delta);
  const [y, m] = period.split("-").map(Number) as [number, number];
  const total = y * 12 + (m - 1) + delta;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
}

export function periodLabel(period: string): string {
  if (period.length === 4) return period;
  const [y, m] = period.split("-").map(Number) as [number, number];
  return `${MONTHS[m - 1]} ${y}`;
}

interface Props {
  value: string;
  onChange: (period: string) => void;
  allowYear?: boolean;
}

export default function PeriodPicker({ value, onChange, allowYear = false }: Props) {
  const isYear = value.length === 4;
  const year = Number(value.slice(0, 4));
  const month = isYear ? 1 : Number(value.slice(5, 7));
  const thisYear = new Date().getFullYear();
  const years = Array.from({ length: 12 }, (_, i) => thisYear - 10 + i).filter((y) => y <= thisYear + 1);
  const atLatest = value >= currentPeriod(isYear ? "year" : "month");

  return (
    <div className="period-picker" role="group" aria-label="Periodo">
      {allowYear && (
        <div className="seg">
          <button className={!isYear ? "on" : ""} onClick={() => isYear && onChange(`${year}-${String(thisYear === year ? new Date().getMonth() + 1 : 12).padStart(2, "0")}`)}>
            Mes
          </button>
          <button className={isYear ? "on" : ""} onClick={() => !isYear && onChange(String(year))}>
            Año
          </button>
        </div>
      )}
      <button className="nav" aria-label="Periodo anterior" onClick={() => onChange(shift(value, -1))}>
        ‹
      </button>
      {!isYear && (
        <select aria-label="Mes" value={month} onChange={(e) => onChange(`${year}-${e.target.value.padStart(2, "0")}`)}>
          {MONTHS.map((m, i) => (
            <option key={m} value={i + 1}>
              {m}
            </option>
          ))}
        </select>
      )}
      <select
        aria-label="Año"
        value={year}
        onChange={(e) => onChange(isYear ? e.target.value : `${e.target.value}-${String(month).padStart(2, "0")}`)}
      >
        {years.map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </select>
      <button className="nav" aria-label="Periodo siguiente" disabled={atLatest} onClick={() => onChange(shift(value, 1))}>
        ›
      </button>
    </div>
  );
}
