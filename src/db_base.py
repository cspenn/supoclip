# start src/db_base.py
"""Declarative base for SupoClip ORM models.

Lives in its own module so that both ``src.models`` (which defines the mapped
classes) and ``src.database`` (which creates the tables) can depend on it
without importing each other — avoiding a ``database <-> models`` import cycle.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""


# end src/db_base.py
