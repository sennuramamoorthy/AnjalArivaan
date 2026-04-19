"use client";

import { useState } from "react";
import useSWR from "swr";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useAccount } from "@/hooks/use-account";
import { travelApi } from "@/lib/endpoints";
import { fmtDate } from "@/lib/format";
import { useAuth } from "@/hooks/use-auth";

export default function TravelPage() {
  const { accountId } = useAccount();
  const { user } = useAuth();
  const [showCreate, setShowCreate] = useState(false);
  const { data, mutate } = useSWR(
    accountId ? ["travel", accountId] : null,
    () => travelApi.list({ account_id: accountId! })
  );

  async function act(id: number, action: "submit" | "approve" | "reject") {
    if (action === "submit") await travelApi.submit(id);
    else if (action === "approve") await travelApi.approve(id);
    else {
      const reason = prompt("Reason for rejection?");
      if (!reason) return;
      await travelApi.reject(id, reason);
    }
    mutate();
  }

  return (
    <>
      <PageHeader
        title="Travel"
        subtitle="Plan trips with the right approval chain (Dean → Registrar → VC)."
        action={
          <Button onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "Close" : "New travel plan"}
          </Button>
        }
      />

      {showCreate && (
        <TravelForm
          accountId={accountId}
          onCreated={() => {
            setShowCreate(false);
            mutate();
          }}
        />
      )}

      <div className="space-y-3">
        {(data ?? []).map((t) => (
          <Card key={t.id}>
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-ink-900">{t.destination}</p>
                <p className="text-sm text-ink-600">{t.purpose}</p>
                <p className="text-xs text-ink-500 mt-1">
                  {fmtDate(t.depart_at)} → {fmtDate(t.return_at)} · {t.mode}
                </p>
                <p className="text-xs text-ink-500">Traveler: {t.traveler_email}</p>
                {t.approver_email && (
                  <p className="text-xs text-ink-500">Approver: {t.approver_email}</p>
                )}
              </div>
              <div className="flex flex-col gap-2 items-end">
                <Badge>{t.status}</Badge>
                <div className="flex gap-1">
                  {t.status === "DRAFT" && t.traveler_email === user?.email && (
                    <Button variant="secondary" onClick={() => act(t.id, "submit")}>
                      Submit
                    </Button>
                  )}
                  {t.status === "PENDING_APPROVAL" && t.approver_email === user?.email && (
                    <>
                      <Button onClick={() => act(t.id, "approve")}>Approve</Button>
                      <Button variant="secondary" onClick={() => act(t.id, "reject")}>
                        Reject
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}

function TravelForm({
  accountId,
  onCreated,
}: {
  accountId: number | null;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    destination: "",
    purpose: "",
    depart_at: "",
    return_at: "",
    mode: "FLIGHT",
  });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!accountId) return;
    setErr(null);
    setBusy(true);
    try {
      await travelApi.create({
        account_id: accountId,
        destination: form.destination,
        purpose: form.purpose,
        depart_at: new Date(form.depart_at).toISOString(),
        return_at: new Date(form.return_at).toISOString(),
        mode: form.mode,
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
      <CardHeader title="New travel plan" />
      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Input
          label="Destination"
          required
          value={form.destination}
          onChange={(e) => setForm({ ...form, destination: e.target.value })}
        />
        <Input
          label="Purpose"
          required
          value={form.purpose}
          onChange={(e) => setForm({ ...form, purpose: e.target.value })}
        />
        <Input
          label="Depart"
          type="datetime-local"
          required
          value={form.depart_at}
          onChange={(e) => setForm({ ...form, depart_at: e.target.value })}
        />
        <Input
          label="Return"
          type="datetime-local"
          required
          value={form.return_at}
          onChange={(e) => setForm({ ...form, return_at: e.target.value })}
        />
        <div>
          <label className="label">Mode</label>
          <select
            className="input"
            value={form.mode}
            onChange={(e) => setForm({ ...form, mode: e.target.value })}
          >
            <option>FLIGHT</option>
            <option>TRAIN</option>
            <option>ROAD</option>
          </select>
        </div>
        {err && <p className="text-sm text-brand-700 md:col-span-2">{err}</p>}
        <div className="md:col-span-2">
          <Button type="submit" loading={busy}>
            Save as draft
          </Button>
        </div>
      </form>
    </Card>
  );
}
