"""Urgency module — government-mail detection + WhatsApp/line-manager escalation.

Thin namespace on top of the existing :mod:`src.modules.notification` primitives.
The Phase 1a defining pilot feature: run per-role urgency rules against every
new mail and fan out WhatsApp + line-manager forward when it hits.
"""
