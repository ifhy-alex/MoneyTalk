"""Inversiones II: comparador local, backtesting y resúmenes de reportes."""

from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.ai import claude_from_settings
from moneytalk.api.investments import DISCLAIMER, Provider, edgar_client
from moneytalk.config import get_settings
from moneytalk.db import get_db
from moneytalk.finance.fx import BccrClient, latest_rate
from moneytalk.investments.backtest import BacktestRequest, run_backtest
from moneytalk.investments.comparator import CompareRequest, OptionIn, compare
from moneytalk.investments.providers import ProviderError
from moneytalk.investments.reports import summarize_quarter
from moneytalk.jobs import today_cr
from moneytalk.models import FixedIncomeKind, FixedIncomeOption

router = APIRouter(prefix="/investments", tags=["inversiones II"])
DB = Annotated[Session, Depends(get_db)]

TBP_INDICATOR = "423"  # Tasa básica pasiva (BCCR)


class FixedIncomeIn(BaseModel):
    name: str
    kind: FixedIncomeKind = FixedIncomeKind.CDP
    institution: str | None = None
    currency: str = Field(pattern="^(CRC|USD)$")
    annual_rate: Decimal = Field(ge=-1, le=1)
    tax_rate: Decimal = Field(default=Decimal("0.15"), ge=0, le=1)
    term_months: int | None = None
    compounding: str = Field(default="simple", pattern="^(simple|monthly|annual)$")
    rate_date: date | None = None
    notes: str | None = None


class FixedIncomeOut(FixedIncomeIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


@router.get("/fixed-income", response_model=list[FixedIncomeOut])
def list_options(db: DB) -> list[FixedIncomeOption]:
    return list(
        db.scalars(
            select(FixedIncomeOption).order_by(FixedIncomeOption.currency, FixedIncomeOption.name)
        )
    )


@router.post("/fixed-income", response_model=FixedIncomeOut, status_code=201)
def create_option(db: DB, body: FixedIncomeIn) -> FixedIncomeOption:
    opt = FixedIncomeOption(**body.model_dump())
    db.add(opt)
    db.commit()
    return opt


@router.delete("/fixed-income/{opt_id}", status_code=204)
def delete_option(db: DB, opt_id: int) -> None:
    opt = db.get(FixedIncomeOption, opt_id)
    if opt:
        db.delete(opt)
        db.commit()


@router.get("/bccr/tbp")
def tasa_basica_pasiva() -> dict[str, Any]:
    """Tasa básica pasiva vigente: referencia para CDP en colones."""
    settings = get_settings()
    end = today_cr(settings)
    try:
        series = BccrClient(settings).series(TBP_INDICATOR, end - timedelta(days=14), end)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not series:
        raise HTTPException(status_code=502, detail="El BCCR no devolvió la TBP")
    day = max(series)
    return {"date": day, "rate": series[day] / 100, "source": "BCCR indicador 423"}


class CompareIn(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="CRC", pattern="^(CRC|USD)$")
    months: int = Field(gt=0, le=600)
    colon_depreciation: Decimal = Decimal("0")
    inflation: Decimal = Decimal("0.03")
    fx_rate: Decimal | None = None
    option_ids: list[int] = Field(default_factory=list)
    extra_options: list[OptionIn] = Field(default_factory=list)


@router.post("/compare")
def compare_options(db: DB, body: CompareIn) -> dict[str, Any]:
    fx = body.fx_rate
    if fx is None:
        rate = latest_rate(db)
        if rate is None:
            raise HTTPException(status_code=409, detail="Falta el tipo de cambio: indicá fx_rate")
        fx = rate.sell
    stored = (
        db.scalars(select(FixedIncomeOption).where(FixedIncomeOption.id.in_(body.option_ids))).all()
        if body.option_ids
        else []
    )
    options = [
        OptionIn(
            name=o.name if not o.institution else f"{o.name} ({o.institution})",
            currency=o.currency,
            annual_rate=o.annual_rate,
            tax_rate=o.tax_rate,
            compounding=o.compounding,
        )
        for o in stored
    ] + body.extra_options
    if not options:
        raise HTTPException(status_code=422, detail="Elegí al menos una opción")
    req = CompareRequest(
        amount=body.amount,
        currency=body.currency,
        months=body.months,
        fx_rate=fx,
        colon_depreciation=body.colon_depreciation,
        inflation=body.inflation,
        options=options,
    )
    rows, extra = compare(req)
    return {
        "disclaimer": DISCLAIMER,
        "assumptions": {
            "fx_rate_start": fx,
            "colon_depreciation": body.colon_depreciation,
            "inflation": body.inflation,
            **extra,
        },
        "rows": sorted((asdict(r) for r in rows), key=lambda r: -r["final_value_base"]),
    }


@router.post("/backtest")
def backtest(db: DB, provider: Provider, body: BacktestRequest) -> dict[str, Any]:
    edgar = edgar_client(db)
    if edgar is None:
        raise HTTPException(status_code=409, detail="Configurá SEC_USER_AGENT con un correo")
    try:
        result = run_backtest(body, provider, edgar.company_facts, today_cr(get_settings()))
    except (ValueError, ProviderError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"disclaimer": DISCLAIMER, **asdict(result)}


@router.post("/reports/{symbol}/quarterly")
def quarterly_report(db: DB, symbol: str, summarize: bool = True) -> dict[str, Any]:
    symbol = symbol.upper()
    edgar = edgar_client(db)
    if edgar is None:
        raise HTTPException(status_code=409, detail="Configurá SEC_USER_AGENT con un correo")
    settings = get_settings()
    try:
        _, facts = edgar.company_facts(symbol)
        result = summarize_quarter(
            db,
            symbol,
            facts,
            claude_from_settings(settings) if summarize else None,
            settings.claude_model,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "disclaimer": DISCLAIMER,
        "symbol": symbol,
        "ai_enabled": bool(settings.anthropic_api_key),
        **result,
    }
