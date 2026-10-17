from fastapi import APIRouter

from moneytalk.api import health

router = APIRouter()
router.include_router(health.router)
