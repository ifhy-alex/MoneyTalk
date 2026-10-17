from fastapi import APIRouter

from moneytalk.api import accounts, categories, health, ingestion, transactions

router = APIRouter()
for module in (health, accounts, ingestion, transactions, categories):
    router.include_router(module.router)
