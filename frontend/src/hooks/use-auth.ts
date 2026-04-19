"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { me } from "@/lib/auth";
import { tokenStore } from "@/lib/api";
import type { UserOut } from "@/types/api";

/** Client-side auth state. Redirects to /login if not authenticated. */
export function useAuth(opts: { required?: boolean } = {}) {
  const required = opts.required ?? true;
  const router = useRouter();
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    setHasToken(tokenStore.getAccess() !== null);
  }, []);

  const { data: user, error, isLoading, mutate } = useSWR<UserOut>(
    hasToken ? "me" : null,
    me,
    { revalidateOnFocus: false }
  );

  useEffect(() => {
    if (!required) return;
    if (!hasToken) {
      router.replace("/login");
      return;
    }
    if (error) {
      tokenStore.clear();
      router.replace("/login");
    }
  }, [hasToken, error, required, router]);

  return { user, isLoading, error, refresh: mutate };
}
