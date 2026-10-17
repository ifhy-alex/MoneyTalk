import { useApi } from "../hooks";
import type { Rate } from "../types-finance";
import type { MarketOverview } from "../types-market";
import { Change } from "./ui";

const TICKER_SYMBOLS = ["^GSPC", "^IXIC", "^DJI", "^VIX", "^TNX", "GC=F", "CL=F", "BTC-USD"];
const SHORT: Record<string, string> = {
  "^GSPC": "S&P 500",
  "^IXIC": "Nasdaq",
  "^DJI": "Dow",
  "^VIX": "VIX",
  "^TNX": "UST 10A",
  "GC=F": "Oro",
  "CL=F": "WTI",
  "BTC-USD": "BTC",
};

/** Cinta superior: tipo de cambio y mercado, presente en todas las páginas. */
export default function Ticker() {
  const fx = useApi<Rate | null>("/fx/latest");
  const market = useApi<MarketOverview>("/market/overview");
  const items = market.data?.groups.flatMap((g) => g.items) ?? [];
  const bySymbol = new Map(items.map((i) => [i.symbol, i]));

  return (
    <div className="ticker" role="status" aria-label="Indicadores de mercado">
      <div className="tick fx" title={fx.data ? `Fuente: ${fx.data.source} · ${fx.data.rate_date}` : undefined}>
        <span className="t-name">USD/CRC</span>
        <span className="t-val">{fx.data ? `₡${Number(fx.data.sell).toFixed(2)}` : "—"}</span>
        {fx.data && <span className="muted small">{fx.data.source === "BCCR" ? "BCCR venta" : "mercado"}</span>}
      </div>
      {TICKER_SYMBOLS.map((s) => {
        const i = bySymbol.get(s);
        if (!i) return null;
        return (
          <div className="tick" key={s}>
            <span className="t-name">{SHORT[s]}</span>
            <span className="t-val">{i.last.toLocaleString("es-CR", { maximumFractionDigits: 2 })}</span>
            <Change value={i.change_1d} />
          </div>
        );
      })}
      <span className="t-meta">
        {market.data ? `Actualizado ${new Date(market.data.fetched_at).toLocaleTimeString("es-CR", { hour: "2-digit", minute: "2-digit" })}` : market.error ? "Mercado no disponible" : "Cargando mercado…"}
      </span>
    </div>
  );
}
