'use client';

import * as React from 'react';
import { ScrollText, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuditLogs } from '@/lib/hooks/use-admin';
import type { AuditEvent } from '@/lib/api/admin';

/**
 * /admin/audit-logs — append-only audit trail. Every admin action and
 * AI-generated content lands here per the architecture's compliance rule.
 * Filters are free-text actor/action substrings; the backend does the
 * ILIKE match. Selecting a row opens a drawer with the before/after JSON.
 */
export default function AdminAuditLogsPage() {
  const [actor, setActor] = React.useState('');
  const [action, setAction] = React.useState('');
  const [page, setPage] = React.useState(1);
  const [selected, setSelected] = React.useState<AuditEvent | null>(null);

  // Debounce the text filters so we don't refetch on every keystroke.
  const [debouncedActor, setDebouncedActor] = React.useState('');
  const [debouncedAction, setDebouncedAction] = React.useState('');
  React.useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedActor(actor);
      setDebouncedAction(action);
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [actor, action]);

  const { data, isLoading, isError } = useAuditLogs({
    actor: debouncedActor || undefined,
    action: debouncedAction || undefined,
    page,
  });

  const events = data?.events ?? [];

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <TextFilter label="Actor" value={actor} onChange={setActor} placeholder="email or id" />
        <TextFilter label="Action" value={action} onChange={setAction} placeholder="e.g. user.suspend" />
        <div className="ml-auto text-xs text-gray-500 dark:text-gray-400">
          {data ? `${data.total} events` : ''}
        </div>
      </div>

      {/* List */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-sm text-red-500">Failed to load audit log.</div>
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center gap-2 p-12 text-center text-sm text-gray-500">
            <ScrollText size={24} className="opacity-50" />
            No audit events match these filters.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:bg-gray-800/60 dark:text-gray-400">
              <tr>
                <th className="px-4 py-2.5">When</th>
                <th className="px-4 py-2.5">Actor</th>
                <th className="px-4 py-2.5">Action</th>
                <th className="px-4 py-2.5">Target</th>
                <th className="px-4 py-2.5">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {events.map((e) => (
                <tr
                  key={e.id}
                  onClick={() => setSelected(e)}
                  className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/40"
                >
                  <td className="px-4 py-2.5 text-xs text-gray-500 dark:text-gray-400">
                    {e.ts ? new Date(e.ts).toLocaleString('en-IN') : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-gray-700 dark:text-gray-300">{e.actor}</td>
                  <td className="px-4 py-2.5">
                    <code className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                      {e.action}
                    </code>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-gray-500 dark:text-gray-400">
                    {e.target ?? '—'}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-gray-500 dark:text-gray-400">
                    {e.ipAddress ?? '—'}
                  </td>
                </tr>
              ))}
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

      {/* Detail drawer */}
      {selected && <EventDrawer event={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function TextFilter({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
      {label}
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={cn(
          'rounded-md border px-2 py-1 text-xs',
          'border-gray-200 bg-white text-gray-700 placeholder:text-gray-400',
          'dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500'
        )}
      />
    </label>
  );
}

function EventDrawer({ event, onClose }: { event: AuditEvent; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-40 flex justify-end bg-black/30"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="h-full w-full max-w-lg overflow-y-auto border-l border-gray-200 bg-white p-5 shadow-xl dark:border-gray-800 dark:bg-gray-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Audit event</h3>
            <p className="mt-0.5 font-mono text-[11px] text-gray-500 dark:text-gray-400">
              {event.id}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <dl className="mt-4 space-y-2 text-xs">
          <Row k="When" v={event.ts ? new Date(event.ts).toLocaleString('en-IN') : '—'} />
          <Row k="Actor" v={event.actor} />
          <Row k="Action" v={<code>{event.action}</code>} />
          <Row k="Target" v={event.target ?? '—'} />
          <Row k="IP" v={event.ip ?? '—'} />
          <Row k="User agent" v={event.userAgent ?? '—'} />
        </dl>

        <JsonBlock title="Before" value={event.before} />
        <JsonBlock title="After" value={event.after} />
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <dt className="w-24 shrink-0 text-gray-500 dark:text-gray-400">{k}</dt>
      <dd className="min-w-0 flex-1 break-words text-gray-800 dark:text-gray-200">{v}</dd>
    </div>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  if (!value) return null;
  return (
    <div className="mt-4">
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
        {title}
      </p>
      <pre className="max-h-60 overflow-auto rounded-md bg-gray-50 p-2 text-[11px] text-gray-800 dark:bg-gray-800 dark:text-gray-200">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}
