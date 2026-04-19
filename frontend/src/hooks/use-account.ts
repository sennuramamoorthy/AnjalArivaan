"use client";

import { useEffect, useState } from "react";

const KEY = "aa.activeAccountId";

/**
 * Tracks which LinkedAccount the UI is currently scoped to.
 * Simple hook — no context provider needed because account ID is user-sticky.
 */
export function useAccount() {
  const [accountId, setAccountIdState] = useState<number | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const v = window.localStorage.getItem(KEY);
    if (v) setAccountIdState(Number(v));
  }, []);

  function setAccountId(id: number) {
    setAccountIdState(id);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(KEY, String(id));
    }
  }

  return { accountId, setAccountId };
}
