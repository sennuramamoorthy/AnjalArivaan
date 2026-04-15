'use client';

import * as React from 'react';
import { RefreshCw, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn, formatDateTime } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

interface DailyBriefingCardProps {
  content?: string;
  generatedAt?: string;
  isLoading: boolean;
  onRefresh: () => void;
}

// Parse simple markdown **bold** to JSX
function renderBriefingText(text: string): React.ReactNode[] {
  return text.split('\n').map((line, i) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g).map((part, j) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={j}>{part.slice(2, -2)}</strong>;
      }
      return part;
    });
    return (
      <p key={i} className={cn('text-sm leading-relaxed', i > 0 && 'mt-2')}>
        {parts}
      </p>
    );
  });
}

export function DailyBriefingCard({
  content,
  generatedAt,
  isLoading,
  onRefresh,
}: DailyBriefingCardProps) {
  const [isExpanded, setIsExpanded] = React.useState(true);

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-2xl border border-primary-200',
        'bg-gradient-to-br from-primary-50 via-white to-indigo-50',
        'dark:border-primary-800 dark:from-primary-900/30 dark:via-gray-900 dark:to-indigo-900/20'
      )}
    >
      {/* Decorative background circle */}
      <div
        className="pointer-events-none absolute -right-12 -top-12 h-48 w-48 rounded-full bg-primary-100/50 dark:bg-primary-900/20"
        aria-hidden
      />

      {/* Header */}
      <div className="relative flex items-center justify-between px-5 pt-5 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-600 shadow-sm">
            <Sparkles size={18} className="text-white" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900 dark:text-gray-100">Daily Briefing</h2>
            {generatedAt && (
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Generated {formatDateTime(generatedAt)}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            isLoading={isLoading}
            className="text-gray-500"
            aria-label="Refresh briefing"
          >
            <RefreshCw size={14} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsExpanded((v) => !v)}
            aria-label={isExpanded ? 'Collapse briefing' : 'Expand briefing'}
            className="text-gray-500"
          >
            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </Button>
        </div>
      </div>

      {/* Body */}
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="relative px-5 pb-5">
              {isLoading || !content ? (
                <div className="space-y-2.5">
                  <Skeleton className="h-4 w-full bg-primary-100 dark:bg-primary-800/40" />
                  <Skeleton className="h-4 w-5/6 bg-primary-100 dark:bg-primary-800/40" />
                  <Skeleton className="h-4 w-full bg-primary-100 dark:bg-primary-800/40" />
                  <Skeleton className="h-4 w-4/5 bg-primary-100 dark:bg-primary-800/40" />
                  <Skeleton className="h-4 w-3/4 bg-primary-100 dark:bg-primary-800/40" />
                </div>
              ) : (
                <div className="text-gray-700 dark:text-gray-300 space-y-0">
                  {renderBriefingText(content)}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
