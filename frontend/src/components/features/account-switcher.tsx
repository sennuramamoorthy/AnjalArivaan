"use client";

import useSWR from "swr";
import { accountsApi } from "@/lib/endpoints";
import { useAccount } from "@/hooks/use-account";

export function AccountSwitcher() {
  const { data: accounts, isLoading } = useSWR("/api/v1/accounts", accountsApi.list);
  const { accountId, setAccountId } = useAccount();

  if (isLoading) {
    return <p className="text-xs text-ink-500 px-2">Loading accounts…</p>;
  }

  if (!accounts || accounts.length === 0) {
    return (
      <div className="px-2">
        <p className="text-xs text-ink-500 mb-2">No linked Google account</p>
        <a href="/settings" className="text-xs text-brand-600 hover:underline">
          Link one in Settings →
        </a>
      </div>
    );
  }

  return (
    <div className="px-2">
      <label htmlFor="acct" className="block text-xs text-ink-500 mb-1">
        Linked account
      </label>
      <select
        id="acct"
        className="w-full text-sm border border-ink-300 rounded-md px-2 py-1.5 bg-white"
        value={accountId ?? accounts[0]?.id}
        onChange={(e) => setAccountId(Number(e.target.value))}
      >
        {accounts.map((a) => (
          <option key={a.id} value={a.id}>
            {a.google_email}
            {a.status !== "ACTIVE" ? ` (${a.status.toLowerCase()})` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
