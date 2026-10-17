"""Cambios relevantes en reportes trimestrales (10-Q) y su explicación en español con IA.

La tabla de cambios se calcula de forma determinista desde EDGAR y siempre se muestra.
La IA solo redacta a partir de esa tabla: no inventa cifras ni recomienda comprar o vender.
"""

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.ai import ClaudeClient
from moneytalk.investments.edgar import CONCEPTS, FactValue, quarterly_series
from moneytalk.investments.providers.base import ProviderError
from moneytalk.models import ReportSummary

LABELS = {
    "revenue": "Ingresos",
    "gross_profit": "Utilidad bruta",
    "operating_income": "Utilidad operativa",
    "net_income": "Utilidad neta",
    "eps_diluted": "UPA diluida",
    "operating_cash_flow": "Flujo de caja operativo",
    "equity": "Patrimonio",
    "long_term_debt": "Deuda de largo plazo",
}


@dataclass(frozen=True)
class ChangeRow:
    metric: str
    label: str
    current: float
    previous_quarter: float | None
    year_ago: float | None
    qoq: float | None
    yoy: float | None
    source: str


def _pct(a: float, b: float | None) -> float | None:
    return (a / b - 1) if b not in (None, 0) and b is not None and b > 0 else None


def _closest(series: dict[date, FactValue], target: date, tolerance: int = 20) -> FactValue | None:
    best = min(series, key=lambda d: abs((d - target).days), default=None)
    return series[best] if best and abs((best - target).days) <= tolerance else None


def quarterly_changes(facts: dict[str, Any]) -> tuple[date, str, list[ChangeRow]]:
    series = {k: quarterly_series(facts, CONCEPTS[k]) for k in LABELS}
    anchor = series["revenue"] or series["net_income"]
    if not anchor:
        raise ProviderError("EDGAR: no hay datos trimestrales (10-Q)")
    latest = max(anchor)
    accession = anchor[latest].accession
    rows: list[ChangeRow] = []
    for key, s in series.items():
        cur = s.get(latest)
        if cur is None:
            continue
        prev = _closest(s, date.fromordinal(latest.toordinal() - 91))
        year_ago = _closest(s, latest.replace(year=latest.year - 1))
        rows.append(
            ChangeRow(
                key,
                LABELS[key],
                cur.value,
                prev.value if prev else None,
                year_ago.value if year_ago else None,
                _pct(cur.value, prev.value if prev else None),
                _pct(cur.value, year_ago.value if year_ago else None),
                f"SEC {cur.form} al {cur.period_end} ({cur.concept}, acc. {cur.accession})",
            )
        )
    return latest, accession, rows


class AiReportSummary(BaseModel):
    summary: str
    highlights: list[str]
    caveats: list[str]


SYSTEM = (
    "Sos un analista que explica reportes financieros en español claro a una persona en Costa "
    "Rica que está aprendiendo a invertir. Usá SOLO las cifras de la tabla dada; si algo no está "
    "en la tabla, no lo afirmes. No des recomendaciones de compra, venta ni precios objetivo. "
    "Señalá qué cambió de forma relevante (comparando contra el trimestre anterior y el mismo "
    "trimestre del año previo), posibles efectos estacionales y qué datos faltan para concluir."
)


def _table_text(symbol: str, period_end: date, rows: list[ChangeRow]) -> str:
    def f(v: float | None, pct: bool = False) -> str:
        if v is None:
            return "n/d"
        return f"{v:+.1%}" if pct else f"{v:,.2f}"

    lines = [f"Empresa: {symbol}. Trimestre terminado el {period_end}. Cifras en USD."]
    lines.append(
        "métrica | actual | trimestre anterior | mismo trimestre año previo | "
        "var. trimestral | var. anual"
    )
    for r in rows:
        lines.append(
            f"{r.label} | {f(r.current)} | {f(r.previous_quarter)} | {f(r.year_ago)} | "
            f"{f(r.qoq, True)} | {f(r.yoy, True)}"
        )
    return "\n".join(lines)


def summarize_quarter(
    db: Session, symbol: str, facts: dict[str, Any], client: ClaudeClient | None, model: str
) -> dict[str, Any]:
    period_end, accession, rows = quarterly_changes(facts)
    table = [asdict(r) for r in rows]
    cached = db.scalar(
        select(ReportSummary).where(
            ReportSummary.symbol == symbol, ReportSummary.period_end == period_end
        )
    )
    if cached:
        return {"period_end": period_end, "table": table, "summary": cached.summary, "cached": True}
    if client is None:
        return {"period_end": period_end, "table": table, "summary": None, "cached": False}
    result = client.structured(
        system=SYSTEM,
        prompt=_table_text(symbol, period_end, rows),
        schema=AiReportSummary,
        effort="medium",
        max_tokens=4096,
    )
    if result is None:
        return {"period_end": period_end, "table": table, "summary": None, "cached": False}
    summary = result.model_dump()
    db.add(
        ReportSummary(
            symbol=symbol,
            period_end=period_end,
            accession=accession,
            facts_table=table,
            summary=summary,
            model=model,
        )
    )
    db.commit()
    return {"period_end": period_end, "table": table, "summary": summary, "cached": False}
