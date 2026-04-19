"use client";

import { useState } from "react";
import useSWR from "swr";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useAccount } from "@/hooks/use-account";
import { tasksApi } from "@/lib/endpoints";
import type { TaskState } from "@/types/api";
import { fmtRelative } from "@/lib/format";

const STATES: TaskState[] = [
  "ASSIGNED",
  "ACKNOWLEDGED",
  "IN_PROGRESS",
  "BLOCKED",
  "DONE",
  "CANCELLED",
];

// Explicit next-state map mirroring the backend state machine.
const NEXT: Record<TaskState, TaskState[]> = {
  ASSIGNED: ["ACKNOWLEDGED", "CANCELLED"],
  ACKNOWLEDGED: ["IN_PROGRESS", "BLOCKED", "CANCELLED"],
  IN_PROGRESS: ["DONE", "BLOCKED", "CANCELLED"],
  BLOCKED: ["IN_PROGRESS", "CANCELLED"],
  DONE: [],
  CANCELLED: [],
};

export default function TasksPage() {
  const { accountId } = useAccount();
  const [filter, setFilter] = useState<TaskState | "ALL">("ALL");
  const [showCreate, setShowCreate] = useState(false);

  const { data, mutate } = useSWR(
    accountId ? ["tasks", accountId, filter] : null,
    () =>
      tasksApi.list({
        account_id: accountId!,
        state: filter === "ALL" ? undefined : filter,
      })
  );

  return (
    <>
      <PageHeader
        title="Tasks"
        subtitle="Coordinated via Gmail ↔ WhatsApp. State machine enforced server-side."
        action={
          <Button onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "Close" : "New task"}
          </Button>
        }
      />

      {showCreate && (
        <CreateTaskForm
          accountId={accountId}
          onCreated={() => {
            setShowCreate(false);
            mutate();
          }}
        />
      )}

      <div className="flex flex-wrap gap-2 mb-4">
        <FilterChip
          label="All"
          active={filter === "ALL"}
          onClick={() => setFilter("ALL")}
        />
        {STATES.map((s) => (
          <FilterChip
            key={s}
            label={s}
            active={filter === s}
            onClick={() => setFilter(s)}
          />
        ))}
      </div>

      <div className="space-y-3">
        {(data ?? []).map((t) => (
          <Card key={t.id}>
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-ink-900">{t.title}</p>
                {t.description && (
                  <p className="text-sm text-ink-600 mt-1">{t.description}</p>
                )}
                <p className="text-xs text-ink-500 mt-2">
                  Assigned to <b>{t.assignee_email}</b>
                  {t.due_at && <> · due {fmtRelative(t.due_at)}</>}
                </p>
              </div>
              <div className="flex flex-col gap-2 items-end">
                <Badge>{t.state}</Badge>
                <div className="flex gap-1 flex-wrap justify-end">
                  {NEXT[t.state].map((next) => (
                    <button
                      key={next}
                      onClick={async () => {
                        await tasksApi.transition(t.id, next);
                        mutate();
                      }}
                      className="px-2 py-1 text-xs rounded bg-ink-100 text-ink-700 hover:bg-brand-100 hover:text-brand-700"
                    >
                      → {next}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={
        active
          ? "px-3 py-1 rounded-full text-xs bg-brand-500 text-white"
          : "px-3 py-1 rounded-full text-xs bg-ink-100 text-ink-700 hover:bg-ink-200"
      }
    >
      {label}
    </button>
  );
}

function CreateTaskForm({
  accountId,
  onCreated,
}: {
  accountId: number | null;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    title: "",
    description: "",
    assignee_email: "",
    due_at: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!accountId) return;
    setErr(null);
    setBusy(true);
    try {
      await tasksApi.create({
        account_id: accountId,
        title: form.title,
        description: form.description || undefined,
        assignee_email: form.assignee_email,
        due_at: form.due_at ? new Date(form.due_at).toISOString() : undefined,
      });
      onCreated();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mb-6">
      <CardHeader title="Create task" />
      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Input
          label="Title"
          required
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
        />
        <Input
          label="Assignee email"
          type="email"
          required
          value={form.assignee_email}
          onChange={(e) => setForm({ ...form, assignee_email: e.target.value })}
        />
        <Input
          label="Due"
          type="datetime-local"
          value={form.due_at}
          onChange={(e) => setForm({ ...form, due_at: e.target.value })}
        />
        <div className="md:col-span-2">
          <label className="label">Description</label>
          <textarea
            className="input"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
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
