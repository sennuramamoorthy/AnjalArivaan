'use client';

import * as React from 'react';
import { UserCheck, UserX, ShieldCheck, Mail, Loader2, UserPlus, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Avatar } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useAdminUsers,
  useSuspendUser,
  useActivateUser,
  useCreateUser,
} from '@/lib/hooks/use-admin';
import type { UserRole, UserStatus } from '@/lib/api/admin';

const CREATE_ROLES: UserRole[] = [
  'SUPER_ADMIN',
  'DEPT_ADMIN',
  'VC',
  'REGISTRAR',
  'DEAN',
  'HOD',
  'STAFF',
];

const ROLE_FILTERS: (UserRole | 'ALL')[] = [
  'ALL',
  'SUPER_ADMIN',
  'DEPT_ADMIN',
  'VC',
  'REGISTRAR',
  'DEAN',
  'HOD',
  'STAFF',
];
const STATUS_FILTERS: (UserStatus | 'ALL')[] = [
  'ALL',
  'ACTIVE',
  'SUSPENDED',
  'PENDING_VERIFICATION',
];

const STATUS_STYLES: Record<UserStatus, string> = {
  ACTIVE: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  SUSPENDED: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  PENDING: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  PENDING_VERIFICATION: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
};

export default function AdminUsersPage() {
  const [roleFilter, setRoleFilter] = React.useState<UserRole | 'ALL'>('ALL');
  const [statusFilter, setStatusFilter] = React.useState<UserStatus | 'ALL'>('ALL');
  const [page, setPage] = React.useState(1);
  const [inviteOpen, setInviteOpen] = React.useState(false);

  const { data, isLoading, isError } = useAdminUsers({
    role: roleFilter === 'ALL' ? undefined : roleFilter,
    status: statusFilter === 'ALL' ? undefined : statusFilter,
    page,
  });

  const { mutate: suspend, isPending: isSuspending, variables: suspendingId } = useSuspendUser();
  const { mutate: activate, isPending: isActivating, variables: activatingId } = useActivateUser();

  const users = data?.users ?? [];

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <FilterSelect
          label="Role"
          value={roleFilter}
          onChange={(v) => {
            setRoleFilter(v as UserRole | 'ALL');
            setPage(1);
          }}
          options={ROLE_FILTERS}
        />
        <FilterSelect
          label="Status"
          value={statusFilter}
          onChange={(v) => {
            setStatusFilter(v as UserStatus | 'ALL');
            setPage(1);
          }}
          options={STATUS_FILTERS}
        />
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {data ? `${data.total} total` : ''}
          </span>
          <Button size="sm" onClick={() => setInviteOpen(true)}>
            <UserPlus size={14} />
            Onboard user
          </Button>
        </div>
      </div>

      {inviteOpen && <InviteUserModal onClose={() => setInviteOpen(false)} />}

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-sm text-red-500">Failed to load users.</div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-500">No users match these filters.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:bg-gray-800/60 dark:text-gray-400">
              <tr>
                <th className="px-4 py-2.5">User</th>
                <th className="px-4 py-2.5">Role</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">MFA</th>
                <th className="px-4 py-2.5">Joined</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {users.map((u) => {
                const isActive = u.status === 'ACTIVE';
                const busy =
                  (isSuspending && suspendingId === u.id) ||
                  (isActivating && activatingId === u.id);
                return (
                  <tr key={u.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/40">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <Avatar name={u.name || u.email} size="sm" />
                        <div className="min-w-0">
                          <p className="truncate font-medium text-gray-900 dark:text-gray-100">
                            {u.name || '—'}
                          </p>
                          <p className="flex items-center gap-1 truncate text-xs text-gray-500 dark:text-gray-400">
                            <Mail size={10} />
                            {u.email}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="default" className="text-[10px]">
                        {u.role === 'SUPER_ADMIN' && <ShieldCheck size={10} className="mr-1" />}
                        {u.role.replace('_', ' ')}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          'rounded-full px-2 py-0.5 text-[10px] font-semibold',
                          STATUS_STYLES[u.status]
                        )}
                      >
                        {u.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600 dark:text-gray-400">
                      {u.mfaEnabled ? 'Enabled' : 'Disabled'}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                      {u.createdAt ? new Date(u.createdAt).toLocaleDateString('en-IN') : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {isActive ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => suspend(u.id)}
                          disabled={busy}
                          className="text-red-600 hover:text-red-700"
                        >
                          {busy ? <Loader2 size={12} className="animate-spin" /> : <UserX size={12} />}
                          Suspend
                        </Button>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => activate(u.id)}
                          disabled={busy}
                          className="text-emerald-600 hover:text-emerald-700"
                        >
                          {busy ? <Loader2 size={12} className="animate-spin" /> : <UserCheck size={12} />}
                          Activate
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {data && data.total > data.pageSize && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500 dark:text-gray-400">
            Page {data.page} of {Math.ceil(data.total / data.pageSize)}
          </span>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              disabled={data.page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={!data.hasMore}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: readonly string[];
}) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          'rounded-md border px-2 py-1 text-xs font-medium',
          'border-gray-200 bg-white text-gray-700',
          'dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500'
        )}
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt === 'ALL' ? 'All' : opt.replace('_', ' ')}
          </option>
        ))}
      </select>
    </label>
  );
}

function InviteUserModal({ onClose }: { onClose: () => void }) {
  const { mutate, isPending, error } = useCreateUser();
  const [email, setEmail] = React.useState('');
  const [name, setName] = React.useState('');
  const [role, setRole] = React.useState<UserRole>('STAFF');
  const [password, setPassword] = React.useState('');

  function submit(e: React.FormEvent) {
    e.preventDefault();
    mutate(
      { email: email.trim(), name: name.trim(), role, password },
      { onSuccess: () => onClose() }
    );
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/30"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-xl border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-800 dark:bg-gray-900"
      >
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Onboard new user
            </h3>
            <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
              The user can log in immediately with the password you set. Share it
              securely and prompt a reset on first login.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <div className="mt-4 space-y-3">
          <Field label="Email">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@takshashilauniv.ac.in"
              className={fieldClass}
            />
          </Field>
          <Field label="Full name">
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jane Doe"
              className={fieldClass}
            />
          </Field>
          <Field label="Role">
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className={fieldClass}
            >
              {CREATE_ROLES.map((r) => (
                <option key={r} value={r}>
                  {r.replace('_', ' ')}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Initial password">
            <input
              type="text"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Minimum 8 characters"
              className={fieldClass}
            />
          </Field>
        </div>

        {error && (
          <p className="mt-3 text-xs text-red-600 dark:text-red-400">
            {(error as Error).message}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button type="submit" size="sm" disabled={isPending}>
            {isPending ? <Loader2 size={12} className="animate-spin" /> : <UserPlus size={12} />}
            Create user
          </Button>
        </div>
      </form>
    </div>
  );
}

const fieldClass = cn(
  'w-full rounded-md border px-2.5 py-1.5 text-sm',
  'border-gray-200 bg-white text-gray-800 placeholder:text-gray-400',
  'dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100',
  'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500'
);

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">
        {label}
      </span>
      {children}
    </label>
  );
}
