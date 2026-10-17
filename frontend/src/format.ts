const formatters: Record<string, Intl.NumberFormat> = {};

export function money(value: string | number, currency: string): string {
  const key = currency;
  formatters[key] ??= new Intl.NumberFormat("es-CR", {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "CRC" ? 0 : 2,
  });
  return formatters[key].format(Number(value));
}

export function pct(value: number | string | null | undefined, digits = 1): string {
  if (value === null || value === undefined || value === "") return "—";
  return `${(Number(value) * 100).toFixed(digits)} %`;
}

export function num(value: number | string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === "") return "—";
  return Number(value).toLocaleString("es-CR", { maximumFractionDigits: digits });
}

export function shortDate(iso: string): string {
  return new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString("es-CR", {
    day: "2-digit",
    month: "short",
  });
}

export function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
