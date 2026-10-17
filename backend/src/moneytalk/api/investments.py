from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from moneytalk.config import get_settings
from moneytalk.db import get_db
from moneytalk.finance.fx import FxConverter
from moneytalk.investments.available import available_to_invest
from moneytalk.investments.edgar import EdgarClient, OfficialFundamentals
from moneytalk.investments.portfolio import (
    BENCHMARK,
    allocation,
    build_positions,
    compare_with_benchmark,
    load_trades,
    price_positions,
)
from moneytalk.investments.providers import CachedProvider, ProviderError, cached_provider
from moneytalk.investments.screener import (
    DEFAULT_PRESETS,
    METRIC_LABELS,
    Criterion,
    ScreenerRequest,
    screen_one,
)
from moneytalk.jobs import today_cr
from moneytalk.models import Asset, AssetType, ScreenerPreset, Trade, TradeSide

router = APIRouter(prefix="/investments", tags=["inversiones"])
DB = Annotated[Session, Depends(get_db)]

DISCLAIMER = (
    "Información educativa basada en criterios definidos por el usuario. "
    "No constituye asesoría financiera ni recomendación de compra o venta."
)


def provider_dep(db: DB) -> CachedProvider:
    try:
        return cached_provider(db, get_settings())
    except ProviderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


Provider = Annotated[CachedProvider, Depends(provider_dep)]


def edgar_client(db: Session) -> EdgarClient | None:
    try:
        return EdgarClient(db, get_settings().sec_user_agent)
    except ProviderError:
        return None


# --- Datos de mercado ---


@router.get("/metrics")
def list_metrics() -> dict[str, dict[str, str]]:
    return {k: {"label": v[0], "format": v[1]} for k, v in METRIC_LABELS.items()}


@router.get("/fundamentals/{symbol}")
def get_fundamentals(db: DB, provider: Provider, symbol: str) -> dict[str, Any]:
    symbol = symbol.upper()
    try:
        f = provider.fundamentals(symbol)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    official: OfficialFundamentals | None = None
    edgar_error = None
    if client := edgar_client(db):
        try:
            official = client.official(symbol)
        except ProviderError as exc:
            edgar_error = str(exc)
    return {
        "disclaimer": DISCLAIMER,
        "provider": f.to_json(),
        "sec": {
            "fiscal_year": official.fiscal_year,
            "entity": official.entity,
            "metrics": official.metrics,
            "provenance": official.provenance,
            "values": {k: asdict(v) for k, v in official.values.items()},
        }
        if official
        else None,
        "sec_error": edgar_error,
    }


# --- Screener ---


class PresetIn(BaseModel):
    name: str
    criteria: list[Criterion] = Field(min_length=1)
    universe: list[str] = Field(min_length=1)


class PresetOut(PresetIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


@router.get("/screener/presets", response_model=list[PresetOut])
def list_presets(db: DB) -> list[ScreenerPreset]:
    if not db.scalar(select(ScreenerPreset.id).limit(1)):
        for p in DEFAULT_PRESETS:
            db.add(ScreenerPreset(**p))
        db.commit()
    return list(db.scalars(select(ScreenerPreset).order_by(ScreenerPreset.id)))


@router.post("/screener/presets", response_model=PresetOut, status_code=201)
def save_preset(db: DB, body: PresetIn) -> ScreenerPreset:
    data = body.model_dump()
    data["universe"] = [s.upper().strip() for s in body.universe if s.strip()]
    preset = db.scalar(select(ScreenerPreset).where(ScreenerPreset.name == body.name))
    if preset:
        preset.criteria, preset.universe = data["criteria"], data["universe"]
    else:
        preset = ScreenerPreset(**data)
        db.add(preset)
    db.commit()
    return preset


@router.delete("/screener/presets/{preset_id}", status_code=204)
def delete_preset(db: DB, preset_id: int) -> None:
    preset = db.get(ScreenerPreset, preset_id)
    if preset:
        db.delete(preset)
        db.commit()


@router.post("/screener/run")
def run_screener(db: DB, provider: Provider, body: ScreenerRequest) -> dict[str, Any]:
    edgar = edgar_client(db) if body.use_sec else None
    rows: list[dict[str, Any]] = []
    for raw in body.universe:
        symbol = raw.upper().strip()
        try:
            f = provider.fundamentals(symbol)
        except ProviderError as exc:
            rows.append({"symbol": symbol, "error": str(exc), "results": []})
            continue
        official = None
        if edgar:
            try:
                official = edgar.official(symbol)
            except ProviderError:
                official = None
        r = screen_one(symbol, body.criteria, f, official)
        rows.append({**asdict(r), "meets_all": r.meets_all})
    rows.sort(key=lambda r: (-(r.get("passed") or 0), r.get("missing") or 0, r["symbol"]))
    return {
        "disclaimer": DISCLAIMER,
        "criteria": [c.describe() for c in body.criteria],
        "rows": rows,
    }


# --- Portafolio ---


class AssetIn(BaseModel):
    symbol: str
    name: str | None = None
    asset_type: AssetType = AssetType.STOCK
    currency: str = Field(default="USD", pattern="^(CRC|USD)$")
    sector: str | None = None
    country: str | None = None
    manual_price: Decimal | None = None
    manual_price_date: date | None = None


class TradeIn(BaseModel):
    symbol: str
    trade_date: date
    side: TradeSide
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)
    fees: Decimal = Decimal("0")
    broker: str | None = None
    notes: str | None = None


