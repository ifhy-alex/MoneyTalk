"""Tipo de cambio desde el servicio web de indicadores económicos del BCCR.

Requiere suscripción gratuita (correo + token) en
https://www.bccr.fi.cr/indicadores-economicos/servicio-web
Indicadores: 317 = compra, 318 = venta (tipo de cambio de referencia).

Para convertir gastos en USD a colones usamos el tipo de **venta**: es lo que cuesta
conseguir esos dólares; es la vista conservadora para presupuesto.
"""

import bisect
import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from moneytalk.config import Settings
from moneytalk.models import ExchangeRate

log = logging.getLogger(__name__)

BCCR_URL = (
    "https://gee.bccr.fi.cr/Indicadores/Suscripciones/WS/wsindicadoreseconomicos.asmx/"
    "ObtenerIndicadoresEconomicosXML"
)
IND_BUY, IND_SELL = "317", "318"


class FxSource(Protocol):
    label: str

    def series(self, indicator: str, start: date, end: date) -> dict[date, Decimal]: ...


def parse_bccr_xml(payload: str) -> dict[date, Decimal]:
    """El BCCR devuelve un <string> cuyo contenido es *otro* XML escapado."""
    outer = ET.fromstring(payload)  # noqa: S314  fuente oficial vía HTTPS
    inner_text = outer.text or ""
    inner = ET.fromstring(inner_text)  # noqa: S314
    values: dict[date, Decimal] = {}
    for row in inner.iter("INGC011_CAT_INDICADORECONOMIC"):
        raw_date = row.findtext("DES_FECHA")
        raw_value = row.findtext("NUM_VALOR")
        if raw_date and raw_value:
            values[datetime.fromisoformat(raw_date).date()] = Decimal(raw_value).quantize(
                Decimal("0.0001")
            )
    return values


class BccrClient:
    label = "BCCR"

    def __init__(self, settings: Settings, http: httpx.Client | None = None) -> None:
        if not settings.bccr_email or not settings.bccr_token:
            raise RuntimeError("Configurá BCCR_EMAIL y BCCR_TOKEN en .env")
        self._email = settings.bccr_email
        self._token = settings.bccr_token
        self._http = http or httpx.Client(timeout=20)

    def series(self, indicator: str, start: date, end: date) -> dict[date, Decimal]:
        resp = self._http.get(
            BCCR_URL,
            params={
                "Indicador": indicator,
                "FechaInicio": start.strftime("%d/%m/%Y"),
                "FechaFinal": end.strftime("%d/%m/%Y"),
                "Nombre": "MoneyTalk",
                "SubNiveles": "N",
                "CorreoElectronico": self._email,
                "Token": self._token,
            },
        )
        resp.raise_for_status()
        return parse_bccr_xml(resp.text)


class YahooFxSource:
    """Respaldo sin token: tipo de cambio de mercado USD/CRC de Yahoo (símbolo CRC=X).

    No es el tipo de referencia oficial del BCCR ni distingue compra/venta (se usa el
    cierre para ambos). Sirve para tener un valor actual mientras no hay token.
    """

    label = "Yahoo (mercado)"

    def __init__(self) -> None:
        self._cache: dict[tuple[date, date], dict[date, Decimal]] = {}

    def series(self, indicator: str, start: date, end: date) -> dict[date, Decimal]:
        key = (start, end)
        if key not in self._cache:
            import yfinance as yf

            df = yf.Ticker("CRC=X").history(
                start=start.isoformat(), end=(end + timedelta(days=1)).isoformat()
            )
            if df is None or df.empty:
                raise RuntimeError("Yahoo no devolvió el tipo de cambio CRC=X")
            self._cache[key] = {
                idx.date(): Decimal(str(round(float(v), 4))) for idx, v in df["Close"].items()
            }
        return self._cache[key]


def default_source(settings: Settings) -> FxSource:
    if settings.bccr_email and settings.bccr_token:
        return BccrClient(settings)
    return YahooFxSource()


def sync_rates(db: Session, source: FxSource, start: date, end: date) -> int:
    buy = source.series(IND_BUY, start, end)
    sell = source.series(IND_SELL, start, end)
    rows = [
        {"rate_date": d, "buy": buy[d], "sell": sell[d], "source": source.label}
        for d in sorted(buy.keys() & sell.keys())
    ]
    if rows:
        stmt = insert(ExchangeRate).values(rows)
        db.execute(
            stmt.on_conflict_do_update(
                index_elements=[ExchangeRate.rate_date],
                set_={
                    "buy": stmt.excluded.buy,
                    "sell": stmt.excluded.sell,
                    "source": stmt.excluded.source,
                },
                # Un dato de mercado nunca reemplaza al oficial del BCCR.
                where=(ExchangeRate.source != "BCCR") | (stmt.excluded.source == "BCCR"),
            )
        )
        db.commit()
    return len(rows)


def latest_rate(db: Session) -> ExchangeRate | None:
    return db.scalar(select(ExchangeRate).order_by(ExchangeRate.rate_date.desc()).limit(1))


class FxConverter:
    """Convierte montos con el tipo de venta vigente en la fecha (o el último anterior).

    Carga las tasas una vez; pensado para un request o un cálculo de reporte.
    """

    def __init__(self, db: Session, fallback: Decimal | None = None) -> None:
        rates = db.execute(
            select(ExchangeRate.rate_date, ExchangeRate.sell).order_by(ExchangeRate.rate_date)
        ).all()
        self._dates = [r[0] for r in rates]
        self._sell = [r[1] for r in rates]
        self._fallback = fallback

    @property
    def has_rates(self) -> bool:
        return bool(self._dates) or self._fallback is not None

    def sell_on(self, day: date) -> Decimal:
        idx = bisect.bisect_right(self._dates, day) - 1
        if idx >= 0:
            return self._sell[idx]
        if self._sell:
            return self._sell[0]  # antes del primer dato: usar el más antiguo
        if self._fallback is not None:
            return self._fallback
        raise LookupError("No hay tipo de cambio: corré `moneytalk fx-sync`")

    def convert(self, amount: Decimal, from_cur: str, to_cur: str, day: date) -> Decimal:
        if from_cur == to_cur:
            return amount
        rate = self.sell_on(day)
        if from_cur == "USD" and to_cur == "CRC":
            return (amount * rate).quantize(Decimal("0.01"))
        if from_cur == "CRC" and to_cur == "USD":
            return (amount / rate).quantize(Decimal("0.01"))
        raise ValueError(f"conversión no soportada {from_cur}->{to_cur}")


def default_sync_window(db: Session, today: date) -> tuple[date, date]:
    last = latest_rate(db)
    start = (last.rate_date - timedelta(days=3)) if last else today - timedelta(days=365)
    return start, today
