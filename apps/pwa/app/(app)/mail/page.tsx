'use client';

import { Mail } from 'lucide-react';

/**
 * /mail index — empty-state placeholder for the desktop detail pane when no
 * thread is selected. On mobile this page is hidden by mail/layout.tsx (the
 * list pane fills the screen instead), so users only ever see this on lg+.
 */
export default function MailIndexPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary-50 dark:bg-primary-900/20">
        <Mail size={28} className="text-primary-500" />
      </div>
      <p className="text-base font-semibold text-gray-900 dark:text-gray-100">
        Select an email to read
      </p>
      <p className="mt-1.5 max-w-sm text-sm text-gray-500 dark:text-gray-400">
        Choose a thread from the list to view its messages, AI summary, and
        suggested reply.
      </p>
    </div>
  );
}