class TradeOut(TradeIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


@router.get("/assets", response_model=list[AssetIn])
def list_assets(db: DB) -> list[Asset]:
    return list(db.scalars(select(Asset).order_by(Asset.symbol)))


@router.put("/assets/{symbol}", response_model=AssetIn)
def upsert_asset(db: DB, symbol: str, body: AssetIn) -> Asset:
    symbol = symbol.upper()
    asset = db.get(Asset, symbol) or Asset(symbol=symbol)
    for key, value in body.model_dump(exclude={"symbol"}).items():
        setattr(asset, key, value)
    db.add(asset)
    db.commit()
    return asset


@router.get("/trades", response_model=list[TradeOut])
def list_trades(db: DB) -> list[Trade]:
    return list(db.scalars(select(Trade).order_by(Trade.trade_date.desc(), Trade.id.desc())))


@router.post("/trades", response_model=TradeOut, status_code=201)
def add_trade(db: DB, provider: Provider, body: TradeIn) -> Trade:
    symbol = body.symbol.upper()
    if db.get(Asset, symbol) is None:
        # Completar metadatos (sector, país) desde el proveedor; editable después.
        meta: dict[str, Any] = {"currency": "USD"}
        try:
            f = provider.fundamentals(symbol)
            meta = {
                "name": f.name,
                "currency": f.currency or "USD",
                "sector": f.sector,
                "country": f.country,
            }
        except ProviderError:
            pass
        db.add(Asset(symbol=symbol, **meta))
        db.flush()
    trade = Trade(**{**body.model_dump(), "symbol": symbol})
    db.add(trade)
    db.flush()
    try:
        build_positions(load_trades(db))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return trade


@router.delete("/trades/{trade_id}", status_code=204)
def delete_trade(db: DB, trade_id: int) -> None:
    trade = db.get(Trade, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="operación no encontrada")
    db.delete(trade)
    try:
        db.flush()
        build_positions(load_trades(db))
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=f"No se puede borrar: {exc}") from exc
    db.commit()


@router.get("/portfolio")
def portfolio(db: DB, provider: Provider) -> dict[str, Any]:
    today = today_cr(get_settings())
    positions = build_positions(load_trades(db))
    warnings = price_positions(positions, db, provider)
    fx = FxConverter(db)
    alloc = (
        allocation(positions, fx, today)
        if fx.has_rates or all(p.currency == "USD" for p in positions.values())
        else None
    )
    rows = [
        {
            "symbol": p.symbol,
            "name": p.name,
            "asset_type": p.asset_type,
            "currency": p.currency,
            "sector": p.sector,
            "country": p.country,
            "quantity": p.quantity,
            "avg_cost": p.avg_cost,
            "cost_basis": p.cost_basis.quantize(Decimal("0.01")),
            "price": p.price,
            "price_source": p.price_source,
            "market_value": p.market_value,
            "unrealized_pnl": p.unrealized_pnl,
            "unrealized_pct": float(p.unrealized_pnl / p.cost_basis)
            if p.unrealized_pnl is not None and p.cost_basis
            else None,
            "realized_pnl": p.realized_pnl.quantize(Decimal("0.01")),
            "weight": float(alloc.by_symbol[p.symbol] / alloc.total_usd)
            if alloc and alloc.total_usd and p.symbol in alloc.by_symbol
            else None,
        }
        for p in sorted(positions.values(), key=lambda p: p.symbol)
        if p.quantity or p.realized_pnl
    ]

    def pct(d: dict[str, Decimal]) -> dict[str, float]:
        total = alloc.total_usd if alloc else Decimal(0)
        return (
            {k: float(v / total) for k, v in sorted(d.items(), key=lambda kv: -kv[1])}
            if total
            else {}
        )

    return {
        "disclaimer": DISCLAIMER,
        "positions": rows,
        "total_value_usd": alloc.total_usd if alloc else None,
        "by_sector": pct(alloc.by_sector) if alloc else {},
        "by_country": pct(alloc.by_country) if alloc else {},
        "by_type": pct(alloc.by_type) if alloc else {},
        "warnings": warnings,
    }


@router.get("/portfolio/benchmark")
def portfolio_benchmark(db: DB, provider: Provider, benchmark: str = BENCHMARK) -> dict[str, Any]:
    try:
        cmp = compare_with_benchmark(
            load_trades(db), provider, today_cr(get_settings()), benchmark.upper()
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "benchmark": cmp.benchmark,
        "invested_net": cmp.invested_net,
        "portfolio_value": cmp.portfolio_value,
        "benchmark_value": cmp.benchmark_value,
        "difference": cmp.difference,
        "series": cmp.series,
        "excluded": cmp.excluded,
        "method": (
            "Cada compra/venta se replica con el mismo monto en el índice el mismo día "
            "(precios ajustados por dividendos). Solo activos en USD con historial."
        ),
    }


@router.get("/available")
def available(db: DB) -> dict[str, Any]:
    fx = FxConverter(db)
    if not fx.has_rates:
        raise HTTPException(status_code=409, detail="Falta el tipo de cambio del BCCR")
    return asdict(available_to_invest(db, fx, today_cr(get_settings())))
