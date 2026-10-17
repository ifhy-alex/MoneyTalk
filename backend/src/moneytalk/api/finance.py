from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from moneytalk.config import get_settings
from moneytalk.db import get_db
from moneytalk.finance.fx import FxConverter, latest_rate
from moneytalk.finance.prefs import Preferences, get_prefs, save_prefs
from moneytalk.finance.reports import (
    add_months,
    budget_status,
    emergency_fund_target,
    goal_progress,
    month_bounds,
    parse_month,
    totals,
    transactions_between,
)
from moneytalk.jobs import job_alerts, job_fx_sync, job_weekly_summary, today_cr
from moneytalk.models import (
    Alert,
    AlertKind,
    Budget,
    CategoryStatus,
    ExchangeRate,
    Goal,
    GoalContribution,
    Transaction,
)

router = APIRouter(tags=["presupuesto y metas"])
DB = Annotated[Session, Depends(get_db)]
Month = Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")]


def _fx(db: Session) -> FxConverter:
    fx = FxConverter(db)
    if not fx.has_rates:
        raise HTTPException(
            status_code=409,
            detail="No hay tipo de cambio cargado. Configurá BCCR_TOKEN y corré la sincronización.",
        )
    return fx


# --- Tipo de cambio ---


class RateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rate_date: date
    buy: Decimal
    sell: Decimal
    source: str


class RateIn(BaseModel):
    rate_date: date
    buy: Decimal = Field(gt=0)
    sell: Decimal = Field(gt=0)


@router.get("/fx/latest", response_model=RateOut | None)
def fx_latest(db: DB) -> ExchangeRate | None:
    return latest_rate(db)


@router.get("/fx/history", response_model=list[RateOut])
def fx_history(db: DB, days: int = 90) -> list[ExchangeRate]:
    rows = db.scalars(select(ExchangeRate).order_by(ExchangeRate.rate_date.desc()).limit(days))
    return list(reversed(list(rows)))


@router.post("/fx/sync")
def fx_sync(db: DB) -> dict[str, int]:
    try:
        return {"days": job_fx_sync(db, get_settings())}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/fx/manual", response_model=RateOut)
def fx_manual(db: DB, body: RateIn) -> ExchangeRate:
    """Respaldo manual si el servicio del BCCR no está disponible."""
    row = db.get(ExchangeRate, body.rate_date) or ExchangeRate(rate_date=body.rate_date)
    row.buy, row.sell, row.source = body.buy, body.sell, "manual"
    db.add(row)
    db.commit()
    return row


# --- Presupuestos ---


class BudgetIn(BaseModel):
    category_id: int
    month: date | None = None
    amount: Decimal = Field(gt=0)
    currency: str = Field(pattern="^(CRC|USD)$")


class BudgetStatusOut(BaseModel):
    budget_id: int
    category_id: int
    category: str
    currency: str
    budgeted: Decimal
    spent: Decimal
    remaining: Decimal
    ratio: float
    is_override: bool


@router.get("/budgets", response_model=list[BudgetStatusOut])
def list_budgets(db: DB, month: Month) -> list[BudgetStatusOut]:
    return [
        BudgetStatusOut(
            **{
                k: getattr(s, k)
                for k in BudgetStatusOut.model_fields
                if k not in {"remaining", "ratio"}
            },
            remaining=s.remaining,
            ratio=s.ratio,
        )
        for s in budget_status(db, parse_month(month), _fx(db))
    ]


@router.post("/budgets", status_code=201)
def upsert_budget(db: DB, body: BudgetIn) -> dict[str, int]:
    month = body.month.replace(day=1) if body.month else None
    existing = db.scalar(
        select(Budget).where(
            Budget.category_id == body.category_id,
            Budget.month.is_(None) if month is None else Budget.month == month,
        )
    )
    budget = existing or Budget(category_id=body.category_id, month=month)
    budget.amount, budget.currency = body.amount, body.currency
    db.add(budget)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail="categoría inválida") from exc
    return {"id": budget.id}


@router.delete("/budgets/{budget_id}", status_code=204)
def delete_budget(db: DB, budget_id: int) -> None:
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="presupuesto no encontrado")
    db.delete(budget)
    db.commit()


# --- Metas ---


class GoalIn(BaseModel):
    name: str
    target_amount: Decimal = Field(gt=0)
    currency: str = Field(pattern="^(CRC|USD)$")
    target_date: date | None = None
    monthly_contribution: Decimal | None = None
    priority: int = 100
    is_emergency_fund: bool = False
    is_active: bool = True


class ContributionIn(BaseModel):
    date: date
    amount: Decimal
    note: str | None = None


class GoalOut(GoalIn):
    id: int
    saved: Decimal
    remaining: Decimal
    ratio: float
    months_to_target: int | None
    required_monthly: Decimal | None


class EmergencyFundOut(BaseModel):
    months: int
    suggested_target: Decimal
    currency: str
    based_on: str


