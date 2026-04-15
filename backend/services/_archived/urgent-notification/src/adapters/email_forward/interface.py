from abc import ABC, abstractmethod


class IEmailForwardAdapter(ABC):
    @abstractmethod
    async def forward(
        self,
        original_mail_id: str,        # Gmail message ID
        to_email: str,
        from_account_token: str,
        note: str,
    ) -> None:
        """
        Forward an existing Gmail message to to_email using the sender's account token.

        Implementations should prepend `note` as a brief context header above the
        original message body.
        """
        ...
