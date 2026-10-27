"""Business logic. Services validate permissions and invariants and own DB commits.

Routers in app/api/v1/ call one service function per request. Services use repositories for
queries and return Pydantic schemas (app/schemas/) ready to be sent as JSON.
"""
