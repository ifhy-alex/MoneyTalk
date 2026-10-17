from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from moneytalk.api.transactions import TransactionOut, load, to_out
from moneytalk.categorization.rules import rule_matches, validate_pattern
from moneytalk.categorization.service import apply_rule_to_pending, confirm
from moneytalk.db import get_db
from moneytalk.models import Category, CategoryKind, CategoryRule, MatchType, Transaction

router = APIRouter(tags=["categorías"])
DB = Annotated[Session, Depends(get_db)]


class CategoryIn(BaseModel):
    name: str
    parent_id: int | None = None
    kind: CategoryKind = CategoryKind.EXPENSE
    is_subscription: bool = False


class CategoryOut(CategoryIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RuleIn(BaseModel):
    match_type: MatchType
    pattern: str
    category_id: int
    priority: int = 100
    is_active: bool = True
    created_from_transaction_id: int | None = None


class RuleOut(RuleIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category_name: str


class RuleCreateResult(BaseModel):
    rule: RuleOut
    applied_to: int


class ConfirmIn(BaseModel):
    category_id: int


class RuleSuggestionOut(BaseModel):
    match_type: MatchType
    pattern: str
    category_id: int
    would_affect: int


class ConfirmOut(BaseModel):
    transaction: TransactionOut
    rule_suggestion: RuleSuggestionOut | None


class RulePreviewOut(BaseModel):
    matches: int
    examples: list[str]


def _rule_out(rule: CategoryRule) -> RuleOut:
    return RuleOut(
        id=rule.id,
        match_type=rule.match_type,
        pattern=rule.pattern,
        category_id=rule.category_id,
        priority=rule.priority,
        is_active=rule.is_active,
        created_from_transaction_id=rule.created_from_transaction_id,
        category_name=rule.category.name,
    )


# --- Categorías ---


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: DB) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.kind, Category.name)))


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(db: DB, body: CategoryIn) -> Category:
    cat = Category(**body.model_dump())
    db.add(cat)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="ya existe una categoría con ese nombre"
        ) from exc
    return cat


@router.patch("/categories/{cat_id}", response_model=CategoryOut)
def update_category(db: DB, cat_id: int, body: CategoryIn) -> Category:
    cat = db.get(Category, cat_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="categoría no encontrada")
    for key, value in body.model_dump().items():
        setattr(cat, key, value)
    db.commit()
    return cat


@router.delete("/categories/{cat_id}", status_code=204)
def delete_category(db: DB, cat_id: int) -> None:
    cat = db.get(Category, cat_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="categoría no encontrada")
    db.delete(cat)
    db.commit()


# --- Reglas ---


@router.get("/rules", response_model=list[RuleOut])
def list_rules(db: DB) -> list[RuleOut]:
    rules = db.scalars(select(CategoryRule).order_by(CategoryRule.priority.desc(), CategoryRule.id))
    return [_rule_out(r) for r in rules]


@router.post("/rules/preview", response_model=RulePreviewOut)
def preview_rule(db: DB, body: RuleIn) -> RulePreviewOut:
    try:
        validate_pattern(body.match_type, body.pattern)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    rule = CategoryRule(**body.model_dump())
    merchants = {
        t.merchant_raw
        for t in db.scalars(select(Transaction))
        if rule_matches(rule, t.merchant_normalized, t.merchant_raw)
    }
    return RulePreviewOut(matches=len(merchants), examples=sorted(merchants)[:10])


@router.post("/rules", response_model=RuleCreateResult, status_code=201)
def create_rule(db: DB, body: RuleIn, apply_to_pending: bool = True) -> RuleCreateResult:
    try:
        validate_pattern(body.match_type, body.pattern)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if db.get(Category, body.category_id) is None:
        raise HTTPException(status_code=422, detail="categoría inexistente")
    rule = CategoryRule(**body.model_dump())
    db.add(rule)
    db.flush()
    applied = apply_rule_to_pending(db, rule) if apply_to_pending else 0
    db.commit()
    db.refresh(rule)
    return RuleCreateResult(rule=_rule_out(rule), applied_to=applied)


@router.patch("/rules/{rule_id}", response_model=RuleOut)
def update_rule(db: DB, rule_id: int, body: RuleIn) -> RuleOut:
    rule = db.get(CategoryRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="regla no encontrada")
    try:
        validate_pattern(body.match_type, body.pattern)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    for key, value in body.model_dump().items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return _rule_out(rule)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(db: DB, rule_id: int) -> None:
    rule = db.get(CategoryRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="regla no encontrada")
    db.delete(rule)
    db.commit()


# --- Confirmación de categorías ---


@router.post("/transactions/{txn_id}/category", response_model=ConfirmOut)
def confirm_category(db: DB, txn_id: int, body: ConfirmIn) -> ConfirmOut:
    txn = load(db, txn_id)
    try:
        suggestion = confirm(db, txn, body.category_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.refresh(txn)
    return ConfirmOut(
        transaction=to_out(txn),
        rule_suggestion=RuleSuggestionOut(**suggestion.__dict__) if suggestion else None,
    )
