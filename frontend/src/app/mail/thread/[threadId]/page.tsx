"use client";

import { useState } from "react";
import useSWR from "swr";
import { useParams } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAccount } from "@/hooks/use-account";
import { mailApi } from "@/lib/endpoints";
import { fmtDate } from "@/lib/format";

export default function ThreadPage() {
  const { threadId } = useParams<{ threadId: string }>();
  const { accountId } = useAccount();

  const { data, isLoading } = useSWR(
    accountId && threadId ? ["thread", accountId, threadId] : null,
    () => mailApi.thread(threadId, accountId!)
  );

  const [summary, setSummary] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ subject: string; body: string } | null>(
    null
  );
  const [busyKey, setBusyKey] = useState<string | null>(null);

  async function summarize() {
    if (!accountId) return;
    setBusyKey("summarize");
    try {
      const r = await mailApi.summarizeThread({
        account_id: accountId,
        thread_id: threadId,
      });
      setSummary(r.summary);
    } finally {
      setBusyKey(null);
    }
  }

  async function draftReply(tone: "formal" | "friendly" | "concise") {
    if (!accountId) return;
    setBusyKey("draft");
    try {
      const r = await mailApi.draftReply({
        account_id: accountId,
        thread_id: threadId,
        tone,
      });
      setDraft({ subject: r.draft_subject, body: r.draft_body_html });
    } finally {
      setBusyKey(null);
    }
  }

  if (isLoading || !data) {
    return <p className="text-sm text-ink-500">Loading thread…</p>;
  }

  return (
    <>
      <PageHeader title={data.subject || "(no subject)"} subtitle={`${data.message_count} messages`} />

      <Card className="mb-4">
        <CardHeader
          title="AI assistance"
          subtitle="Summarize or draft a reply — runs on the on-prem LLM."
          action={
            <div className="flex gap-2">
              <Button variant="secondary" loading={busyKey === "summarize"} onClick={summarize}>
                Summarize
              </Button>
              <Button loading={busyKey === "draft"} onClick={() => draftReply("formal")}>
                Draft reply
              </Button>
            </div>
          }
        />
        {summary && (
          <div className="mt-2 p-3 bg-ink-50 rounded-lg text-sm text-ink-800 whitespace-pre-wrap">
            {summary}
          </div>
        )}
        {draft && (
          <div className="mt-4">
            <p className="label">Subject</p>
            <input className="input mb-3" value={draft.subject} readOnly />
            <p className="label">Body</p>
            <textarea
              className="input min-h-[180px] font-mono text-xs"
              value={draft.body}
              readOnly
            />
            <p className="text-xs text-ink-500 mt-2">
              Draft is created in Gmail as a draft — you can review before sending.
            </p>
          </div>
        )}
      </Card>

      <div className="space-y-3">
        {data.messages.map((m) => (
          <Card key={m.id}>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-ink-900">{m.from_address}</p>
              <p className="text-xs text-ink-500">{fmtDate(m.received_at)}</p>
            </div>
            <p className="text-sm text-ink-600 mb-1">
              To: {m.to_addresses.join(", ")}
            </p>
            <p className="text-ink-800 whitespace-pre-wrap">{m.preview}</p>
          </Card>
        ))}
      </div>
    </>
  );
}
