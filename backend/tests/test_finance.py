from datetime import date, timedelta
from decimal import Decimal

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from moneytalk.config import Settings
from moneytalk.finance.alerts import run_alerts
from moneytalk.finance.fx import BccrClient, FxConverter, parse_bccr_xml, sync_rates
from moneytalk.finance.prefs import Preferences
from moneytalk.finance.reports import budget_status, emergency_fund_target, totals
from moneytalk.finance.summary import weekly_summary
from moneytalk.models import AlertKind, Budget, ExchangeRate
from moneytalk.notifications.telegram import TelegramNotifier
from tests import factories as f
from tests.conftest import FIXTURES

OCT = date(2026, 10, 1)


def test_parse_bccr_xml() -> None:
    values = parse_bccr_xml((FIXTURES / "bccr_317.xml").read_text(encoding="utf-8"))
    assert values == {
        date(2026, 10, 15): Decimal("503.1200"),
        date(2026, 10, 16): Decimal("504.0100"),
    }


def test_bccr_client_sends_subscription_params(db: Session) -> None:
    xml = (FIXTURES / "bccr_317.xml").read_text(encoding="utf-8")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=xml)

    client = BccrClient(
        Settings(bccr_email="x@example.com", bccr_token="TOKEN"),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    n = sync_rates(db, client, date(2026, 10, 15), date(2026, 10, 16))
    assert n == 2
    assert seen[0].url.params["Indicador"] == "317"
    assert seen[1].url.params["Indicador"] == "318"
    assert seen[0].url.params["FechaInicio"] == "15/10/2026"
    # Idempotente: reescribir no duplica
    assert sync_rates(db, client, date(2026, 10, 15), date(2026, 10, 16)) == 2
    assert len(db.scalars(select(ExchangeRate)).all()) == 2


def test_fx_converter_uses_previous_available_rate(db: Session) -> None:
    f.rate(db, date(2026, 10, 9), sell="510.00")  # viernes
    fx = FxConverter(db)
    # El fin de semana no hay dato: usa el del viernes
    assert fx.convert(Decimal("10"), "USD", "CRC", date(2026, 10, 11)) == Decimal("5100.00")
    assert fx.convert(Decimal("5100"), "CRC", "USD", date(2026, 10, 11)) == Decimal("10.00")


def test_totals_exclude_transfers_and_convert_usd(db: Session) -> None:
    f.rate(db, OCT, sell="500.00")
    txns = [
        f.txn(db, date(2026, 10, 2), "-10000", "AUTO MERCADO", category_name="Supermercado"),
        f.txn(db, date(2026, 10, 3), "-12.00", "NETFLIX", "USD", category_name="Suscripciones"),
        f.txn(db, date(2026, 10, 5), "-100000", "SU PAGO", category_name="Pago de tarjeta"),
        f.txn(db, date(2026, 10, 6), "800000", "PLANILLA", category_name="Salario"),
        f.txn(
            db, date(2026, 10, 7), "2000", "AUTO MERCADO", category_name="Supermercado"
        ),  # devolución
    ]
    t = totals(txns, FxConverter(db))
    assert t.expenses == Decimal("14000.00")  # 10000 + 6000 - 2000
    assert t.income == Decimal("800000")
    assert t.by_category["Supermercado"] == Decimal("8000")
    assert t.transfers == Decimal("-100000")


def test_budget_status_mixes_currencies(db: Session) -> None:
    f.rate(db, OCT, sell="500.00")
    subs = f.category(db, "Suscripciones")
    db.add(Budget(category_id=subs.id, amount=Decimal("20.00"), currency="USD"))
    f.txn(db, date(2026, 10, 3), "-12.00", "NETFLIX", "USD", category_name="Suscripciones")
    f.txn(db, date(2026, 10, 4), "-2500", "KOLBI APP", category_name="Suscripciones")
    [status] = budget_status(db, OCT, FxConverter(db))
    assert status.spent == Decimal("17.00")  # 12 USD + 2500/500
    assert status.ratio == 0.85


def test_month_override_beats_default_budget(db: Session) -> None:
    f.rate(db, OCT)
    sup = f.category(db, "Supermercado")
    db.add_all(
        [
            Budget(category_id=sup.id, amount=Decimal("100000"), currency="CRC"),
            Budget(category_id=sup.id, month=OCT, amount=Decimal("150000"), currency="CRC"),
        ]
    )
    db.flush()
    [status] = budget_status(db, OCT, FxConverter(db))
    assert status.budgeted == Decimal("150000") and status.is_override
    [nov] = budget_status(db, date(2026, 11, 1), FxConverter(db))
    assert nov.budgeted == Decimal("100000")


def test_alerts_budget_unusual_and_subscriptions(db: Session) -> None:
    f.rate(db, date(2026, 6, 1), sell="500.00")
    sup = f.category(db, "Supermercado")
    db.add(Budget(category_id=sup.id, amount=Decimal("100000"), currency="CRC"))
    # Historial normal de supermercado (10 compras de ~10 000)
    for i in range(10):
        f.txn(
            db,
            date(2026, 9, 1) + timedelta(days=i * 3),
            str(-10000 - i * 100),
            "PALI",
            category_name="Supermercado",
        )
    big = f.txn(db, date(2026, 10, 14), "-95000", "PRICESMART", category_name="Supermercado")
    f.txn(db, date(2026, 10, 15), "-12.99", "NETFLIX", "USD", category_name="Suscripciones")
    f.txn(db, date(2026, 10, 16), "-12.99", "NETFLIX", "USD", category_name="Suscripciones")

    created = run_alerts(db, FxConverter(db), Preferences(), today=date(2026, 10, 16))
    kinds = {a.kind for a in created}
    assert AlertKind.UNUSUAL_SPEND in kinds
    assert AlertKind.BUDGET_NEAR_LIMIT in kinds  # 95 000 de 100 000
    assert AlertKind.NEW_SUBSCRIPTION in kinds
    assert AlertKind.DUPLICATE_SUBSCRIPTION in kinds
    unusual = next(a for a in created if a.kind is AlertKind.UNUSUAL_SPEND)
    assert unusual.transaction_id == big.id
    assert unusual.evidence["muestras"] == 10

    # Correr de nuevo no repite alertas
    assert run_alerts(db, FxConverter(db), Preferences(), today=date(2026, 10, 16)) == []


def test_recurring_charge_outside_subscription_category(db: Session) -> None:
    f.rate(db, date(2026, 6, 1))
    for month in (8, 9, 10):
        f.txn(db, date(2026, month, 5), "-15000", "GIMNASIO ZETA", category_name="Salud")
    created = run_alerts(
        db, FxConverter(db), Preferences(), today=date(2026, 10, 6), since=date(2026, 10, 1)
    )
    assert any("recurrente" in a.message for a in created)


def test_emergency_fund_target(db: Session) -> None:
    f.rate(db, date(2026, 6, 1))
    for month in (7, 8, 9):
        f.txn(db, date(2026, month, 10), "-300000", "ALQUILER", category_name="Hogar")
    target = emergency_fund_target(db, FxConverter(db), date(2026, 10, 16), months_of_expenses=6)
    assert target == Decimal("1800000.00")


def test_weekly_summary_and_telegram(db: Session) -> None:
    f.rate(db, date(2026, 10, 1))
    f.txn(db, date(2026, 10, 13), "-20000", "AUTO MERCADO", category_name="Supermercado")
    text = weekly_summary(db, FxConverter(db), date(2026, 10, 19))
    assert "Resumen semanal" in text and "Supermercado" in text and "₡20,000" in text

    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    notifier = TelegramNotifier(
        Settings(telegram_bot_token="t", telegram_chat_id="42"),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert notifier.send(text)
    assert sent[0]["chat_id"] == "42" and sent[0]["parse_mode"] == "HTML"
    assert not TelegramNotifier(Settings()).enabled


def test_dashboard_and_goals_api(client: TestClient, db: Session) -> None:
    assert client.get("/api/dashboard", params={"month": "2026-10"}).status_code == 409  # sin FX
    f.rate(db, date(2026, 5, 1))
    f.txn(db, date(2026, 10, 2), "-10000", "AUTO MERCADO", category_name="Supermercado")
    sup = f.category(db, "Supermercado")
    assert (
        client.post(
            "/api/budgets", json={"category_id": sup.id, "amount": "50000", "currency": "CRC"}
        ).status_code
        == 201
    )

    ef = client.post(
        "/api/goals",
        json={
            "name": "Fondo de emergencia",
            "target_amount": "1000000",
            "currency": "CRC",
            "is_emergency_fund": True,
            "monthly_contribution": "100000",
        },
    )
    assert ef.status_code == 201
    dup = client.post(
        "/api/goals",
        json={"name": "Otro", "target_amount": "1", "currency": "CRC", "is_emergency_fund": True},
    )
    assert dup.status_code == 409
    client.post(
        f"/api/goals/{ef.json()['id']}/contributions",
        json={"date": "2026-10-01", "amount": "250000"},
    )

    dash = client.get("/api/dashboard", params={"month": "2026-10"}).json()
    assert Decimal(dash["expenses"]) == Decimal("10000")
    assert dash["budgets"][0]["ratio"] == 0.2
    goal = dash["goals"][0]
    assert goal["ratio"] == 0.25 and goal["months_to_target"] == 8
    assert len(dash["trend"]) == 6

    prefs = client.put("/api/preferences", json={"emergency_fund_months": 4}).json()
    assert prefs["emergency_fund_months"] == 4
    assert client.put("/api/preferences", json={"emergency_fund_months": 99}).status_code == 422
