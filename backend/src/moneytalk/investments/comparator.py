"""Comparador con alternativas locales de renta fija (CDP, bonos, fondos).

Supuestos explícitos (todos editables en la solicitud):
- Impuesto sobre rendimientos de renta fija en CR: 15 % retenido en la fuente (por opción).
- Interés simple por defecto: así pagan la mayoría de CDP (cupón no reinvertido).
- Para comparar colones con dólares hace falta un supuesto de variación cambiaria
  anual; se reporta también el punto de equilibrio (la variación que iguala ambas).
- Rendimiento real = (1 + nominal neto) / (1 + inflación) − 1.
"""

from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, Field

ONE = Decimal(1)


class OptionIn(BaseModel):
    name: str
    currency: str = Field(pattern="^(CRC|USD)$")
    annual_rate: Decimal = Field(ge=-1, le=1)
    tax_rate: Decimal = Field(default=Decimal("0.15"), ge=0, le=1)
    compounding: str = Field(default="simple", pattern="^(simple|monthly|annual)$")


class CompareRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="CRC", pattern="^(CRC|USD)$")
    months: int = Field(gt=0, le=600)
    fx_rate: Decimal = Field(gt=0, description="colones por dólar al inicio")
    colon_depreciation: Decimal = Field(
        default=Decimal("0"),
        description="variación anual esperada del tipo de cambio (0.02 = +2 %)",
    )
    inflation: Decimal = Field(
        default=Decimal("0.03"), description="inflación anual esperada (CRC)"
    )
    options: list[OptionIn] = Field(min_length=1)


@dataclass(frozen=True)
class CompareRow:
    name: str
    currency: str
    gross_rate: Decimal
    gross_interest: Decimal  # en la moneda de la opción
    tax: Decimal
    net_interest: Decimal
    final_value: Decimal  # en la moneda de la opción
    final_value_base: Decimal  # en la moneda base de la solicitud
    net_annual_yield_base: Decimal  # anualizado efectivo, en moneda base
    real_annual_yield: Decimal


def _grow(principal: Decimal, rate: Decimal, months: int, compounding: str) -> Decimal:
    """Interés bruto acumulado al final del plazo."""
    years = months / 12
    if compounding == "simple":
        return principal * rate * Decimal(str(years))
    n = 12 if compounding == "monthly" else 1
    factor = (1 + float(rate) / n) ** (n * years)
    return principal * (Decimal(str(factor)) - ONE)


def _annualize(total_return: Decimal, months: int) -> Decimal:
    if total_return <= -1:
        return Decimal(-1)
    return Decimal(str(float(ONE + total_return) ** (12 / months) - 1)).quantize(Decimal("0.00001"))


def compare(req: CompareRequest) -> tuple[list[CompareRow], dict[str, Decimal | None]]:
    years = Decimal(req.months) / 12
    end_fx = req.fx_rate * Decimal(str((1 + float(req.colon_depreciation)) ** float(years)))
    rows = []
    for o in req.options:
        # Convertir el monto a la moneda de la opción al tipo de hoy.
        if o.currency == req.currency:
            principal = req.amount
        elif o.currency == "USD":
            principal = req.amount / req.fx_rate
        else:
            principal = req.amount * req.fx_rate
        gross = _grow(principal, o.annual_rate, req.months, o.compounding)
        tax = max(gross, Decimal(0)) * o.tax_rate
        net = gross - tax
        final = principal + net
        if o.currency == req.currency:
            final_base = final
        elif o.currency == "USD":
            final_base = final * end_fx
        else:
            final_base = final / end_fx
        total_return = final_base / req.amount - 1
        net_annual = _annualize(total_return, req.months)
        base_inflation = req.inflation if req.currency == "CRC" else Decimal("0")
        real = ((ONE + net_annual) / (ONE + base_inflation) - 1).quantize(Decimal("0.00001"))
        q = Decimal("0.01")
        rows.append(
            CompareRow(
                o.name,
                o.currency,
                o.annual_rate,
                gross.quantize(q),
                tax.quantize(q),
                net.quantize(q),
                final.quantize(q),
                final_base.quantize(q),
                net_annual,
                real,
            )
        )
    return rows, {
        "end_fx_rate": end_fx.quantize(Decimal("0.01")),
        "break_even_depreciation": break_even(req),
    }


def break_even(req: CompareRequest) -> Decimal | None:
    """Variación cambiaria anual que iguala la mejor opción en CRC con la mejor en USD."""

    def net_annual(o: OptionIn) -> float:
        gross = _grow(ONE, o.annual_rate, req.months, o.compounding)
        net = gross - max(gross, Decimal(0)) * o.tax_rate
        return float(float(ONE + net) ** (12 / req.months) - 1)

    crc = [net_annual(o) for o in req.options if o.currency == "CRC"]
    usd = [net_annual(o) for o in req.options if o.currency == "USD"]
    if not crc or not usd:
        return None
    # (1 + r_usd)(1 + d) = 1 + r_crc  →  d = (1 + r_crc)/(1 + r_usd) − 1
    return Decimal(str((1 + max(crc)) / (1 + max(usd)) - 1)).quantize(Decimal("0.00001"))
