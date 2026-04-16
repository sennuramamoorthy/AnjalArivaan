'use client';

import * as React from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowLeft,
  Sparkles,
  AlertCircle,
  Reply,
  ReplyAll,
  Forward,
  Check,
  Archive,
  MoreVertical,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { EmailThread } from '@/components/mail/email-thread';
import { AiSummaryPanel } from '@/components/mail/ai-summary-panel';
import {
  InlineComposer,
  type InlineComposerInitial,
} from '@/components/mail/inline-composer';
import { useUIStore } from '@/store/ui-store';
import { useAuthStore } from '@/store/auth-store';
import { useThread, useMarkThreadRead } from '@/lib/hooks/use-mail';
import type { EmailMessage, ComposeMode } from '@/lib/api/mail';

/** Ghost button used in the detail toolbar — icon + label, hover-tinted. */
function ToolbarButton({
  icon: Icon,
  label,
  onClick,
}: {
  icon: React.ElementType;
  label: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'hidden items-center gap-1.5 rounded-md border border-transparent px-2.5 py-1.5 text-xs font-medium text-gray-600 transition-colors sm:flex',
        'hover:border-gray-200 hover:bg-gray-100 hover:text-gray-900',
        'dark:text-gray-400 dark:hover:border-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-100',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500'
      )}
    >
      <Icon size={14} />
      {label}
    </button>
  );
}

function ToolbarDivider() {
  return <span className="mx-1 hidden h-5 w-px bg-gray-200 dark:bg-gray-700 sm:block" />;
}

