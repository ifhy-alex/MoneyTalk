"""Cálculos de gasto, presupuesto y metas. Todo se expresa en la moneda base (CRC por defecto)
convirtiendo cada transacción con el tipo de cambio de su fecha."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from moneytalk.finance.fx import FxConverter
from moneytalk.models import Budget, Category, CategoryKind, Goal, Transaction

ZERO = Decimal("0")


def month_bounds(month: date) -> tuple[date, date]:
    start = month.replace(day=1)
    nxt = (start + timedelta(days=32)).replace(day=1)
    return start, nxt - timedelta(days=1)


def parse_month(value: str) -> date:
    year, mon = (int(x) for x in value.split("-"))
    return date(year, mon, 1)


def add_months(month: date, delta: int) -> date:
    total = month.year * 12 + (month.month - 1) + delta
    return date(total // 12, total % 12 + 1, 1)


def transactions_between(db: Session, start: date, end: date) -> list[Transaction]:
    return list(
        db.scalars(
            select(Transaction)
            .where(Transaction.txn_date.between(start, end))
            .options(selectinload(Transaction.category))
        )
    )


def kind_of(txn: Transaction) -> CategoryKind | None:
    return txn.category.kind if txn.category else None


@dataclass
class PeriodTotals:
    income: Decimal = ZERO
    expenses: Decimal = ZERO  # positivo
    transfers: Decimal = ZERO
    by_category: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    by_currency: dict[str, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))
    uncategorized_expenses: Decimal = ZERO

    @property
    def net(self) -> Decimal:
        return self.income - self.expenses


def totals(txns: list[Transaction], fx: FxConverter, base: str = "CRC") -> PeriodTotals:
    """Transferencias (pago de tarjeta, entre cuentas) no cuentan como gasto ni ingreso:
    si no, pagar la tarjeta duplicaría el gasto."""
    out = PeriodTotals()
    for t in txns:
        amount = fx.convert(t.amount, t.currency, base, t.txn_date)
        kind = kind_of(t)
        if kind is CategoryKind.TRANSFER:
            out.transfers += amount
            continue
        if amount >= 0 and kind is not CategoryKind.EXPENSE:
            out.income += amount
            continue
        spent = -amount  # devoluciones en categorías de gasto restan gasto
        out.expenses += spent
        out.by_currency[t.currency] += -t.amount
        name = t.category.name if t.category else "Sin categoría"
        out.by_category[name] += spent
        if t.category is None:
            out.uncategorized_expenses += spent
    return out


@dataclass(frozen=True)
class BudgetStatus:
    budget_id: int
    category_id: int
    category: str
    currency: str
    budgeted: Decimal
    spent: Decimal
    is_override: bool

    @property
    def ratio(self) -> float:
        return float(self.spent / self.budgeted) if self.budgeted else 0.0

    @property
    def remaining(self) -> Decimal:
        return self.budgeted - self.spent


def budgets_for_month(db: Session, month: date) -> list[Budget]:
    """Sobrescritura del mes > presupuesto por defecto."""
    rows = db.scalars(
        select(Budget)
        .where((Budget.month.is_(None)) | (Budget.month == month))
        .options(selectinload(Budget.category))
    ).all()
    chosen: dict[int, Budget] = {}
    for b in rows:
        if b.category_id not in chosen or b.month is not None:
            chosen[b.category_id] = b
    return sorted(chosen.values(), key=lambda b: b.category.name)


def budget_status(db: Session, month: date, fx: FxConverter) -> list[BudgetStatus]:
    start, end = month_bounds(month)
    txns = transactions_between(db, start, end)
    spent_by_cat: dict[int, list[Transaction]] = defaultdict(list)
    for t in txns:
        if t.category_id and kind_of(t) is CategoryKind.EXPENSE:
            spent_by_cat[t.category_id].append(t)
    result = []
    for b in budgets_for_month(db, month):
        spent = sum(
            (
                -fx.convert(t.amount, t.currency, b.currency, t.txn_date)
                for t in spent_by_cat[b.category_id]
            ),
            ZERO,
        )
        result.append(
            BudgetStatus(
                budget_id=b.id,
                category_id=b.category_id,
                category=b.category.name,
                currency=b.currency,
                budgeted=b.amount,
                spent=spent,
                is_override=b.month is not None,
            )
        )
    return result


def average_monthly(
    db: Session, fx: FxConverter, until_month: date, months: int = 3, base: str = "CRC"
) -> PeriodTotals:
    """Promedio de los `months` meses completos anteriores a `until_month`."""
    start = add_months(until_month, -months)
    _, end = month_bounds(add_months(until_month, -1))
    t = totals(transactions_between(db, start, end), fx, base)
    div = Decimal(months)
    avg = PeriodTotals(
        income=(t.income / div).quantize(Decimal("0.01")),
        expenses=(t.expenses / div).quantize(Decimal("0.01")),
        transfers=(t.transfers / div).quantize(Decimal("0.01")),
    )
    for k, v in t.by_category.items():
        avg.by_category[k] = (v / div).quantize(Decimal("0.01"))
    return avg


@dataclass(frozen=True)
class GoalProgress:
    goal: Goal
    saved: Decimal

    @property
    def ratio(self) -> float:
        return float(self.saved / self.goal.target_amount) if self.goal.target_amount else 0.0

    @property
    def remaining(self) -> Decimal:
        return max(self.goal.target_amount - self.saved, ZERO)

    def months_to_target(self) -> int | None:
        monthly = self.goal.monthly_contribution
        if not monthly or monthly <= 0:
            return None
        return int((self.remaining / monthly).to_integral_value(rounding="ROUND_CEILING"))

    def required_monthly(self, today: date) -> Decimal | None:
        if not self.goal.target_date or self.goal.target_date <= today:
            return None
        months = max(
            (self.goal.target_date.year - today.year) * 12
            + self.goal.target_date.month
            - today.month,
            1,
        )
        return (self.remaining / months).quantize(Decimal("0.01"))


def goal_progress(db: Session) -> list[GoalProgress]:
    goals = db.scalars(
        select(Goal)
        .where(Goal.is_active)
        .options(selectinload(Goal.contributions))
        .order_by(Goal.is_emergency_fund.desc(), Goal.priority.desc(), Goal.id)
    ).all()
    return [GoalProgress(g, sum((c.amount for c in g.contributions), ZERO)) for g in goals]


def emergency_fund_target(
    db: Session, fx: FxConverter, today: date, months_of_expenses: int, base: str = "CRC"
) -> Decimal:
    avg = average_monthly(db, fx, today.replace(day=1), months=3, base=base)
    return (avg.expenses * months_of_expenses).quantize(Decimal("0.01"))


def expense_categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).where(Category.kind == CategoryKind.EXPENSE)))
