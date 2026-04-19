"use client";

import useSWR from "swr";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/use-auth";
import { request } from "@/lib/api";
import { fmtDate } from "@/lib/format";

interface AuditEvent {
  id: number;
  actor_user_id: number;
  action: string;
  target_type: string | null;
  target_id: string | null;
  occurred_at: string;
}

export default function AdminPage() {
  const { user } = useAuth();
  const isAdmin = user?.is_super_admin;

  const { data: events } = useSWR<AuditEvent[]>(
    isAdmin ? "/api/v1/audit/events?limit=100" : null,
    (url: string) => request<AuditEvent[]>(url)
  );

  if (!user) return null;
  if (!isAdmin) {
    return (
      <Card>
        <p className="text-sm text-ink-700">
          This page is only available to super administrators.
        </p>
      </Card>
    );
  }

  return (
    <>
      <PageHeader
        title="Admin"
        subtitle="Audit log, consent ledger and organization-wide configuration."
      />

      <Card>
        <CardHeader
          title="Audit events"
          subtitle="Append-only log — required for DPDP Act 2023 and UGC/AICTE compliance."
        />
        {!events && <p className="text-sm text-ink-500">Loading…</p>}
        <ul className="divide-y divide-ink-100">
          {(events ?? []).map((e) => (
            <li key={e.id} className="py-2 flex items-center justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ink-900">{e.action}</p>
                <p className="text-xs text-ink-500">
                  actor=user:{e.actor_user_id}
                  {e.target_type && ` · ${e.target_type}:${e.target_id}`}
                </p>
              </div>
              <div className="text-right">
                <Badge>{fmtDate(e.occurred_at)}</Badge>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
