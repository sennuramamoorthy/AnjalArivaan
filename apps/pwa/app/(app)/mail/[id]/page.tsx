'use client';

import * as React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Sparkles, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { EmailThread } from '@/components/mail/email-thread';
import { AiSummaryPanel } from '@/components/mail/ai-summary-panel';
import { DraftReplyPanel } from '@/components/mail/draft-reply-panel';
import { useUIStore } from '@/store/ui-store';
import { useThread, useRequestAiDraft, useMarkRead } from '@/lib/hooks/use-mail';

export default function MailDetailPage() {
  const router = useRouter();
  const params = useParams();
  const threadId = params.id as string;

  const { aiPanelOpen, setAiPanelOpen } = useUIStore();
  const [showDraftPanel, setShowDraftPanel] = React.useState(false);

  const { data: thread, isLoading, isError } = useThread(threadId);
  const { mutate: requestDraft, data: draftData, isPending: draftLoading } = useRequestAiDraft(threadId);
  const { mutate: markRead } = useMarkRead();

  // Mark as read on mount
  React.useEffect(() => {
    if (threadId) {
      markRead(threadId);
    }
  }, [threadId, markRead]);

  const handleDraftReply = () => {
    setShowDraftPanel(true);
    setAiPanelOpen(false);
    requestDraft();
  };

  return (
    <div className="relative flex min-h-[calc(100vh-56px)] flex-col">
      {/* Top bar */}
      <div className="sticky top-0 z-20 flex h-12 items-center justify-between border-b border-gray-200 bg-white/95 px-4 backdrop-blur-sm dark:border-gray-800 dark:bg-gray-950/95">
        <button
          onClick={() => router.back()}
          className={cn(
            'flex items-center gap-1.5 text-sm font-medium text-gray-600 dark:text-gray-400',
            'hover:text-gray-900 dark:hover:text-gray-100 transition-colors',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 rounded'
          )}
        >
          <ArrowLeft size={16} />
          Back to inbox
        </button>

        <Button
          variant={aiPanelOpen ? 'primary' : 'secondary'}
          size="sm"
          onClick={() => setAiPanelOpen(!aiPanelOpen)}
          aria-pressed={aiPanelOpen}
        >
          <Sparkles size={14} />
          AI Summary
        </Button>
      </div>

      {/* Content area */}
      <div
        className={cn(
          'flex-1 transition-all duration-300',
          aiPanelOpen ? 'lg:mr-80' : ''
        )}
      >
        <div className="mx-auto max-w-2xl px-4 py-6 sm:px-6">
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
              <EmailThread thread={thread} />

              {/* AI Draft Panel */}
              {showDraftPanel && (
                <div className="mt-6">
                  <DraftReplyPanel
                    draft={draftData ?? null}
                    isLoading={draftLoading}
                    onRegenerate={() => requestDraft()}
                    onDiscard={() => setShowDraftPanel(false)}
                  />
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>

      {/* AI Summary Panel — slides in from right */}
      <AiSummaryPanel threadId={threadId} onDraftReply={handleDraftReply} />
    </div>
  );
}
