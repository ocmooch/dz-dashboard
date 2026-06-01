"""Pure analytics functions: database rows -> metrics.

Nothing in this package imports FastAPI. Each function takes a SQLAlchemy
``Session`` (read-only) and returns plain data structures the API layer wraps
in the response envelope. This is where Phase 2's correctness lives, so it is
where the unit tests concentrate.
"""
