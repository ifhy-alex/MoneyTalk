"""categorias y reglas base

Datos iniciales editables desde la interfaz. El downgrade solo borra lo que sembró y
nunca toca categorías o reglas creadas por el usuario.

Revision ID: fe7bd71c2854
Revises: 11f13876b9b8
Create Date: 2026-10-16 20:08:56.067274
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fe7bd71c2854"
down_revision: str | None = "11f13876b9b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES: list[tuple[str, str, bool]] = [
    ("Supermercado", "expense", False),
    ("Restaurantes y café", "expense", False),
    ("Transporte", "expense", False),
    ("Combustible", "expense", False),
    ("Servicios públicos", "expense", False),
    ("Internet y teléfono", "expense", False),
    ("Suscripciones", "expense", True),
    ("Salud", "expense", False),
    ("Educación", "expense", False),
    ("Entretenimiento", "expense", False),
    ("Compras", "expense", False),
    ("Hogar", "expense", False),
    ("Viajes", "expense", False),
    ("Seguros", "expense", False),
    ("Impuestos y trámites", "expense", False),
    ("Comisiones bancarias", "expense", False),
    ("Otros gastos", "expense", False),
    ("Salario", "income", False),
    ("Intereses y rendimientos", "income", False),
    ("Otros ingresos", "income", False),
    ("Pago de tarjeta", "transfer", False),
    ("Transferencia entre cuentas", "transfer", False),
    ("Ahorro e inversión", "transfer", False),
]

RULES: list[tuple[str, str, str]] = [
    ("contains", "SU PAGO", "Pago de tarjeta"),
    ("contains", "AUTO MERCADO", "Supermercado"),
    ("contains", "AUTOMERCADO", "Supermercado"),
    ("contains", "WALMART", "Supermercado"),
    ("contains", "MAS X MENOS", "Supermercado"),
    ("contains", "MAXI PALI", "Supermercado"),
    ("contains", "PALI", "Supermercado"),
    ("contains", "FRESH MARKET", "Supermercado"),
    ("contains", "PRICESMART", "Supermercado"),
    ("contains", "UBER EATS", "Restaurantes y café"),
    ("contains", "UBER", "Transporte"),
    ("contains", "DIDI", "Transporte"),
    ("contains", "NETFLIX", "Suscripciones"),
    ("contains", "SPOTIFY", "Suscripciones"),
    ("contains", "DISNEY", "Suscripciones"),
    ("contains", "YOUTUBE", "Suscripciones"),
    ("contains", "ICLOUD", "Suscripciones"),
    ("regex", r"\b(ICE|KOLBI)\b", "Internet y teléfono"),
    ("contains", "LIBERTY", "Internet y teléfono"),
    ("contains", "CNFL", "Servicios públicos"),
    ("contains", "AYA", "Servicios públicos"),
    ("regex", r"\b(DELTA|GAZEL|SERVICENTRO|BOMBA)\b", "Combustible"),
    ("contains", "FARMACIA", "Salud"),
    ("contains", "FISCHEL", "Salud"),
]

categories = sa.table(
    "categories",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("kind", sa.String),
    sa.column("is_subscription", sa.Boolean),
    sa.column("parent_id", sa.Integer),
)
rules = sa.table(
    "category_rules",
    sa.column("match_type", sa.String),
    sa.column("pattern", sa.String),
    sa.column("category_id", sa.Integer),
    sa.column("priority", sa.Integer),
    sa.column("is_active", sa.Boolean),
)


def upgrade() -> None:
    conn = op.get_bind()
    op.bulk_insert(
        categories,
        [{"name": n, "kind": k, "is_subscription": s, "parent_id": None} for n, k, s in CATEGORIES],
    )
    ids = dict(conn.execute(sa.select(categories.c.name, categories.c.id)).all())
    # "UBER EATS" antes que "UBER": las reglas más específicas llevan más prioridad.
    op.bulk_insert(
        rules,
        [
            {
                "match_type": mt,
                "pattern": pattern,
                "category_id": ids[cat],
                "priority": 100 + len(pattern),
                "is_active": True,
            }
            for mt, pattern, cat in RULES
        ],
    )


def downgrade() -> None:
    seeded = [p for _, p, _ in RULES]
    op.execute(rules.delete().where(rules.c.pattern.in_(seeded)))
    op.execute(
        categories.delete().where(
            categories.c.name.in_([n for n, _, _ in CATEGORIES]), categories.c.parent_id.is_(None)
        )
    )
