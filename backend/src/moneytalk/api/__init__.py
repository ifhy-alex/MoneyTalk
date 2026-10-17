from fastapi import APIRouter

from moneytalk.api import (
    accounts,
    analysis,
    categories,
    finance,
    health,
    ingestion,
    investments,
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
    analysis,
):
    router.include_router(module.router)
