'use client';

import * as React from 'react';
import { ChevronDown, ChevronUp, Paperclip, Download } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn, formatDateTime, truncate } from '@/lib/utils';
import { Avatar } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import type { EmailThread as EmailThreadType, EmailMessage } from '@/lib/api/mail';

interface ThreadMessageProps {
  message: EmailMessage;
  defaultOpen?: boolean;
}

function ThreadMessage({ message, defaultOpen = false }: ThreadMessageProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);

  return (
    <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900 overflow-hidden">
      {/* Header — always visible */}
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className={cn(
          'flex w-full items-center gap-3 p-4 text-left',
          'hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-inset'
        )}
        aria-expanded={isOpen}
      >
        <Avatar name={message.from.name} size="md" className="shrink-0" />

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
              {message.from.name}
            </span>
            <div className="flex items-center gap-2 shrink-0">
              {message.hasAttachment && (
                <Paperclip size={13} className="text-gray-400" />
              )}
              <span className="text-xs text-gray-400">{formatDateTime(message.receivedAt)}</span>
              {isOpen ? (
                <ChevronUp size={14} className="text-gray-400" />
              ) : (
                <ChevronDown size={14} className="text-gray-400" />
              )}
            </div>
          </div>
          {!isOpen && (
            <p className="mt-0.5 text-xs text-gray-500 truncate">
              {truncate(message.bodyText, 80)}
            </p>
          )}
          {isOpen && (
            <p className="text-xs text-gray-500">
              To: {message.to.map((t) => t.email).join(', ')}
              {message.cc && message.cc.length > 0 && (
                <span> · CC: {message.cc.map((c) => c.email).join(', ')}</span>
              )}
            </p>
          )}
        </div>
      </button>

      {/* Body */}
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <Separator />
            <div className="p-4">
              {message.bodyHtml ? (
                <div
                  className="prose prose-sm max-w-none dark:prose-invert text-gray-700 dark:text-gray-300"
                  dangerouslySetInnerHTML={{ __html: message.bodyHtml }}
                />
              ) : (
                <p className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">
                  {message.bodyText}
                </p>
              )}

              {/* Attachments */}
              {message.attachments && message.attachments.length > 0 && (
                <div className="mt-4 space-y-2">
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Attachments</p>
                  <div className="flex flex-wrap gap-2">
                    {message.attachments.map((att) => (
                      <div
                        key={att.id}
                        className={cn(
                          'flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2',
                          'bg-gray-50 dark:border-gray-700 dark:bg-gray-800'
                        )}
                      >
                        <Paperclip size={13} className="text-gray-400 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate max-w-[160px]">
                            {att.filename}
                          </p>
                          <p className="text-[10px] text-gray-400">
                            {(att.sizeBytes / 1024).toFixed(0)} KB
                          </p>
                        </div>
                        <button
                          className="ml-1 text-gray-400 hover:text-primary-600 dark:hover:text-primary-400"
                          aria-label={`Download ${att.filename}`}
                        >
                          <Download size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

interface EmailThreadProps {
  thread: EmailThreadType;
}

export function EmailThread({ thread }: EmailThreadProps) {
  return (
    <div className="space-y-2">
      {/* Subject + urgency */}
      <div className="flex items-start justify-between gap-3 mb-4">
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100 leading-snug">
          {thread.subject}
        </h1>
        {(thread.urgencyLevel === 'CRITICAL' || thread.urgencyLevel === 'HIGH') && (
          <Badge variant="urgent" className="shrink-0">
            {thread.urgencyLevel === 'CRITICAL' ? 'Critical' : 'High Priority'}
          </Badge>
        )}
      </div>

      {/* Messages */}
      {thread.messages.map((msg, i) => (
        <ThreadMessage
          key={msg.id}
          message={msg}
          defaultOpen={i === thread.messages.length - 1}
        />
      ))}
    </div>
  );
}
