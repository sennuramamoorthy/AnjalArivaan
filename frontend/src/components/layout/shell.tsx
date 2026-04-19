/**
 * Backwards-compat re-export. The canonical AppShell now lives in
 * `./app-shell.tsx` and includes a sidebar, account switcher, and
 * admin-gated links. Existing imports from `@/components/layout/shell`
 * continue to work.
 */
export { AppShell } from "@/components/layout/app-shell";
