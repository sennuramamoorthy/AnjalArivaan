'use client';

import * as React from 'react';
import { Database, Zap, Inbox, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useSystemHealth, useAdminUsers } from '@/lib/hooks/use-admin';

function StatusPill({ ok }: { ok: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold',
        ok
          ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
          : 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300'
      )}
    >
      {ok ? <CheckCircle2 size={11} /> : <AlertTriangle size={11} />}
      {ok ? 'Healthy' : 'Unavailable'}
    </span>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  trailing,
}: {
  icon: React.ElementType;
  label: string;
  value: React.ReactNode;
  trailing?: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
          <Icon size={13} />
          {label}
        </div>
        {trailing}
      </div>
      <p className="mt-2 text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</p>
    </div>
  );
}

export default function AdminOverviewPage() {
  const { data: health, isLoading, refetch, isFetching } = useSystemHealth();
  const { data: userPage } = useAdminUsers({ pageSize: 1 });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
          Platform health
        </h2>
        <Button variant="ghost" size="sm" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw size={14} className={cn(isFetching && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[96px] w-full rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            icon={Database}
            label="Database"
            value={health?.database === 'ok' ? 'Connected' : 'Offline'}
            trailing={<StatusPill ok={health?.database === 'ok'} />}
          />
          <StatCard
            icon={Zap}
            label="Redis"
            value={health?.redis === 'ok' ? 'Connected' : 'Offline'}
            trailing={<StatusPill ok={health?.redis === 'ok'} />}
          />
          <StatCard
            icon={Inbox}
            label="Outbox pending"
            value={health?.outboxPending ?? 0}
          />
          <StatCard
            icon={CheckCircle2}
            label="Registered users"
            value={userPage?.total ?? '—'}
          />
        </div>
      )}

      <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
          Pilot snapshot
        </h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Phase 1a targets ~20 users (VC, Registrar, 3 Deans and their offices). Use
          the <span className="font-medium text-gray-700 dark:text-gray-300">Users</span> tab
          to suspend or activate accounts, and the{' '}
          <span className="font-medium text-gray-700 dark:text-gray-300">Audit log</span> tab
          to review admin actions and AI-generated content.
        </p>
      </div>
    </div>
  );
}
