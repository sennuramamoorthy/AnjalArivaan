"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { signup, login } from "@/lib/auth";
import { HttpError } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    designation: "",
  });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function set<K extends keyof typeof form>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await signup({
        email: form.email,
        password: form.password,
        full_name: form.full_name,
        designation: form.designation || undefined,
      });
      await login({ email: form.email, password: form.password });
      router.replace("/dashboard");
    } catch (e) {
      setErr(e instanceof HttpError ? e.detail : "Signup failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h1 className="text-xl font-semibold text-ink-900 mb-1">Create your account</h1>
      <p className="text-sm text-ink-500 mb-6">
        Use your official Takshashila email — the workspace domain is whitelisted.
      </p>
      <form onSubmit={onSubmit} className="space-y-4">
        <Input
          id="name"
          label="Full name"
          required
          value={form.full_name}
          onChange={(e) => set("full_name", e.target.value)}
        />
        <Input
          id="email"
          label="Email"
          type="email"
          required
          value={form.email}
          onChange={(e) => set("email", e.target.value)}
        />
        <Input
          id="password"
          label="Password (min 12 characters)"
          type="password"
          minLength={12}
          required
          value={form.password}
          onChange={(e) => set("password", e.target.value)}
        />
        <Input
          id="designation"
          label="Designation (optional)"
          placeholder="Registrar, Dean, Professor…"
          value={form.designation}
          onChange={(e) => set("designation", e.target.value)}
        />

        {err && <p className="text-sm text-brand-700">{err}</p>}

        <Button type="submit" className="w-full" loading={busy}>
          Create account
        </Button>
      </form>

      <p className="text-xs text-ink-500 mt-6 text-center">
        Already have an account?{" "}
        <Link href="/login" className="text-brand-600 hover:underline">
          Sign in
        </Link>
      </p>
    </Card>
  );
}
