"""Repositories hold every DB query. They flush but never commit; services own transactions.

One module per table, called from app/services/. Reads that return financial data take the
account IDs from a resolved scope (core/scope.py), so they can't return data the user may not see.
"""
