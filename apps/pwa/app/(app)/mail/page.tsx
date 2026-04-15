'use client';

import * as React from 'react';
import { Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Search, Inbox, Loader2, Mail, LinkIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { EmailCard } from '@/components/mail/email-card';
import { Skeleton } from '@/components/ui/skeleton';
import { useMailList } from '@/lib/hooks/use-mail';
import { useLinkedAccounts } from '@/lib/hooks/use-account-link';
import { useAuthStore } from '@/store/auth-store';
import type { EmailSummary } from '@/lib/api/mail';

type FilterTab = 'all' | 'urgent' | 'unread' | 'government';

const FILTER_TABS: { id: FilterTab; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'urgent', label: 'Urgent' },
  { id: 'unread', label: 'Unread' },
  { id: 'government', label: 'Government' },
];

function EmailListSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="rounded-xl border border-gray-200 p-3.5 dark:border-gray-700">
          <div className="flex gap-3">
            <Skeleton className="h-9 w-9 rounded-full shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="flex justify-between">
                <Skeleton className="h-3.5 w-1/4" />
                <Skeleton className="h-3 w-12" />
              </div>
              <Skeleton className="h-3.5 w-2/3" />
              <Skeleton className="h-3 w-full" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Convert API EmailSummary → EmailCard props */
function toCardProps(email: EmailSummary) {
  return {
    id: email.id,
    from: email.from,
    subject: email.subject,
    preview: email.preview,
    receivedAt: new Date(email.receivedAt),
    isRead: email.isRead,
    urgencyLevel: email.urgencyLevel,
    hasAttachment: email.hasAttachment,
    linkedAccount: email.linkedAccount,
  };
}

function NoAccountConnected() {
  const router = useRouter();
  return (
    <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
      <div className="flex flex-col items-center justify-center py-20">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary-50 dark:bg-primary-900/20">
          <Mail size={28} className="text-primary-500" />
        </div>
        <p className="text-base font-semibold text-gray-900 dark:text-gray-100">
          No email account connected
        </p>
        <p className="mt-1.5 text-center text-sm text-gray-500 dark:text-gray-400 max-w-xs">
          Link your Google Workspace account to start viewing and managing your emails.
        </p>
        <button
          onClick={() => router.push('/settings')}
          className={cn(
            'mt-5 flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium',
            'bg-primary-600 text-white hover:bg-primary-700',
            'transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500'
          )}
        >
          <LinkIcon size={16} />
          Connect Account
        </button>
      </div>
    </div>
  );
}

function MailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { activeAccountId } = useAuthStore();
  const { data: linkedAccounts, isLoading: isLoadingAccounts } = useLinkedAccounts();
  const [activeFilter, setActiveFilter] = React.useState<FilterTab>(
    (searchParams.get('filter') as FilterTab) ?? 'all'
  );
  const [searchQuery, setSearchQuery] = React.useState('');
  const [debouncedSearch, setDebouncedSearch] = React.useState('');

  // Debounce search input
  React.useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const hasAccount = activeAccountId || (linkedAccounts && linkedAccounts.length > 0);

  const {
    data,
    isLoading,
    isError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useMailList({ filter: activeFilter, search: debouncedSearch });

  // Flatten paginated results — must be called before any early return (rules of hooks)
  const emails = React.useMemo(() => {
    if (!data?.pages) return [];
    return data.pages.flatMap((page) => page.emails);
  }, [data]);

  const total = data?.pages?.[0]?.total ?? 0;

  // Show connect prompt if no linked accounts
  if (!isLoadingAccounts && !hasAccount) {
    return <NoAccountConnected />;
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
      {/* Search */}
      <div className="relative mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search emails…"
          className={cn(
            'w-full rounded-xl border border-gray-200 bg-white py-2.5 pl-9 pr-4 text-sm',
            'placeholder:text-gray-400 text-gray-900',
            'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
            'dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100'
          )}
        />
      </div>

      {/* Filter tabs */}
      <div className="mb-4 flex gap-1 overflow-x-auto pb-1" role="tablist">
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeFilter === tab.id}
            onClick={() => setActiveFilter(tab.id)}
            className={cn(
              'shrink-0 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500',
              activeFilter === tab.id
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Email list */}
      {isLoading || isLoadingAccounts ? (
        <EmailListSkeleton />
      ) : isError ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Inbox size={40} className="text-gray-300 dark:text-gray-600 mb-3" />
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
            Failed to load emails
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Please check your connection and try again.
          </p>
        </div>
      ) : emails.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Inbox size={40} className="text-gray-300 dark:text-gray-600 mb-3" />
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">No emails found</p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            {debouncedSearch ? 'Try a different search term' : 'Nothing here yet'}
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-2" role="list">
            {emails.map((email) => (
              <div key={email.id} role="listitem">
                <EmailCard
                  {...toCardProps(email)}
                  onClick={() => router.push(`/mail/${email.id}`)}
                />
              </div>
            ))}
          </div>

          {/* Load more */}
          {hasNextPage && (
            <div className="mt-4 flex justify-center">
              <button
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className={cn(
                  'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium',
                  'text-primary-600 hover:bg-primary-50 dark:text-primary-400 dark:hover:bg-primary-900/20',
                  'transition-colors disabled:opacity-50'
                )}
              >
                {isFetchingNextPage && <Loader2 size={14} className="animate-spin" />}
                {isFetchingNextPage ? 'Loading…' : `Load more (${total - emails.length} remaining)`}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function MailPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-3xl px-4 py-6 sm:px-6"><EmailListSkeleton /></div>}>
      <MailContent />
    </Suspense>
  );
}
