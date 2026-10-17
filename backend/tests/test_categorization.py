from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.categorization.ai import AiSuggestion
from moneytalk.categorization.service import categorize, confirm
from moneytalk.ingestion import service
from moneytalk.models import Category, CategorySource, CategoryStatus, Transaction
from tests.helpers import email_fixture, statement_pdf

BAC_SENDER = "notificacion@notificacionesbaccr.com"


class FakeAi:
    def __init__(self, category: str | None, confidence: float = 0.9) -> None:
        self.category = category
        self.confidence = confidence
        self.calls = 0

    def suggest(
        self, merchant: str, amount: Decimal, currency: str, categories: list[str]
    ) -> AiSuggestion | None:
        self.calls += 1
        if self.category is None:
            return None
        return AiSuggestion(category=self.category, confidence=self.confidence, reason="test")


def _by_merchant(db: Session, needle: str) -> Transaction:
    return db.scalars(select(Transaction).where(Transaction.merchant_raw.contains(needle))).one()


def _cat(db: Session, name: str) -> Category:
    return db.scalars(select(Category).where(Category.name == name)).one()


def _ingest(db: Session, ai: FakeAi | None = None) -> None:
    service.ingest_pdf(db, statement_pdf(), on_new=lambda d, t: categorize(d, t, ai))


def test_seed_rules_categorize_on_ingest(db: Session) -> None:
    _ingest(db)
    assert _by_merchant(db, "AUTOMERCADO").category_id == _cat(db, "Supermercado").id
    assert _by_merchant(db, "SU PAGO").category_id == _cat(db, "Pago de tarjeta").id
    assert _by_merchant(db, "SPOTIFY").category_id == _cat(db, "Suscripciones").id
    uber = _by_merchant(db, "UBER")
    assert uber.category_status is CategoryStatus.CONFIRMED
    assert uber.category_source is CategorySource.RULE


def test_ai_fallback_is_only_a_suggestion(db: Session) -> None:
    ai = FakeAi("Entretenimiento")
    service.ingest_email(
        db,
        email_fixture("bac_devolucion.html", BAC_SENDER),  # AMAZON: sin regla
        on_new=lambda d, t: categorize(d, t, ai),
    )
    txn = _by_merchant(db, "AMAZON")
    assert ai.calls == 1
    assert txn.category_status is CategoryStatus.SUGGESTED
    assert txn.category_source is CategorySource.AI
    assert txn.ai_reason and "90%" in txn.ai_reason


def test_low_confidence_ai_is_ignored(db: Session) -> None:
    service.ingest_email(
        db,
        email_fixture("bac_devolucion.html", BAC_SENDER),
        on_new=lambda d, t: categorize(d, t, FakeAi("Compras", confidence=0.2)),
    )
    assert _by_merchant(db, "AMAZON").category_status is CategoryStatus.UNCATEGORIZED


def test_confirm_proposes_rule_and_merchant_memory(db: Session) -> None:
    service.ingest_email(db, email_fixture("bac_devolucion.html", BAC_SENDER))
    txn = _by_merchant(db, "AMAZON")
    compras = _cat(db, "Compras")
    suggestion = confirm(db, txn, compras.id)
    assert txn.category_status is CategoryStatus.CONFIRMED
    assert suggestion is not None
    assert suggestion.pattern == "AMAZON MKTPLACE"

    # Otra transacción del mismo comercio se sugiere sin llamar a la IA
    ai = FakeAi("Entretenimiento")
    other = Transaction(
        account_id=txn.account_id,
        txn_date=txn.txn_date,
        amount=Decimal("-10"),
        currency="USD",
        merchant_raw="AMAZON MKTPLACE",
        merchant_normalized="AMAZON MKTPLACE",
    )
    db.add(other)
    db.flush()
    categorize(db, other, ai)
    assert ai.calls == 0
    assert other.category_id == compras.id
    assert other.category_status is CategoryStatus.SUGGESTED


def test_rules_never_override_manual_confirmation(db: Session) -> None:
    _ingest(db)
    uber = _by_merchant(db, "UBER")
    viajes = _cat(db, "Viajes")
    confirm(db, uber, viajes.id)
    categorize(db, uber)
    assert uber.category_id == viajes.id


def test_rule_api_flow(client: TestClient, db: Session) -> None:
    service.ingest_email(db, email_fixture("bac_devolucion.html", BAC_SENDER))
    txn = _by_merchant(db, "AMAZON")
    compras = _cat(db, "Compras")

    resp = client.post(f"/api/transactions/{txn.id}/category", json={"category_id": compras.id})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["transaction"]["category_name"] == "Compras"
    assert body["rule_suggestion"]["pattern"] == "AMAZON MKTPLACE"

    preview = client.post(
        "/api/rules/preview",
        json={"match_type": "contains", "pattern": "AMAZON", "category_id": compras.id},
    ).json()
    assert preview["matches"] == 1

    bad = client.post(
        "/api/rules", json={"match_type": "regex", "pattern": "([", "category_id": compras.id}
    )
    assert bad.status_code == 422

    created = client.post(
        "/api/rules",
        json={"match_type": "contains", "pattern": "AMAZON", "category_id": compras.id},
    )
    assert created.status_code == 201
    assert created.json()["rule"]["category_name"] == "Compras"
    assert any(r["pattern"] == "AMAZON" for r in client.get("/api/rules").json())


def test_contains_rule_matches_whole_words_only() -> None:
    from moneytalk.categorization.rules import rule_matches
    from moneytalk.models import CategoryRule, MatchType

    rule = CategoryRule(match_type=MatchType.CONTAINS, pattern="AYA", category_id=1)
    assert rule_matches(rule, "AYA RECIBO", "AYA RECIBO")
    assert not rule_matches(rule, "HOTEL PLAYA HERMOSA", "HOTEL PLAYA HERMOSA")


class _StubClaude:
    def __init__(self, category: str) -> None:
        self.category = category
        self.prompts: list[str] = []

    def structured(self, *, system: str, prompt: str, schema: type, **_: object) -> object:
        self.prompts.append(prompt)
        return schema(category=self.category, confidence=0.8, reason="r")


def test_claude_categorizer_rejects_invented_categories() -> None:
    from moneytalk.categorization.ai import ClaudeCategorizer

    stub = _StubClaude("Categoría Inventada")
    cat = ClaudeCategorizer(stub)  # type: ignore[arg-type]
    assert cat.suggest("TIENDA X", Decimal("-10"), "USD", ["Compras"]) is None
    stub.category = "Compras"
    result = cat.suggest("TIENDA X", Decimal("-10"), "USD", ["Compras"])
    assert result is not None and result.category == "Compras"
    # El prompt solo lleva comercio, monto y moneda: nada de tarjetas ni cuentas.
    assert "TIENDA X" in stub.prompts[0] and "salida" in stub.prompts[0]
