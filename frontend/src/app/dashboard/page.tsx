"use client";

import useSWR from "swr";
import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/use-auth";
import { useAccount } from "@/hooks/use-account";
import { briefingApi, mailApi, tasksApi, meetingsApi } from "@/lib/endpoints";
import { fmtRelative } from "@/lib/format";

export default function DashboardPage() {
  const { user } = useAuth();
  const { accountId } = useAccount();

  const { data: briefing } = useSWR(
    accountId ? ["briefing", accountId] : null,
    () => briefingApi.today(accountId!)
  );
  const { data: urgentMail } = useSWR(
    accountId ? ["urgent-mail", accountId] : null,
    () => mailApi.list({ account_id: accountId!, is_urgent: true, size: 5 })
  );
  const { data: tasks } = useSWR(
    accountId ? ["my-tasks", accountId] : null,
    () => tasksApi.list({ account_id: accountId!, state: "ASSIGNED" })
  );
  const { data: meetings } = useSWR(
    accountId ? ["meetings-today", accountId] : null,
    () => meetingsApi.list({ account_id: accountId! })
  );

  return (
    <>
      <PageHeader
        title={`Vanakkam, ${user?.full_name?.split(" ")[0] || "there"} 👋`}
        subtitle="Here's your day at a glance."
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <Stat
          label="Urgent mail"
          value={urgentMail?.length ?? 0}
          href="/mail?urgent=1"
          tone="urgent"
        />
        <Stat label="Open tasks" value={tasks?.length ?? 0} href="/tasks" />
        <Stat label="Today's meetings" value={meetings?.length ?? 0} href="/calendar" />
        <Stat
          label="Briefing items"
          value={briefing?.items.length ?? 0}
          href="/briefing"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader
            title="Urgent mail"
            action={<Link href="/mail" className="text-sm text-brand-600 hover:underline">Open mail →</Link>}
          />
          {(urgentMail ?? []).length === 0 && (
            <p className="text-sm text-ink-500">No urgent mail right now.</p>
          )}
          <ul className="space-y-3">
            {(urgentMail ?? []).map((m) => (
              <li key={m.id} className="flex items-start justify-between gap-3">
                <Link
                  href={`/mail/thread/${m.thread_id}`}
                  className="min-w-0 flex-1 hover:text-brand-700"
                >
                  <p className="font-medium truncate">{m.subject || "(no subject)"}</p>
                  <p className="text-xs text-ink-500 truncate">
                    {m.from_address} · {fmtRelative(m.received_at)}
                  </p>
                </Link>
                <Badge tone="urgent">{Math.round(m.urgency_score * 100)}%</Badge>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <CardHeader
            title="Tasks assigned to you"
            action={<Link href="/tasks" className="text-sm text-brand-600 hover:underline">All tasks →</Link>}
          />
          {(tasks ?? []).length === 0 && (
            <p className="text-sm text-ink-500">No open tasks — nice!</p>
          )}
          <ul className="space-y-3">
            {(tasks ?? []).map((t) => (
              <li key={t.id} className="flex items-center justify-between">
                <span className="truncate">{t.title}</span>
                <Badge>{t.state}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}

function Stat({
  label,
  value,
  href,
  tone,
}: {
  label: string;
  value: number;
  href: string;
  tone?: "urgent";
}) {
  return (
    <Link href={href} className="card p-5 block hover:border-brand-300 transition">
      <p className="text-sm text-ink-500">{label}</p>
      <p
        className={
          tone === "urgent"
            ? "mt-1 text-3xl font-bold text-brand-600"
            : "mt-1 text-3xl font-bold text-ink-900"
        }
      >
        {value}
      </p>
    </Link>
  );
}
