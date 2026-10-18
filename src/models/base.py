"""
Shared SQLAlchemy declarative base.

All ORM models must import Base from here (not create their own
declarative_base()) so they register into the same metadata that
src.infrastructure.database.init_db() uses to create tables.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
