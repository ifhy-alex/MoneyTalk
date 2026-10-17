"""Preferencias del usuario guardadas en `app_settings`, con valores por defecto tipados."""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from moneytalk.models import AppSetting

KEY = "preferences"


class Preferences(BaseModel):
    base_currency: str = "CRC"
    budget_alert_threshold: float = Field(default=0.8, gt=0, lt=1)
    emergency_fund_months: int = Field(default=6, ge=1, le=24)
    unusual_spend_zscore: float = Field(default=3.0, gt=0)
    unusual_spend_min_samples: int = Field(default=8, ge=3)
    # Ingreso mensual neto esperado; si es None se estima con el promedio de 3 meses.
    monthly_income: float | None = None
    monthly_income_currency: str = "CRC"
    # Colchón adicional que nunca se considera "disponible para invertir".
    investment_safety_buffer: float = 0
    telegram_alerts: bool = True


def get_prefs(db: Session) -> Preferences:
    row = db.get(AppSetting, KEY)
    return Preferences.model_validate(row.value if row else {})


def save_prefs(db: Session, updates: dict[str, Any]) -> Preferences:
    prefs = get_prefs(db).model_copy(update=updates)
    prefs = Preferences.model_validate(prefs.model_dump())  # revalida
    row = db.get(AppSetting, KEY)
    if row is None:
        db.add(AppSetting(key=KEY, value=prefs.model_dump()))
    else:
        row.value = prefs.model_dump()
    db.commit()
    return prefs
