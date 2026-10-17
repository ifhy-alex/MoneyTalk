"""Detección de alertas. Cada alerta guarda la evidencia numérica que la disparó.

- Gasto inusual: monto > media + z·desviación del historial de 120 días de la categoría
  (requiere un mínimo de muestras); sin historial de categoría, > 3× la mediana del comercio.
- Presupuesto: al cruzar el umbral (80 % por defecto) y al excederlo, una vez por mes.
- Suscripción nueva: cargo en una categoría de suscripciones de un comercio sin cargos en
  los 120 días previos, o comercio con montos similares en 3 meses distintos (recurrente).
- Suscripción duplicada: el mismo comercio de suscripción cobra dos veces en < 25 días.
"""

import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from moneytalk.finance.fx import FxConverter
from moneytalk.finance.prefs import Preferences
from moneytalk.finance.reports import budget_status
from moneytalk.models import Alert, AlertKind, CategoryKind, Transaction

HISTORY_DAYS = 120
DUPLICATE_WINDOW_DAYS = 25
SIMILAR_AMOUNT = Decimal("0.10")  # ±10 %


@dataclass(frozen=True)
class AlertDraft:
    kind: AlertKind
    dedup_key: str
    message: str
    evidence: dict[str, Any]
    transaction_id: int | None = None


def _similar(a: Decimal, b: Decimal) -> bool:
    a, b = abs(a), abs(b)
    return bool(a and b) and abs(a - b) / max(a, b) <= SIMILAR_AMOUNT


def _history(db: Session, txn: Transaction) -> list[Transaction]:
    return list(
        db.scalars(
            select(Transaction)
            .where(
                Transaction.id != txn.id,
                Transaction.txn_date.between(
                    txn.txn_date - timedelta(days=HISTORY_DAYS), txn.txn_date
                ),
                Transaction.amount < 0,
            )
            .options(selectinload(Transaction.category))
        )
    )


def unusual_spend(
    txn: Transaction, history: list[Transaction], fx: FxConverter, prefs: Preferences
) -> AlertDraft | None:
    if txn.amount >= 0 or (txn.category and txn.category.kind is not CategoryKind.EXPENSE):
        return None
    amount = abs(fx.convert(txn.amount, txn.currency, "CRC", txn.txn_date))
    same_cat = [
        abs(fx.convert(t.amount, t.currency, "CRC", t.txn_date))
        for t in history
        if txn.category_id and t.category_id == txn.category_id
    ]
    evidence: dict[str, Any]
    if len(same_cat) >= prefs.unusual_spend_min_samples:
        samples = [float(x) for x in same_cat]
        mean = statistics.fmean(samples)
        stdev = statistics.pstdev(samples)
        threshold = mean + prefs.unusual_spend_zscore * stdev
        if stdev == 0 or float(amount) <= threshold:
            return None
        evidence = {
            "monto_crc": float(amount),
            "media_categoria": round(mean, 2),
            "desviacion": round(stdev, 2),
            "umbral": round(threshold, 2),
            "muestras": len(same_cat),
        }
        reason = f"supera {prefs.unusual_spend_zscore:g} desviaciones de la media de la categoría"
    else:
        same_merchant = [
            abs(fx.convert(t.amount, t.currency, "CRC", t.txn_date))
            for t in history
            if t.merchant_normalized == txn.merchant_normalized
        ]
        if len(same_merchant) < 3:
            return None
        median = statistics.median(same_merchant)
        if float(amount) <= 3 * float(median):
            return None
        evidence = {
            "monto_crc": float(amount),
            "mediana_comercio": float(median),
            "muestras": len(same_merchant),
        }
        reason = "es más de 3× lo usual en este comercio"
    return AlertDraft(
        AlertKind.UNUSUAL_SPEND,
        f"unusual:{txn.id}",
        f"Gasto inusual en {txn.merchant_raw}: {abs(txn.amount):,.2f} {txn.currency} ({reason}).",
        evidence,
        txn.id,
    )


