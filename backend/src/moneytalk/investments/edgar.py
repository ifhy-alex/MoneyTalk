"""Estados financieros oficiales desde SEC EDGAR (XBRL "companyfacts").

Reglas de acceso de la SEC: User-Agent con nombre y correo de contacto, máximo 10
solicitudes por segundo. Las respuestas se cachean (cambian solo cuando hay un filing nuevo).

Cada métrica calculada guarda su procedencia: concepto XBRL, periodo y formulario.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.investments.providers.base import ProviderError
from moneytalk.models import MarketCache

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
CACHE_TTL = timedelta(days=1)

# Varias empresas reportan el mismo concepto con etiquetas distintas: se prueba en orden.
CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "net_income": ["NetIncomeLoss"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "short_term_debt": ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "eps_diluted": ["EarningsPerShareDiluted"],
}


@dataclass(frozen=True)
class FactValue:
    concept: str
    value: float
    period_end: date
    fiscal_year: int
    form: str
    accession: str
    filed: date | None = None

    @property
    def citation(self) -> str:
        return f"SEC {self.form} FY{self.fiscal_year} ({self.concept}, acc. {self.accession})"


@dataclass(frozen=True)
class OfficialFundamentals:
    symbol: str
    cik: int
    entity: str
    fiscal_year: int
    values: dict[str, FactValue]
    previous: dict[str, FactValue]
    metrics: dict[str, float | None]
    provenance: dict[str, str]


def _entries(facts: dict[str, Any], concept: str) -> list[dict[str, Any]]:
    node = facts.get("facts", {}).get("us-gaap", {}).get(concept)
    if not node:
        return []
    units = node.get("units", {})
    entries: list[dict[str, Any]] = units.get("USD") or units.get("USD/shares") or []
    return entries


def _filed(e: dict[str, Any]) -> date | None:
    return date.fromisoformat(e["filed"]) if e.get("filed") else None


def _annual_series(
    facts: dict[str, Any], concept_names: list[str], as_of: date | None = None
) -> dict[int, FactValue]:
    """Valores anuales (10-K, periodo de ~12 meses), uno por año fiscal.

    Con `as_of`, solo usa lo *presentado* antes de esa fecha (point-in-time): evita el
    sesgo de anticipación en backtests, incluidas reexpresiones posteriores.
    """
    for concept in concept_names:
        by_year: dict[int, FactValue] = {}
        for e in _entries(facts, concept):
            if e.get("form") not in {"10-K", "10-K/A", "20-F"} or e.get("fp") != "FY":
                continue
            filed = _filed(e)
            if as_of and (filed is None or filed > as_of):
                continue
            end = date.fromisoformat(e["end"])
            if "start" in e:
                days = (end - date.fromisoformat(e["start"])).days
                if not 330 <= days <= 400:
                    continue  # descartar trimestres incluidos en el 10-K
            # El año del periodo (no el "fy" del filing, que se repite en comparativos).
            year = end.year
            fv = FactValue(concept, float(e["val"]), end, year, e["form"], e.get("accn", ""), filed)
            if year not in by_year or fv.accession >= by_year[year].accession:
                by_year[year] = fv
        if by_year:
            return by_year
    return {}


def quarterly_series(facts: dict[str, Any], concept_names: list[str]) -> dict[date, FactValue]:
    """Valores de 10-Q: flujos de ~3 meses o saldos al cierre del trimestre."""
    for concept in concept_names:
        by_end: dict[date, FactValue] = {}
        for e in _entries(facts, concept):
            if e.get("form") not in {"10-Q", "10-Q/A"}:
                continue
            end = date.fromisoformat(e["end"])
            if "start" in e and not 80 <= (end - date.fromisoformat(e["start"])).days <= 100:
                continue  # descartar acumulados de 6 y 9 meses
            fv = FactValue(
                concept, float(e["val"]), end, end.year, e["form"], e.get("accn", ""), _filed(e)
            )
            if end not in by_end or fv.accession >= by_end[end].accession:
                by_end[end] = fv
        if by_end:
            return by_end
    return {}


def compute_official(
    symbol: str, cik: int, facts: dict[str, Any], as_of: date | None = None
) -> OfficialFundamentals:
    series = {k: _annual_series(facts, v, as_of) for k, v in CONCEPTS.items()}
    years = sorted(series["revenue"] or series["net_income"])
    if not years:
        raise ProviderError(f"EDGAR: {symbol} no tiene datos anuales en us-gaap")
    fy = years[-1]
    cur = {k: s[fy] for k, s in series.items() if fy in s}
    prev = {k: s[fy - 1] for k, s in series.items() if fy - 1 in s}

    def v(key: str, src: dict[str, FactValue] = cur) -> float | None:
        return src[key].value if key in src else None

    revenue, net_income, equity = v("revenue"), v("net_income"), v("equity")
    debt_parts = [x for x in (v("long_term_debt"), v("short_term_debt")) if x is not None]
    debt = sum(debt_parts) if debt_parts else None
    ocf, capex = v("operating_cash_flow"), v("capex")
    prev_revenue = v("revenue", prev)
    gross, operating = v("gross_profit"), v("operating_income")

    metrics: dict[str, float | None] = {
        "roe": net_income / equity if net_income is not None and equity else None,
        "debt_to_equity": debt / equity if debt is not None and equity else None,
        "free_cash_flow": ocf - capex if ocf is not None and capex is not None else ocf,
        "revenue_growth": (revenue / prev_revenue - 1) if revenue and prev_revenue else None,
        "gross_margin": gross / revenue if gross is not None and revenue else None,
        "operating_margin": operating / revenue if operating is not None and revenue else None,
        "net_margin": net_income / revenue if net_income is not None and revenue else None,
        "eps_diluted": v("eps_diluted"),
    }
    deps = {
        "eps_diluted": ["eps_diluted"],
        "roe": ["net_income", "equity"],
        "debt_to_equity": ["long_term_debt", "short_term_debt", "equity"],
        "free_cash_flow": ["operating_cash_flow", "capex"],
        "revenue_growth": ["revenue"],
        "gross_margin": ["gross_profit", "revenue"],
        "operating_margin": ["operating_income", "revenue"],
        "net_margin": ["net_income", "revenue"],
    }
    provenance = {
        m: "; ".join(cur[d].citation for d in deps[m] if d in cur)
        for m, val in metrics.items()
        if val is not None
    }
    return OfficialFundamentals(
        symbol=symbol,
        cik=cik,
        entity=str(facts.get("entityName", symbol)),
        fiscal_year=fy,
        values=cur,
        previous=prev,
        metrics=metrics,
        provenance=provenance,
    )


def _slim_facts(facts: dict[str, Any]) -> dict[str, Any]:
    """companyfacts pesa varios MB: se guardan solo los conceptos que usamos."""
    wanted = {c for names in CONCEPTS.values() for c in names}
    gaap = facts.get("facts", {}).get("us-gaap", {})
    return {
        "entityName": facts.get("entityName"),
        "facts": {"us-gaap": {k: v for k, v in gaap.items() if k in wanted}},
    }


class EdgarClient:
    def __init__(self, db: Session, user_agent: str, http: httpx.Client | None = None) -> None:
        if "@" not in user_agent:
            raise ProviderError("SEC_USER_AGENT debe incluir un correo de contacto")
        self._db = db
        self._http = http or httpx.Client(timeout=30, headers={"User-Agent": user_agent})
        self._last = 0.0

    def _get_json(self, url: str) -> Any:
        wait = 0.15 - (time.monotonic() - self._last)  # < 10 req/s
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        try:
            resp = self._http.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"EDGAR: {type(exc).__name__}") from exc
        return resp.json()

    def _cached(
        self, symbol: str, key: str, url: str, transform: Callable[[Any], Any] | None = None
    ) -> Any:

        row = self._db.scalar(
            select(MarketCache).where(
                MarketCache.provider == "sec",
                MarketCache.kind == "edgar",
                MarketCache.symbol == symbol,
                MarketCache.cache_key == key,
            )
        )
        if row and datetime.now(UTC) - row.fetched_at < CACHE_TTL:
            return row.payload
        payload = self._get_json(url)
        if transform:
            payload = transform(payload)
        if row is None:
            row = MarketCache(provider="sec", kind="edgar", symbol=symbol, cache_key=key)
            self._db.add(row)
        row.payload = payload
        row.fetched_at = datetime.now(UTC)
        self._db.commit()
        return payload

    def cik_for(self, symbol: str) -> int:
        table: dict[str, int] = self._cached(
            "*",
            "tickers",
            TICKERS_URL,
            lambda raw: {e["ticker"].upper(): int(e["cik_str"]) for e in raw.values()},
        )
        if symbol.upper() in table:
            return table[symbol.upper()]
        raise ProviderError(
            f"EDGAR: {symbol} no está registrado en la SEC (¿empresa no estadounidense?)"
        )

    def company_facts(self, symbol: str) -> tuple[int, dict[str, Any]]:
        symbol = symbol.upper()
        cik = self.cik_for(symbol)
        return cik, self._cached(symbol, "facts", FACTS_URL.format(cik=cik), _slim_facts)

    def official(self, symbol: str) -> OfficialFundamentals:
        cik, facts = self.company_facts(symbol)
        return compute_official(symbol.upper(), cik, facts)
