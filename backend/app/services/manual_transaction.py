"""Compatibility import for callers migrating to TransactionService."""

from app.services.transactions import TransactionService

ManualTransactionService = TransactionService

__all__ = ["ManualTransactionService", "TransactionService"]
