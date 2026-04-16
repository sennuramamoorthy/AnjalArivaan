'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { InlineComposer } from '@/components/mail/inline-composer';

/**
 * Standalone compose page — used when the user clicks the "Compose" button
 * in the sidebar to create a new email (not a reply/forward).
 */
export default function ComposePage() {
  const router = useRouter();

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div className="sticky top-0 z-20 flex h-12 items-center gap-2 border-b border-gray-200 bg-white/95 px-3 backdrop-blur-sm dark:border-gray-800 dark:bg-gray-950/95">
        <button
          onClick={() => router.back()}
          className={cn(
            'flex items-center gap-1.5 rounded px-1.5 text-sm font-medium text-gray-600 dark:text-gray-400',
            'hover:text-gray-900 dark:hover:text-gray-100 transition-colors',
          )}
          aria-label="Back"
        >
          <ArrowLeft size={16} />
          <span className="hidden sm:inline">Back</span>
        </button>
        <h1 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
          New Message
        </h1>
      </div>

      {/* Composer */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
          <InlineComposer
            threadId="new"
            initial={{
              mode: 'compose',
              to: [],
              cc: [],
              subject: '',
              body: '',
            }}
            onClose={() => router.back()}
            onSent={() => router.push('/mail?folder=sent')}
          />
        </div>
      </div>
    </div>
  );
}
