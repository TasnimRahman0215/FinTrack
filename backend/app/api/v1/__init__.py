"""Version 1 of the REST API, mounted at /api/v1 by app/main.py. Routers stay thin: they
parse input, check auth via dependencies, call one service function and return a schema.
"""
