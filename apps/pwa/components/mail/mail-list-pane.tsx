'use client';

import * as React from 'react';
import { Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Search,
  Inbox as InboxIcon,
  Loader2,
  Mail,
  LinkIcon,
  Send,
  FileText,
  Trash2,
  Star,
  AlertTriangle,
  ArrowUpDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { EmailCard } from '@/components/mail/email-card';
import { Skeleton } from '@/components/ui/skeleton';
import { useMailList } from '@/lib/hooks/use-mail';
import { useLinkedAccounts } from '@/lib/hooks/use-account-link';
import { useAuthStore } from '@/store/auth-store';
import type { EmailSummary, MailFolder, MailSort } from '@/lib/api/mail';

/**
 * MailListPane — the middle column of the desktop 3-pane mail view
 * (sidebar | list | detail). Modeled on the AnjalArivaan_UI_Themes.html
 * `.list-pane` block: header (title + count + search) above a scrollable
 * email list. Selecting a row routes to /mail/[id] — on desktop the
 * detail loads in the right pane, on mobile it takes over the screen.
 */

type FilterTab = 'all' | 'urgent' | 'unread' | 'government';

const FILTER_TABS: { id: FilterTab; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'urgent', label: 'Urgent' },
  { id: 'unread', label: 'Unread' },
  { id: 'government', label: 'Government' },
];

const FOLDER_META: Record<
  MailFolder,
  { title: string; icon: React.ElementType; emptyHint: string }
> = {
  inbox: { title: 'Inbox', icon: InboxIcon, emptyHint: 'Nothing in your inbox.' },
  sent: { title: 'Sent', icon: Send, emptyHint: 'No sent messages.' },
  drafts: { title: 'Drafts', icon: FileText, emptyHint: 'No drafts saved.' },
  trash: { title: 'Trash', icon: Trash2, emptyHint: 'Trash is empty.' },
  starred: { title: 'Starred', icon: Star, emptyHint: 'No starred messages.' },
  important: {
    title: 'Important',
    icon: AlertTriangle,
    emptyHint: 'Nothing flagged important.',
  },
  all: { title: 'All Mail', icon: Mail, emptyHint: 'No mail in this account.' },
};

const FOLDER_VALUES: ReadonlySet<MailFolder> = new Set([
  'inbox',
  'sent',
  'drafts',
  'trash',
  'starred',
  'important',
  'all',
]);

function parseFolder(value: string | null): MailFolder {
  return value && FOLDER_VALUES.has(value as MailFolder)
    ? (value as MailFolder)
    : 'inbox';
}

const SORT_OPTIONS: { id: MailSort; label: string }[] = [
  { id: 'newest', label: 'Newest first' },
  { id: 'oldest', label: 'Oldest first' },
  { id: 'sender', label: 'Sender (A→Z)' },
  { id: 'subject', label: 'Subject (A→Z)' },
];

const SORT_VALUES: ReadonlySet<MailSort> = new Set(SORT_OPTIONS.map((s) => s.id));

function parseSort(value: string | null): MailSort {
  return value && SORT_VALUES.has(value as MailSort)
    ? (value as MailSort)
    : 'newest';
}

function EmailListSkeleton() {
  return (
    <div className="space-y-2 p-3">
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
    // Gmail labels deliberately dropped — only app-defined tags are rendered.
    // When the backend starts returning `appTags`, forward them here.
    appTags: (email as unknown as { appTags?: string[] }).appTags,
  };
}

function NoAccountConnected() {
  const router = useRouter();
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 py-16">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary-50 dark:bg-primary-900/20">
        <Mail size={28} className="text-primary-500" />
      </div>
      <p className="text-base font-semibold text-gray-900 dark:text-gray-100">
        No email account connected
      </p>
      <p className="mt-1.5 max-w-xs text-center text-sm text-gray-500 dark:text-gray-400">
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
  );
}

interface MailListPaneInnerProps {
  selectedId?: string;
}

