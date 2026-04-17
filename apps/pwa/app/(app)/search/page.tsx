'use client';

import * as React from 'react';
import Link from 'next/link';
import { Search as SearchIcon, Paperclip, Mail as MailIcon, type LucideIcon } from 'lucide-react';

import { cn } from '@/lib/utils';
import { useSearch } from '@/lib/hooks/use-search';
import type { SearchDocType, SearchHit } from '@/lib/api/search';

/** Debounce hook — 250ms default. */
function useDebounced<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

const FILTERS: Array<{ id: SearchDocType; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'mail', label: 'Mail' },
  { id: 'attachment', label: 'Attachments' },
];

export default function SearchPage() {
  const [q, setQ] = React.useState('');
  const [type, setType] = React.useState<SearchDocType>('all');
  const debounced = useDebounced(q, 250);

  const { data, isLoading, isError, error } = useSearch({ q: debounced, type });

  return (
    <div className="mx-auto flex h-full w-full max-w-3xl flex-col gap-4 p-4 sm:p-6">
      <header className="flex flex-col gap-3">
        <div className="relative">
          <SearchIcon
            size={18}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
          />
          <input
            type="search"
            autoFocus
            placeholder="Search emails and attachments..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className={cn(
              'w-full rounded-lg border border-gray-200 bg-white py-2.5 pl-10 pr-4 text-sm',
              'placeholder:text-gray-400 text-gray-900',
              'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
              'dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100',
            )}
          />
        </div>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setType(f.id)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                type === f.id
                  ? 'bg-primary-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300',
              )}
              aria-pressed={type === f.id}
            >
              {f.label}
            </button>
          ))}
        </div>
      </header>

      <section className="flex-1">
        {debounced.trim().length < 2 && (
          <EmptyState message="Type at least 2 characters to search" />
        )}
        {debounced.trim().length >= 2 && isLoading && (
          <EmptyState message="Searching..." />
        )}
        {isError && (
          <EmptyState
            message={
              error instanceof Error ? error.message : 'Search failed'
            }
            tone="error"
          />
        )}
        {data && data.results.length === 0 && !isLoading && (
          <EmptyState message={`No results for "${debounced}"`} />
        )}
        {data && data.results.length > 0 && (
          <ul className="flex flex-col divide-y divide-gray-100 dark:divide-gray-800">
            {data.results.map((hit) => (
              <ResultRow key={hit.id} hit={hit} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function ResultRow({ hit }: { hit: SearchHit }) {
  const Icon = hit.type === 'attachment' ? Paperclip : MailIcon;
  const title = hit.subject || hit.filename || hit.id;
  const body =
    hit.type === 'mail' ? (
      <Link
        href={`/mail/${hit.id}`}
        className="block py-3 hover:bg-gray-50 dark:hover:bg-gray-900"
      >
        <RowContent Icon={Icon} title={title} hit={hit} />
      </Link>
    ) : (
      <div className="block py-3">
        <RowContent Icon={Icon} title={title} hit={hit} />
      </div>
    );
  return <li>{body}</li>;
}

function RowContent({
  Icon,
  title,
  hit,
}: {
  Icon: LucideIcon;
  title: string;
  hit: SearchHit;
}) {
  return (
    <div className="flex items-start gap-3 px-1">
      <Icon
        size={16}
        className="mt-0.5 shrink-0 text-gray-500 dark:text-gray-400"
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
            {title}
          </p>
          <span className="shrink-0 text-[10px] uppercase tracking-wide text-gray-400">
            {hit.sources.join(' + ')}
          </span>
        </div>
        {hit.snippet && (
          <p className="mt-0.5 line-clamp-2 text-xs text-gray-500 dark:text-gray-400">
            {hit.snippet}
          </p>
        )}
      </div>
    </div>
  );
}

function EmptyState({
  message,
  tone = 'muted',
}: {
  message: string;
  tone?: 'muted' | 'error';
}) {
  return (
    <div
      className={cn(
        'flex h-full min-h-[200px] items-center justify-center rounded-lg border border-dashed text-sm',
        tone === 'error'
          ? 'border-red-200 text-red-500 dark:border-red-800'
          : 'border-gray-200 text-gray-500 dark:border-gray-800 dark:text-gray-400',
      )}
    >
      {message}
    </div>
  );
}
