import { Link } from "react-router-dom";

import { useApi } from "../hooks";
import type { Rate } from "../types-finance";
import type { Instrument, MarketOverview } from "../types-market";

// Orden de la cinta: lo más seguido primero. Los ETF amplios llevan una marca dorada
// porque son la referencia más usada para invertir a largo plazo (no es una recomendación).
const ORDER = [
  "^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX", "^TNX",
  "VOO", "VTI", "QQQ", "VXUS", "BND", "SCHD",
  "NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "META", "BRK-B", "TSLA",
  "^STOXX50E", "^FTSE", "^N225", "^HSI",
  "GC=F", "CL=F", "BTC-USD", "DX-Y.NYB",
];
const SHORT: Record<string, string> = {
  "^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow Jones", "^RUT": "Russell 2000", "^VIX": "VIX",
  "^TNX": "Bono 10A", "^STOXX50E": "Euro Stoxx", "^FTSE": "FTSE 100", "^N225": "Nikkei", "^HSI": "Hang Seng",
  "GC=F": "Oro", "CL=F": "Petróleo", "BTC-USD": "Bitcoin", "DX-Y.NYB": "Dólar (DXY)", "BRK-B": "BRK.B",
};
const ETFS = new Set(["VOO", "VTI", "QQQ", "VXUS", "BND", "SCHD"]);

function Item({ i }: { i: Instrument }) {
  const ch = i.change_1d;
  const cls = ch === null ? "flat" : ch >= 0 ? "up" : "down";
  return (
    <Link to="/mercado" className={`tick ${ETFS.has(i.symbol) ? "etf" : ""}`} title={`${i.name} · ${i.as_of}`}>
      <span className="t-name">{SHORT[i.symbol] ?? i.symbol}</span>
      <span className="t-val">
        {i.symbol === "^TNX" ? `${i.last.toFixed(2)}%` : i.last.toLocaleString("es-CR", { maximumFractionDigits: 2 })}
      </span>
      <span className={`t-ch ${cls}`}>
        {ch === null ? "—" : `${ch >= 0 ? "▲" : "▼"} ${Math.abs(ch * 100).toFixed(2)}%`}
      </span>
    </Link>
  );
}

/** Cinta superior en movimiento continuo: tipo de cambio fijo a la izquierda y mercado rodando. */
export default function Ticker() {
  const fx = useApi<Rate | null>("/fx/latest");
  const market = useApi<MarketOverview>("/market/overview");
  const all = new Map((market.data?.groups.flatMap((g) => g.items) ?? []).map((i) => [i.symbol, i]));
  const items = ORDER.map((s) => all.get(s)).filter((i): i is Instrument => Boolean(i));
  const seconds = Math.max(items.length * 3.2, 30);

  return (
    <div className="ticker" role="region" aria-label="Indicadores de mercado">
      <div className="tick fx pinned" title={fx.data ? `Fuente: ${fx.data.source} · ${fx.data.rate_date}` : undefined}>
        <span className="t-name">USD/CRC</span>
        <span className="t-val">{fx.data ? `₡${Number(fx.data.sell).toFixed(2)}` : "—"}</span>
        {fx.data && <span className="t-src">{fx.data.source === "BCCR" ? "BCCR" : "mercado"}</span>}
      </div>
      <div className="marquee">
        {items.length > 0 ? (
          <div className="marquee-track" style={{ animationDuration: `${seconds}s` }}>
            {[0, 1].map((copy) => (
              <div className="marquee-group" key={copy} aria-hidden={copy === 1}>
                {items.map((i) => (
                  <Item key={`${copy}-${i.symbol}`} i={i} />
                ))}
              </div>
            ))}
          </div>
        ) : (
          <span className="t-meta">{market.error ? "Mercado no disponible" : "Cargando mercado…"}</span>
        )}
      </div>
    </div>
  );
}
