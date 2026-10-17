from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from moneytalk.config import get_settings
from moneytalk.db import get_db
from moneytalk.investments.market import RANGES, history, overview
from moneytalk.jobs import today_cr

router = APIRouter(prefix="/market", tags=["mercado"])
DB = Annotated[Session, Depends(get_db)]


@router.get("/overview")
def market_overview(db: DB, refresh: bool = False) -> dict[str, Any]:
    try:
        return overview(db, today_cr(get_settings()), refresh=refresh)
    except Exception as exc:  # yfinance lanza errores heterogéneos
        raise HTTPException(status_code=502, detail=f"Yahoo Finance no respondió: {exc}") from exc


@router.get("/history/{symbol}")
def market_history(db: DB, symbol: str, range: str = "1A") -> dict[str, Any]:  # noqa: A002
    if range not in RANGES:
        raise HTTPException(status_code=422, detail=f"Rango inválido; usá {', '.join(RANGES)}")
    try:
        return history(db, symbol.upper(), range, today_cr(get_settings()))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Yahoo Finance no respondió: {exc}") from exc
