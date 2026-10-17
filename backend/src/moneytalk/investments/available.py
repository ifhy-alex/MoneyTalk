"""¿Cuánto queda disponible para invertir? Integra finanzas personales con inversiones.

excedente mensual = ingreso − gasto promedio − aportes planificados a metas − colchón
Si el fondo de emergencia no está completo, el excedente va primero ahí y lo
disponible para invertir es 0 hasta completarlo.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from moneytalk.finance.fx import FxConverter
from moneytalk.finance.prefs import get_prefs
from moneytalk.finance.reports import average_monthly, goal_progress

ZERO = Decimal("0")


@dataclass(frozen=True)
class AvailableToInvest:
    monthly_income: Decimal
    income_source: str
    avg_expenses: Decimal
    goal_contributions: Decimal
    safety_buffer: Decimal
    surplus: Decimal
    emergency_fund_gap: Decimal
    emergency_fund_months_left: int | None
    available_monthly: Decimal
    explanation: list[str]


def available_to_invest(db: Session, fx: FxConverter, today: date) -> AvailableToInvest:
    prefs = get_prefs(db)
    avg = average_monthly(db, fx, today.replace(day=1), months=3)
    if prefs.monthly_income is not None:
        income = fx.convert(
            Decimal(str(prefs.monthly_income)), prefs.monthly_income_currency, "CRC", today
        )
        income_source = "ingreso declarado en ajustes"
    else:
        income, income_source = avg.income, "promedio de ingresos de los últimos 3 meses"

    progress = goal_progress(db)
    contributions = ZERO
    ef_gap = ZERO
    for p in progress:
        monthly = p.goal.monthly_contribution or ZERO
        if p.remaining > 0 and monthly:
            contributions += fx.convert(monthly, p.goal.currency, "CRC", today)
        if p.goal.is_emergency_fund:
            ef_gap = fx.convert(p.remaining, p.goal.currency, "CRC", today)

    buffer = Decimal(str(prefs.investment_safety_buffer))
    surplus = (income - avg.expenses - contributions - buffer).quantize(Decimal("0.01"))
    explanation = [
        f"Ingreso mensual: ₡{income:,.0f} ({income_source}).",
        f"Gasto promedio (3 meses, sin transferencias): ₡{avg.expenses:,.0f}.",
        f"Aportes planificados a metas: ₡{contributions:,.0f}.",
    ]
    if buffer:
        explanation.append(f"Colchón reservado: ₡{buffer:,.0f}.")

    has_ef = any(p.goal.is_emergency_fund for p in progress)
    months_left = None
    if not has_ef:
        available = ZERO
        explanation.append("Definí primero un fondo de emergencia (meta prioritaria).")
    elif ef_gap > 0:
        available = ZERO
        if surplus > 0:
            months_left = int((ef_gap / surplus).to_integral_value(rounding="ROUND_CEILING"))
        explanation.append(
            f"Al fondo de emergencia le faltan ₡{ef_gap:,.0f}: el excedente va primero ahí"
            + (f" (≈{months_left} meses)." if months_left else ".")
        )
    else:
        available = max(surplus, ZERO)
        explanation.append("Fondo de emergencia completo: el excedente queda disponible.")

    if surplus <= 0:
        explanation.append("No hay excedente mensual con los números actuales.")
    return AvailableToInvest(
        monthly_income=income.quantize(Decimal("0.01")),
        income_source=income_source,
        avg_expenses=avg.expenses,
        goal_contributions=contributions,
        safety_buffer=buffer,
        surplus=surplus,
        emergency_fund_gap=ef_gap,
        emergency_fund_months_left=months_left,
        available_monthly=available,
        explanation=explanation,
    )
