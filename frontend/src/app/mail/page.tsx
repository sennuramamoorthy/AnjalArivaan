"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAccount } from "@/hooks/use-account";
import { mailApi } from "@/lib/endpoints";
import { fmtRelative } from "@/lib/format";

export default function MailInboxPage() {
  const { accountId } = useAccount();
  const [urgentOnly, setUrgentOnly] = useState(false);

  const { data: items, isLoading } = useSWR(
    accountId ? ["mail", accountId, urgentOnly] : null,
    () =>
      mailApi.list({
        account_id: accountId!,
        is_urgent: urgentOnly || undefined,
        size: 50,
      })
  );

  return (
    <>
      <PageHeader
        title="Mail"
        subtitle="Inbox with urgency-aware triage."
        action={
          <div className="flex gap-2">
            <Button
              variant={urgentOnly ? "primary" : "secondary"}
              onClick={() => setUrgentOnly((v) => !v)}
            >
              {urgentOnly ? "Showing urgent" : "All mail"}
            </Button>
          </div>
        }
      />

      {isLoading && <p className="text-sm text-ink-500">Loading…</p>}

      {!accountId && (
        <Card>
          <p className="text-sm text-ink-500">Link a Google account to see mail.</p>
        </Card>
      )}

      {items && items.length === 0 && (
        <Card>
          <p className="text-sm text-ink-500">Inbox zero. Nicely done.</p>
        </Card>
      )}

      <div className="space-y-2">
        {(items ?? []).map((m) => (
          <Link
            key={m.id}
            href={`/mail/thread/${m.thread_id}`}
            className="card p-4 block hover:border-brand-300 transition"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  {m.is_urgent && <Badge tone="urgent">Urgent</Badge>}
                  <p className="text-sm text-ink-500 truncate">{m.from_address}</p>
                </div>
                <p className="font-medium text-ink-900 truncate">
                  {m.subject || "(no subject)"}
                </p>
                <p className="text-sm text-ink-600 mt-0.5 line-clamp-1">{m.preview}</p>
              </div>
              <div className="text-xs text-ink-500 whitespace-nowrap">
                {fmtRelative(m.received_at)}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}
