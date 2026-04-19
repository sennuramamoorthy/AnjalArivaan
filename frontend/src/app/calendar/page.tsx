"use client";

import { useState } from "react";
import useSWR from "swr";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useAccount } from "@/hooks/use-account";
import { meetingsApi, resourcesApi } from "@/lib/endpoints";
import { fmtDate } from "@/lib/format";

export default function CalendarPage() {
  const { accountId } = useAccount();
  const { data: meetings, mutate } = useSWR(
    accountId ? ["meetings", accountId] : null,
    () => meetingsApi.list({ account_id: accountId! })
  );
  const { data: resources } = useSWR("/api/v1/resources", resourcesApi.list);

  const [showCreate, setShowCreate] = useState(false);

  return (
    <>
      <PageHeader
        title="Calendar & resources"
        subtitle="Meetings, classrooms, labs, equipment, vehicles, and guesthouses."
        action={
          <Button onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "Close" : "New meeting"}
          </Button>
        }
      />

      {showCreate && (
        <MeetingForm
          accountId={accountId}
          resources={resources ?? []}
          onCreated={() => {
            setShowCreate(false);
            mutate();
          }}
        />
      )}

      {(meetings ?? []).length === 0 && (
        <Card>
          <p className="text-sm text-ink-500">No meetings scheduled.</p>
        </Card>
      )}

      <div className="space-y-3">
        {(meetings ?? []).map((m) => (
          <Card key={m.id}>
            <div className="flex items-start justify-between">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-ink-900">{m.title}</p>
                {m.description && (
                  <p className="text-sm text-ink-600 mt-1">{m.description}</p>
                )}
                <p className="text-xs text-ink-500 mt-2">
                  {fmtDate(m.start_at)} → {fmtDate(m.end_at)}
                </p>
                {m.location && (
                  <p className="text-xs text-ink-500">📍 {m.location}</p>
                )}
              </div>
              <Badge>{m.status}</Badge>
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}

function MeetingForm({
  accountId,
  resources,
  onCreated,
}: {
  accountId: number | null;
  resources: { id: number; name: string; type: string }[];
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    title: "",
    description: "",
    start_at: "",
    end_at: "",
    attendees: "",
    resource_ids: [] as number[],
  });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!accountId) return;
    setErr(null);
    setBusy(true);
    try {
      await meetingsApi.create({
        account_id: accountId,
        title: form.title,
        description: form.description || undefined,
        start_at: new Date(form.start_at).toISOString(),
        end_at: new Date(form.end_at).toISOString(),
        attendees: form.attendees.split(",").map((s) => s.trim()).filter(Boolean),
        resource_ids: form.resource_ids,
      });
      onCreated();
    } catch (e: unknown) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mb-6">
      <CardHeader title="Create meeting" />
      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Input
          label="Title"
          required
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
        />
        <Input
          label="Attendees (comma-separated emails)"
          value={form.attendees}
          onChange={(e) => setForm({ ...form, attendees: e.target.value })}
        />
        <Input
          label="Start"
          type="datetime-local"
          required
          value={form.start_at}
          onChange={(e) => setForm({ ...form, start_at: e.target.value })}
        />
        <Input
          label="End"
          type="datetime-local"
          required
          value={form.end_at}
          onChange={(e) => setForm({ ...form, end_at: e.target.value })}
        />
        <div className="md:col-span-2">
          <label className="label">Description</label>
          <textarea
            className="input"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </div>
        <div className="md:col-span-2">
          <label className="label">Resources</label>
          <div className="flex flex-wrap gap-2">
            {resources.map((r) => {
              const selected = form.resource_ids.includes(r.id);
              return (
                <button
                  type="button"
                  key={r.id}
                  onClick={() =>
                    setForm({
                      ...form,
                      resource_ids: selected
                        ? form.resource_ids.filter((x) => x !== r.id)
                        : [...form.resource_ids, r.id],
                    })
                  }
                  className={
                    selected
                      ? "px-3 py-1 rounded-full text-xs bg-brand-500 text-white"
                      : "px-3 py-1 rounded-full text-xs bg-ink-100 text-ink-700 hover:bg-ink-200"
                  }
                >
                  {r.name} · {r.type.toLowerCase()}
                </button>
              );
            })}
          </div>
        </div>
        {err && <p className="text-sm text-brand-700 md:col-span-2">{err}</p>}
        <div className="md:col-span-2">
          <Button type="submit" loading={busy}>
            Create
          </Button>
        </div>
      </form>
    </Card>
  );
}
