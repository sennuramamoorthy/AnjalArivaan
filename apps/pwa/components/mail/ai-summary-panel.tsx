'use client';

import * as React from 'react';
import { X, Sparkles, MessageSquarePlus } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { useAiSummary } from '@/lib/hooks/use-mail';
import { useUIStore } from '@/store/ui-store';

interface AiSummaryPanelProps {
  threadId: string;
  onDraftReply: () => void;
}

export function AiSummaryPanel({ threadId, onDraftReply }: AiSummaryPanelProps) {
  const { aiPanelOpen, setAiPanelOpen } = useUIStore();
  const { data: summary, isLoading } = useAiSummary(threadId);

  return (
    <AnimatePresence>
      {aiPanelOpen && (
        <>
          {/* Mobile overlay backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/40 lg:hidden"
            onClick={() => setAiPanelOpen(false)}
            aria-hidden
          />

          {/* Panel */}
          <motion.aside
            key="panel"
            initial={{ x: '100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0 }}
            transition={{ type: 'tween', duration: 0.3, ease: 'easeOut' }}
            className={cn(
              'fixed inset-y-0 right-0 z-50 w-full max-w-sm',
              'flex flex-col border-l border-gray-200 bg-white shadow-xl',
              'dark:border-gray-700 dark:bg-gray-900',
              // Desktop: positioned relative to content
              'lg:fixed lg:inset-y-0 lg:right-0 lg:z-30'
            )}
            aria-label="AI Summary"
          >
            {/* Header */}
            <div className="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 px-4 dark:border-gray-700">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary-100 dark:bg-primary-900/40">
                  <Sparkles size={14} className="text-primary-600 dark:text-primary-400" />
                </div>
                <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">AI Summary</h2>
              </div>
              <button
                onClick={() => setAiPanelOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label="Close AI panel"
              >
                <X size={16} />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {isLoading || !summary ? (
                <div className="space-y-3">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-5/6" />
                  <Skeleton className="h-4 w-2/3" />
                  <Separator className="my-2" />
                  <Skeleton className="h-3 w-1/2" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-4/5" />
                </div>
              ) : (
                <>
                  <div>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">
                      Summary
                    </h3>
                    <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                      {summary.summary}
                    </p>
                  </div>

                  {summary.keyPoints.length > 0 && (
                    <div>
                      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">
                        Key Points
                      </h3>
                      <ul className="space-y-1.5">
                        {summary.keyPoints.map((point, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
                            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary-500" />
                            {point}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {summary.urgencyReason && (
                    <div className="rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950/30">
                      <p className="text-xs font-semibold text-red-700 dark:text-red-400 mb-1">
                        Why this is urgent
                      </p>
                      <p className="text-xs text-red-600 dark:text-red-400">{summary.urgencyReason}</p>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Footer */}
            <div className="shrink-0 border-t border-gray-200 p-4 dark:border-gray-700 space-y-3">
              <Button className="w-full" onClick={onDraftReply} disabled={isLoading || !summary}>
                <MessageSquarePlus size={15} />
                Draft Reply
              </Button>

              {/* Model attribution */}
              <p className="text-center text-[10px] text-gray-400 dark:text-gray-500">
                Generated by <span className="font-medium">Llama 3.1</span> · Takshashila LLM
                {summary && (
                  <> · {summary.retrievedChunkCount} context chunks</>
                )}
              </p>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
