"""External integration ports + adapters (Hexagonal architecture).

All external systems (Google, WhatsApp, Vault, LLM, vector, search, storage) are
accessed via an interface (Protocol) and at least two implementations:
  - a real adapter (hits the live service)
  - a stub adapter (used in tests + local dev without external credentials)
"""
