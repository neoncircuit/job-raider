"""Declarative base — imported by both models and Alembic env.py.

Kept separate from connection.py so that Alembic can import Base
without triggering async engine creation.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