def subscription_alerts(txn: Transaction, history: list[Transaction]) -> list[AlertDraft]:
    if txn.amount >= 0:
        return []
    same = [t for t in history if t.merchant_normalized == txn.merchant_normalized]
    is_sub_cat = bool(txn.category and txn.category.is_subscription)
    drafts: list[AlertDraft] = []

    recent_dupes = [
        t
        for t in same
        if abs((t.txn_date - txn.txn_date).days) < DUPLICATE_WINDOW_DAYS
        and _similar(t.amount, txn.amount)
        and t.currency == txn.currency
    ]
    if is_sub_cat and recent_dupes:
        other = recent_dupes[0]
        drafts.append(
            AlertDraft(
                AlertKind.DUPLICATE_SUBSCRIPTION,
                f"dupsub:{min(txn.id, other.id)}:{max(txn.id, other.id)}",
                f"Posible cobro duplicado de {txn.merchant_raw}: {other.txn_date:%d/%m} y "
                f"{txn.txn_date:%d/%m} por montos similares.",
                {
                    "transacciones": [other.id, txn.id],
                    "montos": [str(other.amount), str(txn.amount)],
                },
                txn.id,
            )
        )

    if is_sub_cat and not same:
        drafts.append(
            AlertDraft(
                AlertKind.NEW_SUBSCRIPTION,
                f"newsub:{txn.merchant_normalized}",
                f"Suscripción nueva: {txn.merchant_raw} ({abs(txn.amount):,.2f} {txn.currency}).",
                {"sin_cargos_previos_dias": HISTORY_DAYS},
                txn.id,
            )
        )
    elif not is_sub_cat:
        months = {
            (t.txn_date.year, t.txn_date.month) for t in same if _similar(t.amount, txn.amount)
        }
        months.discard((txn.txn_date.year, txn.txn_date.month))
        if len(months) >= 2:
            drafts.append(
                AlertDraft(
                    AlertKind.NEW_SUBSCRIPTION,
                    f"recurring:{txn.merchant_normalized}",
                    f"{txn.merchant_raw} parece un cargo recurrente (montos similares en "
                    f"{len(months) + 1} meses). ¿Es una suscripción?",
                    {"meses": sorted(f"{y}-{m:02d}" for y, m in months)},
                    txn.id,
                )
            )
    return drafts


def budget_alerts(
    db: Session, month: date, fx: FxConverter, prefs: Preferences
) -> list[AlertDraft]:
    drafts = []
    for s in budget_status(db, month, fx):
        evidence = {
            "presupuesto": str(s.budgeted),
            "gastado": str(s.spent),
            "moneda": s.currency,
            "porcentaje": round(s.ratio * 100, 1),
        }
        if s.ratio >= 1:
            drafts.append(
                AlertDraft(
                    AlertKind.BUDGET_EXCEEDED,
                    f"budget:{s.category_id}:{month:%Y-%m}:100",
                    f"Excediste el presupuesto de {s.category}: "
                    f"{s.spent:,.0f} de {s.budgeted:,.0f} {s.currency}.",
                    evidence,
                )
            )
        elif s.ratio >= prefs.budget_alert_threshold:
            drafts.append(
                AlertDraft(
                    AlertKind.BUDGET_NEAR_LIMIT,
                    f"budget:{s.category_id}:{month:%Y-%m}:near",
                    f"{s.category} va en {s.ratio:.0%} del presupuesto "
                    f"({s.remaining:,.0f} {s.currency} disponibles).",
                    evidence,
                )
            )
    return drafts


def save_alerts(db: Session, drafts: Iterable[AlertDraft]) -> list[Alert]:
    created = []
    for d in drafts:
        if db.scalar(select(Alert.id).where(Alert.dedup_key == d.dedup_key)):
            continue
        alert = Alert(
            kind=d.kind,
            dedup_key=d.dedup_key,
            message=d.message,
            evidence=d.evidence,
            transaction_id=d.transaction_id,
        )
        db.add(alert)
        created.append(alert)
    db.flush()
    return created


def run_alerts(
    db: Session, fx: FxConverter, prefs: Preferences, today: date, since: date | None = None
) -> list[Alert]:
    """Evalúa transacciones desde `since` (por defecto, últimos 7 días) y presupuestos del mes."""
    since = since or today - timedelta(days=7)
    recent = db.scalars(
        select(Transaction)
        .where(Transaction.txn_date >= since)
        .options(selectinload(Transaction.category))
        .order_by(Transaction.txn_date, Transaction.id)
    ).all()
    drafts: list[AlertDraft] = []
    for txn in recent:
        history = [t for t in _history(db, txn) if t.txn_date < txn.txn_date or t.id < txn.id]
        if fx.has_rates or txn.currency == "CRC":
            try:
                if d := unusual_spend(txn, history, fx, prefs):
                    drafts.append(d)
            except LookupError:
                pass
        drafts.extend(subscription_alerts(txn, history))
    if fx.has_rates:
        drafts.extend(budget_alerts(db, today.replace(day=1), fx, prefs))
    created = save_alerts(db, drafts)
    db.commit()
    return created
