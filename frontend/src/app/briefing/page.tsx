"use client";

import useSWR from "swr";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAccount } from "@/hooks/use-account";
import { briefingApi } from "@/lib/endpoints";
import { fmtDate } from "@/lib/format";

const KIND_LABEL: Record<string, string> = {
  URGENT_MAIL: "Urgent mail",
  MEETING: "Meeting",
  TASK: "Task",
  TRAVEL: "Travel",
  REMINDER: "Reminder",
};

export default function BriefingPage() {
  const { accountId } = useAccount();
  const { data, isLoading } = useSWR(
    accountId ? ["briefing", accountId] : null,
    () => briefingApi.today(accountId!)
  );

  return (
    <>
      <PageHeader
        title="Daily briefing"
        subtitle={
          data
            ? `Generated ${fmtDate(data.generated_at)}`
            : "AI-curated summary of everything that needs your attention today."
        }
      />

      {isLoading && <p className="text-sm text-ink-500">Generating your briefing…</p>}

      {data && (
        <Card>
          <p className="text-ink-800 text-base mb-4">{data.greeting}</p>

          {data.items.length === 0 && (
            <p className="text-sm text-ink-500">Nothing urgent on the plate today. Enjoy the calm.</p>
          )}

          <ol className="space-y-4">
            {data.items.map((item, idx) => (
              <li key={idx} className="border-l-2 border-brand-200 pl-4 py-1">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-ink-900">{item.title}</p>
                    <p className="text-sm text-ink-600 mt-0.5">{item.summary}</p>
                    {item.when && (
                      <p className="text-xs text-ink-500 mt-1">{fmtDate(item.when)}</p>
                    )}
                  </div>
                  <Badge tone={item.kind === "URGENT_MAIL" ? "urgent" : "muted"}>
                    {KIND_LABEL[item.kind] ?? item.kind}
                  </Badge>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      )}
    </>
  );
}
