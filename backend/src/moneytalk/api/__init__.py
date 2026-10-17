from fastapi import APIRouter

from moneytalk.api import accounts, health, ingestion, transactions

router = APIRouter()
for module in (health, accounts, ingestion, transactions):
    router.include_router(module.router)
