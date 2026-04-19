"use client";

import { useState } from "react";
import useSWR from "swr";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAccount } from "@/hooks/use-account";
import { contactsApi } from "@/lib/endpoints";

export default function ContactsPage() {
  const { accountId } = useAccount();
  const [q, setQ] = useState("");
  const [showForm, setShowForm] = useState(false);
  const { data, mutate } = useSWR(
    accountId ? ["contacts", accountId] : null,
    () => contactsApi.list(accountId!)
  );

  const filtered = (data ?? []).filter(
    (c) =>
      !q ||
      c.display_name.toLowerCase().includes(q.toLowerCase()) ||
      c.email.toLowerCase().includes(q.toLowerCase()) ||
      (c.organization || "").toLowerCase().includes(q.toLowerCase())
  );

  return (
    <>
      <PageHeader
        title="Contacts"
        subtitle="University people & vendors — synced with Google Contacts."
        action={
          <Button onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Close" : "Add contact"}
          </Button>
        }
      />

      {showForm && (
        <AddContactForm
          accountId={accountId}
          onCreated={() => {
            setShowForm(false);
            mutate();
          }}
        />
      )}

      <Input
        placeholder="Search by name, email, organization…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        className="mb-4"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {filtered.map((c) => (
          <Card key={c.id}>
            <p className="font-medium text-ink-900">{c.display_name}</p>
            <p className="text-sm text-ink-600">{c.email}</p>
            {c.phone_e164 && <p className="text-sm text-ink-600">{c.phone_e164}</p>}
            {c.title && c.organization && (
              <p className="text-xs text-ink-500 mt-1">
                {c.title} · {c.organization}
              </p>
            )}
            {c.relationship && (
              <p className="text-xs text-brand-600 mt-1">#{c.relationship}</p>
            )}
          </Card>
        ))}
      </div>
      {filtered.length === 0 && (
        <Card>
          <p className="text-sm text-ink-500">No contacts match.</p>
        </Card>
      )}
    </>
  );
}

function AddContactForm({
  accountId,
  onCreated,
}: {
  accountId: number | null;
  onCreated: () => void;
}) {
  const [f, setF] = useState({
    display_name: "",
    email: "",
    phone_e164: "",
    title: "",
    organization: "",
    relationship: "",
    note: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!accountId) return;
    setBusy(true);
    setErr(null);
    try {
      await contactsApi.create(accountId, {
        display_name: f.display_name,
        email: f.email,
        phone_e164: f.phone_e164 || null,
        title: f.title || null,
        organization: f.organization || null,
        relationship: f.relationship || null,
        note: f.note || null,
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
      <CardHeader title="Add contact" />
      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Input
          label="Display name"
          required
          value={f.display_name}
          onChange={(e) => setF({ ...f, display_name: e.target.value })}
        />
        <Input
          label="Email"
          type="email"
          required
          value={f.email}
          onChange={(e) => setF({ ...f, email: e.target.value })}
        />
        <Input
          label="Phone (E.164)"
          placeholder="+919812345678"
          value={f.phone_e164}
          onChange={(e) => setF({ ...f, phone_e164: e.target.value })}
        />
        <Input
          label="Title"
          value={f.title}
          onChange={(e) => setF({ ...f, title: e.target.value })}
        />
        <Input
          label="Organization"
          value={f.organization}
          onChange={(e) => setF({ ...f, organization: e.target.value })}
        />
        <Input
          label="Relationship (tag)"
          value={f.relationship}
          onChange={(e) => setF({ ...f, relationship: e.target.value })}
        />
        {err && <p className="text-sm text-brand-700 md:col-span-2">{err}</p>}
        <div className="md:col-span-2">
          <Button type="submit" loading={busy}>
            Save
          </Button>
        </div>
      </form>
    </Card>
  );
}
