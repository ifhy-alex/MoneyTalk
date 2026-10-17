from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from moneytalk.config import get_settings
from moneytalk.db import get_db
from moneytalk.investments.market import overview
from moneytalk.jobs import today_cr

router = APIRouter(prefix="/market", tags=["mercado"])
DB = Annotated[Session, Depends(get_db)]


@router.get("/overview")
def market_overview(db: DB, refresh: bool = False) -> dict[str, Any]:
    try:
        return overview(db, today_cr(get_settings()), refresh=refresh)
    except Exception as exc:  # yfinance lanza errores heterogéneos
        raise HTTPException(status_code=502, detail=f"Yahoo Finance no respondió: {exc}") from exc
