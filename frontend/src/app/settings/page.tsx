"use client";

import { useState } from "react";
import useSWR from "swr";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/use-auth";
import { useAccount } from "@/hooks/use-account";
import { accountsApi, contactsApi } from "@/lib/endpoints";
import { startMfa, verifyMfa } from "@/lib/auth";
import { fmtDate } from "@/lib/format";

export default function SettingsPage() {
  const { user } = useAuth();
  const { accountId } = useAccount();
  const { data: accounts, mutate: mutateAccounts } = useSWR(
    "/api/v1/accounts",
    accountsApi.list
  );

  async function linkGoogle() {
    const r = await accountsApi.startOAuth();
    window.location.href = r.authorization_url;
  }

  // MFA setup
  const [mfa, setMfa] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [mfaMsg, setMfaMsg] = useState<string | null>(null);
  async function beginMfa() {
    const r = await startMfa();
    setMfa(r);
    setMfaMsg(null);
  }
  async function confirmMfa() {
    const r = await verifyMfa(code);
    setMfaMsg(r.verified ? "MFA enabled — you'll be asked for a code on next sign-in." : "Invalid code.");
  }

  // Out-of-office
  const [ooo, setOoo] = useState({
    enabled: true,
    subject: "Out of office",
    body: "Thank you for your message — I'm currently away from the university and will respond on my return.",
    start_at: "",
    end_at: "",
  });
  const [oooMsg, setOooMsg] = useState<string | null>(null);
  async function saveOoo() {
    if (!accountId) return;
    await contactsApi.setOoo(accountId, {
      enabled: ooo.enabled,
      subject: ooo.subject,
      body: ooo.body,
      start_at: ooo.start_at ? new Date(ooo.start_at).toISOString() : undefined,
      end_at: ooo.end_at ? new Date(ooo.end_at).toISOString() : undefined,
    });
    setOooMsg("Out-of-office saved.");
  }

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Profile, linked Google accounts, MFA, and delegated assistants."
      />

      <Card className="mb-6">
        <CardHeader title="Profile" />
        <dl className="grid grid-cols-2 gap-y-2 text-sm">
          <dt className="text-ink-500">Name</dt>
          <dd>{user?.full_name}</dd>
          <dt className="text-ink-500">Email</dt>
          <dd>{user?.email}</dd>
          <dt className="text-ink-500">Designation</dt>
          <dd>{user?.designation ?? "—"}</dd>
          <dt className="text-ink-500">Department</dt>
          <dd>{user?.department ?? "—"}</dd>
          <dt className="text-ink-500">Role</dt>
          <dd>
            {user?.is_super_admin
              ? "Super admin"
              : user?.is_dept_admin
              ? "Department admin"
              : "Member"}
          </dd>
        </dl>
      </Card>

      <Card className="mb-6">
        <CardHeader
          title="Linked Google accounts"
          action={<Button onClick={linkGoogle}>Link account</Button>}
        />
        {(accounts ?? []).length === 0 && (
          <p className="text-sm text-ink-500">
            No linked accounts yet — link one to start receiving mail, calendar and contacts.
          </p>
        )}
        <ul className="divide-y divide-ink-100">
          {(accounts ?? []).map((a) => (
            <li key={a.id} className="py-3 flex items-center justify-between gap-3">
              <div>
                <p className="font-medium text-ink-900">{a.google_email}</p>
                <p className="text-xs text-ink-500">
                  Linked {fmtDate(a.created_at)} · scopes: {a.scopes.length}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={a.status === "ACTIVE" ? "muted" : "urgent"}>
                  {a.status}
                </Badge>
                {a.status === "ACTIVE" && (
                  <Button
                    variant="secondary"
                    onClick={async () => {
                      if (confirm("Revoke this account?")) {
                        await accountsApi.revoke(a.id);
                        mutateAccounts();
                      }
                    }}
                  >
                    Revoke
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <Card className="mb-6">
        <CardHeader
          title="Two-factor authentication"
          subtitle="Required for administrators; recommended for everyone."
          action={
            mfa ? null : (
              <Button variant="secondary" onClick={beginMfa}>
                Set up
              </Button>
            )
          }
        />
        {mfa && (
          <div className="space-y-3">
            <p className="text-sm text-ink-600">
              Add this key to your authenticator app (Google Authenticator, 1Password, etc.):
            </p>
            <code className="block p-2 bg-ink-100 rounded font-mono text-sm">
              {mfa.secret}
            </code>
            <p className="text-xs text-ink-500 break-all">URI: {mfa.otpauth_uri}</p>
            <div className="flex gap-2 items-end">
              <Input
                label="6-digit code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                maxLength={6}
                inputMode="numeric"
                className="max-w-[160px]"
              />
              <Button onClick={confirmMfa}>Verify</Button>
            </div>
            {mfaMsg && <p className="text-sm text-brand-700">{mfaMsg}</p>}
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Out-of-office auto-reply" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Input
            label="Subject"
            value={ooo.subject}
            onChange={(e) => setOoo({ ...ooo, subject: e.target.value })}
          />
          <div>
            <label className="label">Enabled</label>
            <input
              type="checkbox"
              checked={ooo.enabled}
              onChange={(e) => setOoo({ ...ooo, enabled: e.target.checked })}
              className="h-5 w-5"
            />
          </div>
          <Input
            label="Start"
            type="datetime-local"
            value={ooo.start_at}
            onChange={(e) => setOoo({ ...ooo, start_at: e.target.value })}
          />
          <Input
            label="End"
            type="datetime-local"
            value={ooo.end_at}
            onChange={(e) => setOoo({ ...ooo, end_at: e.target.value })}
          />
          <div className="md:col-span-2">
            <label className="label">Body</label>
            <textarea
              className="input min-h-[100px]"
              value={ooo.body}
              onChange={(e) => setOoo({ ...ooo, body: e.target.value })}
            />
          </div>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <Button onClick={saveOoo}>Save</Button>
          {oooMsg && <p className="text-sm text-ink-600">{oooMsg}</p>}
        </div>
      </Card>
    </>
  );
}
