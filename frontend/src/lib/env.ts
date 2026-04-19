/**
 * Typed env accessor. Only NEXT_PUBLIC_* vars are readable in the browser.
 */
export const env = {
  API_BASE:
    process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1",
  IS_DEV: process.env.NODE_ENV !== "production",
} as const;
