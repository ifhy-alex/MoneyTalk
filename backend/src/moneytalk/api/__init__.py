from fastapi import APIRouter

from moneytalk.api import (
    accounts,
    analysis,
    categories,
    finance,
    health,
    ingestion,
    investments,
    market,
    transactions,
)

router = APIRouter()
for module in (
    health,
    accounts,
    ingestion,
    transactions,
    categories,
    finance,
    investments,
    market,
    analysis,
):
    router.include_router(module.router)
