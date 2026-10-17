"""Categorización: reglas → memoria por comercio → IA (pendiente de confirmar).

1. Reglas configurables (prioridad descendente). Resultado: confirmada, fuente "rule".
2. Si ya confirmaste otra transacción del mismo comercio normalizado, se reutiliza esa
   categoría como sugerencia (sin gastar una llamada a la IA).
3. Si nada aplica y hay API key: Claude sugiere; queda "suggested" hasta que confirmes.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.categorization.ai import AiCategorizer
from moneytalk.categorization.rules import active_rules, first_match, rule_matches
from moneytalk.models import (
    Category,
    CategoryRule,
    CategorySource,
    CategoryStatus,
    MatchType,
    Transaction,
)

AI_MIN_CONFIDENCE = 0.5


@dataclass(frozen=True)
class RuleSuggestion:
    """Propuesta de regla tras confirmar/corregir: el usuario decide si la crea."""

    match_type: MatchType
    pattern: str
    category_id: int
    would_affect: int  # transacciones sin confirmar que la regla recategorizaría


def _apply(
    txn: Transaction,
    category_id: int,
    status: CategoryStatus,
    source: CategorySource,
    reason: str | None = None,
) -> None:
    txn.category_id = category_id
    txn.category_status = status
    txn.category_source = source
    txn.ai_reason = reason


def categorize(
    db: Session,
    txn: Transaction,
    ai: AiCategorizer | None = None,
    rules: list[CategoryRule] | None = None,
) -> None:
    if txn.category_status is CategoryStatus.CONFIRMED and txn.category_source in {
        CategorySource.MANUAL,
        CategorySource.AI,
    }:
        return  # nunca pisar una decisión del usuario

    rule = first_match(
        rules if rules is not None else active_rules(db),
        txn.merchant_normalized,
        txn.merchant_raw,
    )
    if rule:
        _apply(txn, rule.category_id, CategoryStatus.CONFIRMED, CategorySource.RULE)
        return

    previous = db.scalar(
        select(Transaction.category_id)
        .where(
            Transaction.merchant_normalized == txn.merchant_normalized,
            Transaction.category_status == CategoryStatus.CONFIRMED,
            Transaction.id != txn.id,
        )
        .order_by(Transaction.updated_at.desc())
        .limit(1)
    )
    if previous:
        _apply(
            txn,
            previous,
            CategoryStatus.SUGGESTED,
            CategorySource.MANUAL,
            "Mismo comercio que una transacción que ya confirmaste",
        )
        return

    if ai is None:
        return
    categories = {c.name: c.id for c in db.scalars(select(Category))}
    suggestion = ai.suggest(txn.merchant_raw, txn.amount, txn.currency, sorted(categories))
    if suggestion and suggestion.confidence >= AI_MIN_CONFIDENCE:
        _apply(
            txn,
            categories[suggestion.category],
            CategoryStatus.SUGGESTED,
            CategorySource.AI,
            f"{suggestion.reason} (confianza {suggestion.confidence:.0%})",
        )


def _count_affected(db: Session, rule: CategoryRule, exclude_id: int | None = None) -> int:
    pending = db.scalars(
        select(Transaction).where(Transaction.category_status != CategoryStatus.CONFIRMED)
    )
    return sum(
        1
        for t in pending
        if t.id != exclude_id and rule_matches(rule, t.merchant_normalized, t.merchant_raw)
    )


def confirm(db: Session, txn: Transaction, category_id: int) -> RuleSuggestion | None:
    """Confirma (o corrige) la categoría y propone una regla si no existe una que la cubra."""
    if db.get(Category, category_id) is None:
        raise ValueError("categoría inexistente")
    same_as_ai = txn.category_source is CategorySource.AI and txn.category_id == category_id
    _apply(
        txn,
        category_id,
        CategoryStatus.CONFIRMED,
        CategorySource.AI if same_as_ai else CategorySource.MANUAL,
        txn.ai_reason if same_as_ai else None,
    )
    db.commit()

    existing = first_match(active_rules(db), txn.merchant_normalized, txn.merchant_raw)
    if existing and existing.category_id == category_id:
        return None
    candidate = CategoryRule(
        match_type=MatchType.CONTAINS, pattern=txn.merchant_normalized, category_id=category_id
    )
    return RuleSuggestion(
        match_type=candidate.match_type,
        pattern=candidate.pattern,
        category_id=category_id,
        would_affect=_count_affected(db, candidate, exclude_id=txn.id),
    )


def apply_rule_to_pending(db: Session, rule: CategoryRule) -> int:
    """Aplica una regla nueva a lo que todavía no está confirmado por el usuario."""
    changed = 0
    pending = db.scalars(
        select(Transaction).where(Transaction.category_status != CategoryStatus.CONFIRMED)
    )
    for txn in pending:
        if rule_matches(rule, txn.merchant_normalized, txn.merchant_raw):
            _apply(txn, rule.category_id, CategoryStatus.CONFIRMED, CategorySource.RULE)
            changed += 1
    return changed
