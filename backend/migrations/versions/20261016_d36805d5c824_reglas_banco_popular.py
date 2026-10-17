"""reglas banco popular

Conceptos genéricos que aparecen en los reportes de movimientos de cuentas.

Revision ID: d36805d5c824
Revises: 7082522e57fe
Create Date: 2026-10-16 21:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d36805d5c824"
down_revision: str | None = "7082522e57fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RULES: list[tuple[str, str]] = [
    ("COMISION", "Comisiones bancarias"),
    ("INTERES CREDITO", "Intereses y rendimientos"),
    ("PARQUIMETRO", "Transporte"),
    ("SUPERCELL", "Entretenimiento"),
    ("STEAM", "Entretenimiento"),
]

categories = sa.table("categories", sa.column("id", sa.Integer), sa.column("name", sa.String))
rules = sa.table(
    "category_rules",
    sa.column("match_type", sa.String),
    sa.column("pattern", sa.String),
    sa.column("category_id", sa.Integer),
    sa.column("priority", sa.Integer),
    sa.column("is_active", sa.Boolean),
)


def upgrade() -> None:
    ids = dict(op.get_bind().execute(sa.select(categories.c.name, categories.c.id)).all())
    rows = [
        {
            "match_type": "contains",
            "pattern": pattern,
            "category_id": ids[cat],
            "priority": 100 + len(pattern),
            "is_active": True,
        }
        for pattern, cat in RULES
        if cat in ids
    ]
    if rows:
        op.bulk_insert(rules, rows)


def downgrade() -> None:
    op.execute(rules.delete().where(rules.c.pattern.in_([p for p, _ in RULES])))
