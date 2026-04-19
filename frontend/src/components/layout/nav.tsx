/**
 * Nav is an internal component of the old `shell.tsx`. Navigation now
 * lives inside `AppShell` (a left sidebar), so this file exists only
 * as a backwards-compat stub — the symbol still resolves, even though
 * no in-tree code imports it any more.
 *
 * Kept as a no-op to avoid breaking external imports that may predate
 * the sidebar redesign.
 */
import type { UserOut } from "@/types/api";

export function Nav(_props: { user: UserOut | undefined }): null {
  return null;
}
