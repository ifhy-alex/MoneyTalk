from fastapi import APIRouter

from moneytalk.api import accounts, categories, finance, health, ingestion, transactions

router = APIRouter()
for module in (health, accounts, ingestion, transactions, categories, finance):
    router.include_router(module.router)
