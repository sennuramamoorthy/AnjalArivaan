"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { login } from "@/lib/auth";
import { HttpError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [showTotp, setShowTotp] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login({ email, password, totp: totp || null });
      router.replace("/dashboard");
    } catch (e) {
      if (e instanceof HttpError) {
        if (e.code === "MFA_REQUIRED") {
          setShowTotp(true);
          setErr("Enter your 6-digit authenticator code.");
        } else {
          setErr(e.detail);
        }
      } else {
        setErr("Login failed. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h1 className="text-xl font-semibold text-ink-900 mb-1">Sign in</h1>
      <p className="text-sm text-ink-500 mb-6">Use your Takshashila account.</p>

      <form onSubmit={onSubmit} className="space-y-4">
        <Input
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@takshashilauniv.ac.in"
        />
        <Input
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {showTotp && (
          <Input
            id="totp"
            label="Authenticator code"
            inputMode="numeric"
            pattern="[0-9]{6}"
            maxLength={6}
            value={totp}
            onChange={(e) => setTotp(e.target.value)}
            placeholder="123456"
            required
          />
        )}

        {err && <p className="text-sm text-brand-700">{err}</p>}

        <Button type="submit" className="w-full" loading={busy}>
          Sign in
        </Button>
      </form>

      <p className="text-xs text-ink-500 mt-6 text-center">
        New here?{" "}
        <Link href="/signup" className="text-brand-600 hover:underline">
          Create an account
        </Link>
      </p>
    </Card>
  );
}
