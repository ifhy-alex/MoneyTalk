import re
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.ingestion.merchant import normalize_merchant
from moneytalk.models import CategoryRule, MatchType


@lru_cache(maxsize=512)
def _compiled(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


def rule_matches(rule: CategoryRule, merchant_normalized: str, merchant_raw: str) -> bool:
    match rule.match_type:
        case MatchType.EXACT:
            return merchant_normalized == normalize_merchant(rule.pattern)
        case MatchType.CONTAINS:
            # Por palabras completas: "AYA" no debe atrapar "PLAYA HERMOSA".
            return f" {normalize_merchant(rule.pattern)} " in f" {merchant_normalized} "
        case MatchType.REGEX:
            return bool(_compiled(rule.pattern).search(merchant_raw))


def validate_pattern(match_type: MatchType, pattern: str) -> None:
    if not pattern.strip():
        raise ValueError("el patrón no puede estar vacío")
    if match_type is MatchType.REGEX:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"regex inválida: {exc}") from exc


def active_rules(db: Session) -> list[CategoryRule]:
    return list(
        db.scalars(
            select(CategoryRule)
            .where(CategoryRule.is_active)
            .order_by(CategoryRule.priority.desc(), CategoryRule.id)
        )
    )


def first_match(
    rules: list[CategoryRule], merchant_normalized: str, merchant_raw: str
) -> CategoryRule | None:
    return next((r for r in rules if rule_matches(r, merchant_normalized, merchant_raw)), None)
