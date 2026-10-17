"""Resumen semanal (texto HTML para Telegram)."""

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from moneytalk.finance.fx import FxConverter
from moneytalk.finance.reports import budget_status, goal_progress, totals, transactions_between
from moneytalk.models import Alert, CategoryStatus, Transaction
from moneytalk.notifications.telegram import esc


def _crc(v: Decimal) -> str:
    return f"₡{v:,.0f}"


def weekly_summary(db: Session, fx: FxConverter, today: date) -> str:
    end = today - timedelta(days=1)
    start = end - timedelta(days=6)
    prev_start, prev_end = start - timedelta(days=7), start - timedelta(days=1)

    week = transactions_between(db, start, end)
    current = totals(week, fx)
    previous = totals(transactions_between(db, prev_start, prev_end), fx)

    lines = [f"<b>Resumen semanal</b> ({start:%d/%m} – {end:%d/%m})", ""]
    change = ""
    if previous.expenses:
        delta = (current.expenses - previous.expenses) / previous.expenses
        change = f" ({'+' if delta >= 0 else ''}{delta:.0%} vs. semana anterior)"
    lines.append(f"Gastos: <b>{_crc(current.expenses)}</b>{change}")
    lines.append(f"Ingresos: {_crc(current.income)}")

    top = sorted(current.by_category.items(), key=lambda kv: kv[1], reverse=True)[:5]
    if top:
        lines += ["", "<b>Por categoría</b>"] + [f"• {esc(k)}: {_crc(v)}" for k, v in top]

    merchants: Counter[str] = Counter()
    for t in week:
        if t.amount < 0:
            merchants[t.merchant_normalized] += int(
                -fx.convert(t.amount, t.currency, "CRC", t.txn_date)
            )
    if merchants:
        lines += ["", "<b>Comercios principales</b>"] + [
            f"• {esc(m)}: ₡{v:,}" for m, v in merchants.most_common(3)
        ]

    budgets = [b for b in budget_status(db, today.replace(day=1), fx) if b.ratio >= 0.7]
    if budgets:
        lines += ["", "<b>Presupuestos del mes</b>"] + [
            f"• {esc(b.category)}: {b.ratio:.0%} ({b.remaining:,.0f} {b.currency} disponibles)"
            for b in sorted(budgets, key=lambda b: -b.ratio)
        ]

    goals = goal_progress(db)
    if goals:
        lines += ["", "<b>Metas</b>"] + [
            f"• {esc(g.goal.name)}: {g.ratio:.0%} de {g.goal.target_amount:,.0f} {g.goal.currency}"
            for g in goals[:4]
        ]

    pending = db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.category_status != CategoryStatus.CONFIRMED)
    )
    unread = db.scalar(select(func.count()).select_from(Alert).where(Alert.read_at.is_(None)))
    lines += ["", f"Pendientes de categorizar: {pending} · Alertas sin leer: {unread}"]
    return "\n".join(lines)
