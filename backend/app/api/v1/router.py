"""Collects every v1 router. Add a new feature's router to the tuple below."""

from fastapi import APIRouter

from app.api.v1 import accounts, auth, connections, health, household, summary, sync, transactions

api_router = APIRouter()
for module in (health, auth, household, connections, sync, accounts, transactions, summary):
    api_router.include_router(module.router)
