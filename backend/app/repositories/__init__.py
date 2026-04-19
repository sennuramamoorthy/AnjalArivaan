"""Repository layer — Data Access abstraction.

Every repository extends `BaseRepository[T]` (generic CRUD). Account-scoped
repositories MUST filter by `owner_account_id` to enforce PRD §8.2 isolation.
"""
