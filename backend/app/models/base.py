"""SQLAlchemy declarative base.

SQLAlchemy 2.x is used rather than SQLModel deliberately. SQLModel fuses the
persistence model and the API schema into one class, which is convenient but
makes it easy to leak database columns into API payloads — exactly what
section 8 of PROJECT_STANDARD.md ("separate domain logic from transport")
forbids. Keeping ORM models and Pydantic schemas as distinct types means a
column can change without silently reshaping the public contract.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