export default function MailDetailPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const threadId = params.id as string;
  // When the user goes back to the list (mobile) we keep the folder/filter
  // they were viewing so they don't snap back to Inbox.
  const listHref = React.useMemo(() => {
    const qs = searchParams.toString();
    return qs ? `/mail?${qs}` : '/mail';
  }, [searchParams]);

  const { aiPanelOpen, setAiPanelOpen } = useUIStore();
  const [composeInitial, setComposeInitial] =
    React.useState<InlineComposerInitial | null>(null);
  const currentUserEmail = useAuthStore((s) => s.user?.email?.toLowerCase());

  const { data: thread, isLoading, isError } = useThread(threadId);
  const { mutate: markThreadRead } = useMarkThreadRead();

  // Mark as read once the thread has loaded — waiting for `thread` ensures
  // the auth store has already been hydrated and `accountId` is available,
  // otherwise the backend rejects the request with a 400.
  React.useEffect(() => {
    if (threadId && thread) {
      markThreadRead(threadId);
    }
  }, [threadId, thread, markThreadRead]);

  /**
   * "Draft Reply" from the AI Summary panel — open the inline composer in
   * reply mode so the user can immediately trigger AI draft (with optional
   * context) and send from the same place.
   */
  const handleDraftReply = () => {
    setAiPanelOpen(false);
    openCompose('reply');
  };

  /**
   * Build the initial compose state for Reply / Reply All / Forward.
   *
   * - Reply:     to = original sender only
   * - Reply all: to = original sender; cc = (original to + cc) minus self + sender
   * - Forward:   to = empty; subject "Fwd:"; body quotes the original
   */
  const openCompose = React.useCallback(
    (mode: ComposeMode) => {
      if (!thread) return;
      const messages = thread.messages;
      const last: EmailMessage | undefined = messages[messages.length - 1];
      if (!last) return;

      const senderEmail = last.from.email;
      const originalTo = (last.to ?? []).map((p) => p.email).filter(Boolean);
      const originalCc = (last.cc ?? []).map((p) => p.email).filter(Boolean);

      const isSelf = (addr: string) =>
        currentUserEmail && addr.toLowerCase() === currentUserEmail;

      const dedupedCc = Array.from(
        new Set([...originalTo, ...originalCc].filter((a) => a && a !== senderEmail && !isSelf(a))),
      );

      const baseSubject = thread.subject || last.subject || '';
      const stripRe = (s: string) => s.replace(/^(re:|fwd?:)\s*/i, '');
      const formattedDate = new Date(last.receivedAt).toLocaleString();
      const quoted =
        `\n\n\nOn ${formattedDate}, ${last.from.name || last.from.email} wrote:\n> ` +
        (last.bodyText || '').split('\n').join('\n> ');

      let to: string[] = [];
      let cc: string[] = [];
      let subject = baseSubject;
      let body = '';

      if (mode === 'reply') {
        to = [senderEmail];
        subject = baseSubject.toLowerCase().startsWith('re:')
          ? baseSubject
          : `Re: ${stripRe(baseSubject)}`;
        body = quoted;
      } else if (mode === 'replyAll') {
        to = [senderEmail];
        cc = dedupedCc;
        subject = baseSubject.toLowerCase().startsWith('re:')
          ? baseSubject
          : `Re: ${stripRe(baseSubject)}`;
        body = quoted;
      } else if (mode === 'forward') {
        to = [];
        subject = baseSubject.toLowerCase().startsWith('fwd:')
          ? baseSubject
          : `Fwd: ${stripRe(baseSubject)}`;
        body =
          `\n\n---------- Forwarded message ----------\n` +
          `From: ${last.from.name || ''} <${last.from.email}>\n` +
          `Date: ${formattedDate}\n` +
          `Subject: ${last.subject}\n` +
          `To: ${originalTo.join(', ')}\n\n` +
          (last.bodyText || '');
      }

      setComposeInitial({ mode, to, cc, subject, body });
    },
    [thread, currentUserEmail],
  );

  return (
    <div className="relative flex h-full flex-col">
      {/* Detail toolbar — modeled on AnjalArivaan_UI_Themes.html `.detail-toolbar`.
          Reply / Reply All / Forward · Mark Done / Archive · overflow.
          Mobile keeps a leading back button; on lg+ the list is always visible. */}
      <div className="sticky top-0 z-20 flex h-12 items-center gap-1 border-b border-gray-200 bg-white/95 px-3 backdrop-blur-sm dark:border-gray-800 dark:bg-gray-950/95">
        <button
          onClick={() => router.push(listHref)}
          className={cn(
            'mr-1 flex items-center gap-1.5 rounded px-1.5 text-sm font-medium text-gray-600 dark:text-gray-400 lg:hidden',
            'hover:text-gray-900 dark:hover:text-gray-100 transition-colors',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500'
          )}
          aria-label="Back to inbox"
        >
          <ArrowLeft size={16} />
        </button>

        {/* Primary action */}
        <button
          type="button"
          onClick={() => openCompose('reply')}
          disabled={!thread}
          className={cn(
            'flex items-center gap-1.5 rounded-md bg-primary-600 px-3 py-1.5 text-xs font-semibold text-white',
            'hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-1'
          )}
        >
          <Reply size={14} />
          Reply
        </button>

        <ToolbarButton icon={ReplyAll} label="Reply All" onClick={() => openCompose('replyAll')} />
        <ToolbarButton icon={Forward} label="Forward" onClick={() => openCompose('forward')} />

        <ToolbarDivider />

        <ToolbarButton icon={Check} label="Mark Done" />
        <ToolbarButton icon={Archive} label="Archive" />

        {/* Right-side cluster */}
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant={aiPanelOpen ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setAiPanelOpen(!aiPanelOpen)}
            aria-pressed={aiPanelOpen}
          >
            <Sparkles size={14} />
            AI Summary
          </Button>
          <button
            type="button"
            aria-label="More actions"
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-md text-gray-500 transition-colors',
              'hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-100',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500'
            )}
          >
            <MoreVertical size={16} />
          </button>
        </div>
      </div>

      {/* Content area — scrolls inside the pane */}
      <div className="flex-1 overflow-y-auto">
        {/* ~90% of pane width, with comfortable side padding */}
        <div className="w-full px-4 py-6 sm:px-6">
          {isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-8 w-3/4" />
              <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-700 space-y-3">
                <div className="flex gap-3">
                  <Skeleton className="h-9 w-9 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-1/3" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                </div>
                <Skeleton className="h-32 w-full" />
              </div>
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center justify-center py-20">
              <AlertCircle size={40} className="text-red-400 mb-3" />
              <p className="text-sm font-medium text-red-500">Failed to load thread</p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                Please check your connection and try again
              </p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-4"
                onClick={() => router.back()}
              >
                Back to inbox
              </Button>
            </div>
          ) : thread ? (
            <>
              {/* Inline AI Summary — rendered above the thread when toggled on */}
              <AiSummaryPanel threadId={threadId} onDraftReply={handleDraftReply} />

              <EmailThread thread={thread} />

              {/* Inline composer — rendered in the same right pane, below the
                  thread. Hosts the AI Draft action with optional context. */}
              {composeInitial && (
                <InlineComposer
                  threadId={threadId}
                  initial={composeInitial}
                  onClose={() => setComposeInitial(null)}
                />
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