function MailListPaneInner({ selectedId }: MailListPaneInnerProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { activeAccountId } = useAuthStore();
  const { data: linkedAccounts, isLoading: isLoadingAccounts } = useLinkedAccounts();

  // The folder is URL-driven (sidebar links set it). The cross-cut filter
  // (urgent / unread / government) is also URL-driven so deep links work.
  const folder: MailFolder = parseFolder(searchParams.get('folder'));
  const activeFilter: FilterTab =
    (searchParams.get('filter') as FilterTab) ?? 'all';
  const activeSort: MailSort = parseSort(searchParams.get('sort'));
  const folderMeta = FOLDER_META[folder];

  function setFilter(next: FilterTab) {
    const params = new URLSearchParams(searchParams.toString());
    if (next === 'all') params.delete('filter');
    else params.set('filter', next);
    const qs = params.toString();
    router.replace(qs ? `/mail?${qs}` : '/mail');
  }

  function setSort(next: MailSort) {
    const params = new URLSearchParams(searchParams.toString());
    if (next === 'newest') params.delete('sort');
    else params.set('sort', next);
    const qs = params.toString();
    router.replace(qs ? `/mail?${qs}` : '/mail');
  }

  const [searchQuery, setSearchQuery] = React.useState('');
  const [debouncedSearch, setDebouncedSearch] = React.useState('');

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
  } = useMailList({ folder, filter: activeFilter, search: debouncedSearch, sort: activeSort });

  const emails = React.useMemo(() => {
    if (!data?.pages) return [];
    return data.pages.flatMap((page) => page.emails);
  }, [data]);

  const total = data?.pages?.[0]?.total ?? 0;
  const unreadCount = emails.filter((e) => !e.isRead).length;

  if (!isLoadingAccounts && !hasAccount) {
    return <NoAccountConnected />;
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header — title row + search box (mirrors .list-header in the mockup) */}
      <div className="border-b border-gray-200 px-5 pb-3 pt-4 dark:border-gray-800">
        <div className="mb-3 flex items-center justify-between">
          <h1 className="flex items-center gap-2 text-base font-bold text-gray-900 dark:text-gray-100">
            <folderMeta.icon size={16} className="text-gray-500 dark:text-gray-400" />
            {folderMeta.title}
          </h1>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {unreadCount > 0
              ? `${unreadCount} unread · ${emails.length} threads`
              : `${emails.length} threads`}
          </span>
        </div>

        <div
          className={cn(
            'flex items-center gap-2 rounded-lg px-3 py-2',
            'bg-gray-100 border border-gray-200 dark:bg-gray-800/60 dark:border-gray-700'
          )}
        >
          <Search size={14} className="text-gray-400" />
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search mail, tasks, people…"
            className={cn(
              'flex-1 bg-transparent text-sm outline-none',
              'text-gray-900 placeholder:text-gray-400 dark:text-gray-100'
            )}
          />
        </div>

        <div className="mt-3 flex items-center gap-2">
          <div className="flex flex-1 gap-1 overflow-x-auto" role="tablist">
            {FILTER_TABS.map((tab) => (
              <button
                key={tab.id}
                role="tab"
                aria-selected={activeFilter === tab.id}
                onClick={() => setFilter(tab.id)}
                className={cn(
                  'shrink-0 rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
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

          {/* Sort — native <select> keeps a11y + mobile ergonomics free. */}
          <label
            className={cn(
              'flex shrink-0 items-center gap-1 rounded-md border px-2 py-1',
              'border-gray-200 bg-white text-xs text-gray-600',
              'dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400',
              'focus-within:ring-2 focus-within:ring-primary-500'
            )}
            title="Sort"
          >
            <ArrowUpDown size={12} className="text-gray-400" />
            <select
              aria-label="Sort emails"
              value={activeSort}
              onChange={(e) => setSort(e.target.value as MailSort)}
              className="bg-transparent pr-1 text-xs font-medium outline-none"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {/* Scrollable list */}
      <div className="flex-1 overflow-y-auto">
        {isLoading || isLoadingAccounts ? (
          <EmailListSkeleton />
        ) : isError ? (
          <div className="flex flex-col items-center justify-center px-4 py-16">
            <InboxIcon size={40} className="mb-3 text-gray-300 dark:text-gray-600" />
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Failed to load emails
            </p>
            <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
              Please check your connection and try again.
            </p>
          </div>
        ) : emails.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-4 py-16">
            <folderMeta.icon size={40} className="mb-3 text-gray-300 dark:text-gray-600" />
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
              {debouncedSearch ? 'No emails match your search' : `${folderMeta.title} is empty`}
            </p>
            <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
              {debouncedSearch ? 'Try a different search term' : folderMeta.emptyHint}
            </p>
          </div>
        ) : (
          <>
            <div role="list" className="divide-y divide-gray-100 dark:divide-gray-800">
              {emails.map((email) => {
                const isSelected = email.threadId === selectedId || email.id === selectedId;
                return (
                  <div
                    key={email.id}
                    role="listitem"
                    className={cn(
                      // Reserve the 3px accent strip on every row so selecting
                      // a row doesn't shift the card width / reflow text.
                      'transition-colors border-l-[3px] border-l-transparent',
                      isSelected &&
                        'bg-primary-50 border-l-primary-600 dark:bg-primary-900/20'
                    )}
                  >
                    <EmailCard
                      {...toCardProps(email)}
                      onClick={() => {
                        // Preserve ?folder=… and ?filter=… when opening a
                        // thread so the list pane doesn't snap back to Inbox
                        // on navigation.
                        const qs = searchParams.toString();
                        router.push(`/mail/${email.threadId}${qs ? `?${qs}` : ''}`);
                      }}
                    />
                  </div>
                );
              })}
            </div>

            {hasNextPage && (
              <div className="flex justify-center py-4">
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
                  {isFetchingNextPage
                    ? 'Loading…'
                    : `Load more (${total - emails.length} remaining)`}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function MailListPane({ selectedId }: { selectedId?: string }) {
  return (
    <Suspense fallback={<EmailListSkeleton />}>
      <MailListPaneInner selectedId={selectedId} />
    </Suspense>
  );
}