@router.get("/goals", response_model=list[GoalOut])
def list_goals(db: DB) -> list[GoalOut]:
    today = today_cr(get_settings())
    return [
        GoalOut(
            id=p.goal.id,
            **GoalIn.model_validate(p.goal, from_attributes=True).model_dump(),
            saved=p.saved,
            remaining=p.remaining,
            ratio=p.ratio,
            months_to_target=p.months_to_target(),
            required_monthly=p.required_monthly(today),
        )
        for p in goal_progress(db)
    ]


@router.post("/goals", status_code=201)
def create_goal(db: DB, body: GoalIn) -> dict[str, int]:
    goal = Goal(**body.model_dump())
    db.add(goal)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="ya existe un fondo de emergencia") from exc
    return {"id": goal.id}


@router.patch("/goals/{goal_id}", status_code=204)
def update_goal(db: DB, goal_id: int, body: GoalIn) -> None:
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="meta no encontrada")
    for key, value in body.model_dump().items():
        setattr(goal, key, value)
    db.commit()


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(db: DB, goal_id: int) -> None:
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="meta no encontrada")
    db.delete(goal)
    db.commit()


@router.post("/goals/{goal_id}/contributions", status_code=201)
def add_contribution(db: DB, goal_id: int, body: ContributionIn) -> dict[str, int]:
    if db.get(Goal, goal_id) is None:
        raise HTTPException(status_code=404, detail="meta no encontrada")
    c = GoalContribution(goal_id=goal_id, **body.model_dump())
    db.add(c)
    db.commit()
    return {"id": c.id}


@router.get("/goals/emergency-fund/suggestion", response_model=EmergencyFundOut)
def emergency_suggestion(db: DB) -> EmergencyFundOut:
    prefs = get_prefs(db)
    target = emergency_fund_target(
        db, _fx(db), today_cr(get_settings()), prefs.emergency_fund_months
    )
    return EmergencyFundOut(
        months=prefs.emergency_fund_months,
        suggested_target=target,
        currency="CRC",
        based_on="promedio de gastos de los últimos 3 meses completos (sin transferencias)",
    )


# --- Alertas ---


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: AlertKind
    message: str
    evidence: dict[str, Any]
    transaction_id: int | None
    created_at: datetime
    read_at: datetime | None


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(db: DB, unread: bool = False, limit: int = 100) -> list[Alert]:
    stmt = select(Alert).order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit)
    if unread:
        stmt = stmt.where(Alert.read_at.is_(None))
    return list(db.scalars(stmt))


@router.post("/alerts/{alert_id}/read", status_code=204)
def mark_read(db: DB, alert_id: int) -> None:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alerta no encontrada")
    alert.read_at = datetime.now(UTC)
    db.commit()


@router.post("/alerts/run")
def run_alerts_now(db: DB) -> dict[str, int]:
    return {"created": len(job_alerts(db, get_settings()))}


@router.post("/summary/weekly")
def send_weekly_summary(db: DB) -> dict[str, str]:
    return {"text": job_weekly_summary(db, get_settings())}


# --- Preferencias ---


@router.get("/preferences", response_model=Preferences)
def read_prefs(db: DB) -> Preferences:
    return get_prefs(db)


@router.put("/preferences", response_model=Preferences)
def write_prefs(db: DB, body: dict[str, Any]) -> Preferences:
    try:
        return save_prefs(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# --- Dashboard ---


class MonthPoint(BaseModel):
    month: str
    income: Decimal
    expenses: Decimal


class DashboardOut(BaseModel):
    month: str
    base_currency: str
    income: Decimal
    expenses: Decimal
    net: Decimal
    expenses_by_currency: dict[str, Decimal]
    by_category: dict[str, Decimal]
    uncategorized_expenses: Decimal
    trend: list[MonthPoint]
    budgets: list[BudgetStatusOut]
    goals: list[GoalOut]
    fx: RateOut | None
    unread_alerts: int
    pending_categorization: int


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: DB, month: Month) -> DashboardOut:
    m = parse_month(month)
    fx = _fx(db)
    start, end = month_bounds(m)
    current = totals(transactions_between(db, start, end), fx)

    trend = []
    for i in range(5, -1, -1):
        tm = add_months(m, -i)
        ts, te = month_bounds(tm)
        t = totals(transactions_between(db, ts, te), fx)
        trend.append(MonthPoint(month=f"{tm:%Y-%m}", income=t.income, expenses=t.expenses))

    rate = latest_rate(db)
    return DashboardOut(
        month=month,
        base_currency="CRC",
        income=current.income,
        expenses=current.expenses,
        net=current.net,
        expenses_by_currency=dict(current.by_currency),
        by_category=dict(sorted(current.by_category.items(), key=lambda kv: kv[1], reverse=True)),
        uncategorized_expenses=current.uncategorized_expenses,
        trend=trend,
        budgets=list_budgets(db, month),
        goals=list_goals(db),
        fx=RateOut.model_validate(rate) if rate else None,
        unread_alerts=db.scalar(
            select(func.count()).select_from(Alert).where(Alert.read_at.is_(None))
        )
        or 0,
        pending_categorization=db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.category_status != CategoryStatus.CONFIRMED)
        )
        or 0,
    )
