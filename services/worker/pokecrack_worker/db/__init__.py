"""Database execution contracts. Credentials are accepted but never rendered."""

from .postgres import PsycopgQueryExecutor

__all__ = ["PsycopgQueryExecutor"]
