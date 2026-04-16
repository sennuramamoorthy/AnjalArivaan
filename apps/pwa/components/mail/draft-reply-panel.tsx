'use client';

import * as React from 'react';
import { RefreshCw, Send, Trash2, ChevronDown, ChevronUp, FileText, Mail } from 'lucide-react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import type { AiDraft } from '@/lib/api/mail';

interface DraftReplyPanelProps {
  draft: AiDraft | null;
  isLoading: boolean;
  onRegenerate: () => void;
  onDiscard: () => void;
  onAccept?: (draftText: string) => void;
}

export function DraftReplyPanel({
  draft,
  isLoading,
  onRegenerate,
  onDiscard,
  onAccept,
}: DraftReplyPanelProps) {
  const [draftText, setDraftText] = React.useState('');
  const [contextOpen, setContextOpen] = React.useState(false);

  React.useEffect(() => {
    if (draft?.draftText) {
      setDraftText(draft.draftText);
    }
  }, [draft?.draftText]);

  const handleAccept = () => {
    onAccept?.(draftText);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">AI Draft Reply</h3>
        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            onClick={onRegenerate}
            isLoading={isLoading}
            aria-label="Regenerate draft"
          >
            <RefreshCw size={13} />
            Regenerate
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onDiscard}
            className="text-gray-400 hover:text-red-600"
            aria-label="Discard draft"
          >
            <Trash2 size={15} />
          </Button>
        </div>
      </div>

      {/* Draft textarea */}
      <div className="p-4">
        {isLoading && !draftText ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        ) : (
          <textarea
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            rows={8}
            className={cn(
              'w-full resize-none rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm',
              'text-gray-800 dark:text-gray-200',
              'dark:border-gray-700 dark:bg-gray-800',
              'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
              'transition-colors'
            )}
            aria-label="Draft reply text"
            placeholder="AI draft will appear here…"
          />
        )}
      </div>

      {/* Context sources accordion */}
      {draft && draft.contextSources.length > 0 && (
        <div className="border-t border-gray-200 dark:border-gray-700">
          <button
            type="button"
            onClick={() => setContextOpen((v) => !v)}
            className={cn(
              'flex w-full items-center justify-between px-4 py-3 text-xs font-medium',
              'text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800',
              'focus:outline-none transition-colors'
            )}
          >
            <span>Context sources ({draft.contextSources.length})</span>
            {contextOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>

          {contextOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              className="overflow-hidden"
            >
              <div className="space-y-1.5 px-4 pb-3">
                {draft.contextSources.map((src, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-800"
                  >
                    {src.type === 'email' ? (
                      <Mail size={12} className="mt-0.5 shrink-0 text-gray-400" />
                    ) : (
                      <FileText size={12} className="mt-0.5 shrink-0 text-gray-400" />
                    )}
                    <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
                      {src.snippet}
                    </p>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </div>
      )}

      {/* Footer actions */}
      <div className="border-t border-gray-200 p-4 dark:border-gray-700">
        <Button
          className="w-full"
          size="lg"
          onClick={handleAccept}
          disabled={!draftText || isLoading}
        >
          <Send size={15} />
          Use This Draft
        </Button>
        <p className="mt-2 text-center text-[10px] text-gray-400">
          Opens the in-app composer with this draft pre-filled
        </p>
      </div>
    </motion.div>
  );
}
