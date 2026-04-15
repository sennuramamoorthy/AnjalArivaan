"""SearchService — Phase 1a search using PostgreSQL ILIKE.

Delegates to the mail repository's list_by_account with a search param.
OpenSearch integration is deferred to Phase 1b.
"""


class SearchService:
    def __init__(self, mail_repo) -> None:
        self._mail_repo = mail_repo

    async def search_mail(
        self,
        account_id: str,
        query: str,
        *,
        filter: str = "all",
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """Search mail for a given account. Returns paginated results dict."""
        msgs, total = await self._mail_repo.list_by_account(
            account_id,
            filter=filter,
            search=query,
            page=page,
            page_size=page_size,
        )

        has_more = (page * page_size) < total

        return {
            "results": msgs,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "hasMore": has_more,
        }
