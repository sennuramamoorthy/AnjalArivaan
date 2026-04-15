from .interface import IEmailForwardAdapter


class MockEmailForwardAdapter(IEmailForwardAdapter):
    """In-memory email forward adapter for unit tests."""

    def __init__(self):
        self._forwarded: list[dict] = []

    async def forward(
        self,
        original_mail_id: str,
        to_email: str,
        from_account_token: str,
        note: str,
    ) -> None:
        self._forwarded.append(
            {
                "original_mail_id": original_mail_id,
                "to_email": to_email,
                "from_account_token": from_account_token,
                "note": note,
            }
        )

    def get_forwarded_mails(self) -> list[dict]:
        return list(self._forwarded)

    def reset(self) -> None:
        self._forwarded.clear()
