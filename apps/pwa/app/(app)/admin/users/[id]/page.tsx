'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  UserCheck,
  UserX,
  ShieldCheck,
  Mail,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Avatar } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useAdminUsers,
  useActivateUser,
  useSuspendUser,
} from '@/lib/hooks/use-admin';
import type { UserStatus } from '@/lib/api/admin';

const STATUS_STYLES: Record<UserStatus, string> = {
  ACTIVE: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  SUSPENDED: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  PENDING: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  PENDING_VERIFICATION:
    'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
};

/**
 * /admin/users/[id] — user detail + status editor.
 *
 * The backend has no single-user GET endpoint in Phase 1a, so we look up
 * the user from the cached list response. Role editing isn't exposed by
 * the admin API yet (only ACTIVE/SUSPENDED toggles), so this page is a
 * read-only profile plus the two status mutations.
 */
export default function AdminUserDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const userId = params?.id;

  // We page through the list until we find the user — in Phase 1a pilot
  // scope (~20 users) this is one request. If the pilot grows, swap this
  // for a dedicated GET /admin/users/{id} call.
  const { data, isLoading, isError } = useAdminUsers({ pageSize: 200 });
  const user = data?.users.find((u) => u.id === userId);

  const { mutate: suspend, isPending: isSuspending } = useSuspendUser();
  const { mutate: activate, isPending: isActivating } = useActivateUser();

  const busy = isSuspending || isActivating;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft size={14} />
          Back
        </Button>
        <Link
          href="/admin/users"
          className="text-xs text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
        >
          All users
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-48 w-full rounded-xl" />
        </div>
      ) : isError ? (
        <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-300">
          <AlertTriangle size={16} />
          Failed to load user.
        </div>
      ) : !user ? (
        <div className="rounded-xl border border-gray-200 bg-white p-8 text-center text-sm text-gray-500 dark:border-gray-800 dark:bg-gray-900">
          User not found.
        </div>
      ) : (
        <>
          {/* Identity card */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex items-start gap-4">
              <Avatar name={user.name || user.email} size="lg" />
              <div className="min-w-0 flex-1">
                <h2 className="truncate text-lg font-semibold text-gray-900 dark:text-gray-100">
                  {user.name || '—'}
                </h2>
                <p className="mt-0.5 flex items-center gap-1 truncate text-sm text-gray-500 dark:text-gray-400">
                  <Mail size={12} />
                  {user.email}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Badge variant="default" className="text-[10px]">
                    {user.role === 'SUPER_ADMIN' && (
                      <ShieldCheck size={10} className="mr-1" />
                    )}
                    {user.role.replace('_', ' ')}
                  </Badge>
                  <span
                    className={cn(
                      'rounded-full px-2 py-0.5 text-[10px] font-semibold',
                      STATUS_STYLES[user.status]
                    )}
                  >
                    {user.status}
                  </span>
                  <span className="text-[10px] text-gray-500 dark:text-gray-400">
                    MFA {user.mfaEnabled ? 'enabled' : 'disabled'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Status editor */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Account status
            </h3>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Suspended users cannot log in or sync mail. Changes are recorded in
              the audit log.
            </p>
            <div className="mt-3 flex gap-2">
              {user.status === 'ACTIVE' ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => suspend(user.id)}
                  disabled={busy}
                  className="text-red-600 hover:text-red-700"
                >
                  {busy ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : (
                    <UserX size={12} />
                  )}
                  Suspend user
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => activate(user.id)}
                  disabled={busy}
                  className="text-emerald-600 hover:text-emerald-700"
                >
                  {busy ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : (
                    <UserCheck size={12} />
                  )}
                  Activate user
                </Button>
              )}
            </div>
          </div>

          {/* Metadata */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Details
            </h3>
            <dl className="mt-3 space-y-2 text-xs">
              <Row k="User ID" v={<code className="font-mono">{user.id}</code>} />
              <Row k="Role" v={user.role.replace('_', ' ')} />
              <Row k="Status" v={user.status} />
              <Row k="MFA" v={user.mfaEnabled ? 'Enabled' : 'Disabled'} />
              <Row
                k="Joined"
                v={
                  user.createdAt
                    ? new Date(user.createdAt).toLocaleString('en-IN')
                    : '—'
                }
              />
            </dl>
            <p className="mt-4 text-[11px] text-gray-500 dark:text-gray-400">
              Role changes are not yet exposed through the admin API — to change
              a user&apos;s role, update it directly in identity service.
            </p>
          </div>
        </>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <dt className="w-24 shrink-0 text-gray-500 dark:text-gray-400">{k}</dt>
      <dd className="min-w-0 flex-1 break-words text-gray-800 dark:text-gray-200">
        {v}
      </dd>
    </div>
  );
}
