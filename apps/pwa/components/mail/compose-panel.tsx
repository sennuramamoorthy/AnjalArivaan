'use client';

import * as React from 'react';
import { X, Send, Loader2, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useSendReply } from '@/lib/hooks/use-mail';
import type { ComposeMode, SendReplyPayload } from '@/lib/api/mail';

export interface ComposeInitial {
  mode: ComposeMode;
  to: string[];
  cc: string[];
  subject: string;
  body: string;
  inReplyTo?: string;
  references?: string[];
}

interface ComposePanelProps {
  threadId: string;
  initial: ComposeInitial;
  onClose: () => void;
  onSent?: () => void;
}

const MODE_LABEL: Record<ComposeMode, string> = {
  reply: 'Reply',
  replyAll: 'Reply all',
  forward: 'Forward',
  compose: 'New message',
};

/**
 * Chip-style recipient editor — backspace deletes the last chip, Enter /
 * comma / Tab commits the current input. Addresses are freeform text so
 * the server can validate against Gmail's rules (we don't block typos here).
 */
function RecipientField({
  label,
  values,
  onChange,
  placeholder,
}: {
  label: string;
  values: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}) {
  const [input, setInput] = React.useState('');

  function commit() {
    const trimmed = input.trim().replace(/,$/, '');
    if (!trimmed) return;
    if (values.includes(trimmed)) {
      setInput('');
      return;
    }
    onChange([...values, trimmed]);
    setInput('');
  }

  function handleKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' || e.key === ',' || e.key === 'Tab') {
      if (input.trim()) {
        e.preventDefault();
        commit();
      }
    } else if (e.key === 'Backspace' && !input && values.length > 0) {
      e.preventDefault();
      onChange(values.slice(0, -1));
    }
  }

  return (
    <div className="flex items-start gap-2 border-b border-gray-200 px-3 py-2 dark:border-gray-800">
      <label className="w-14 shrink-0 pt-1 text-xs font-medium text-gray-500 dark:text-gray-400">
        {label}
      </label>
      <div className="flex flex-1 flex-wrap items-center gap-1.5">
        {values.map((v) => (
          <span
            key={v}
            className={cn(
              'inline-flex items-center gap-1 rounded-full px-2 py-0.5',
              'bg-primary-50 text-xs text-primary-700',
              'dark:bg-primary-900/30 dark:text-primary-300'
            )}
          >
            {v}
            <button
              type="button"
              onClick={() => onChange(values.filter((x) => x !== v))}
              className="text-primary-500 hover:text-red-500"
              aria-label={`Remove ${v}`}
            >
              <X size={11} />
            </button>
          </span>
        ))}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          onBlur={commit}
          placeholder={values.length === 0 ? placeholder : ''}
          className={cn(
            'min-w-[120px] flex-1 bg-transparent text-sm outline-none',
            'text-gray-900 placeholder:text-gray-400 dark:text-gray-100'
          )}
        />
      </div>
    </div>
  );
}

export function ComposePanel({ threadId, initial, onClose, onSent }: ComposePanelProps) {
  const [to, setTo] = React.useState<string[]>(initial.to);
  const [cc, setCc] = React.useState<string[]>(initial.cc);
  const [bcc, setBcc] = React.useState<string[]>([]);
  const [showCc, setShowCc] = React.useState(initial.cc.length > 0);
  const [showBcc, setShowBcc] = React.useState(false);
  const [subject, setSubject] = React.useState(initial.subject);
  const [body, setBody] = React.useState(initial.body);
  const [error, setError] = React.useState<string | null>(null);

  const { mutate: send, isPending } = useSendReply(threadId);

  function handleSend() {
    setError(null);
    if (to.length === 0) {
      setError('Add at least one recipient.');
      return;
    }
    const payload: SendReplyPayload = {
      mode: initial.mode,
      to,
      cc,
      bcc,
      subject: subject.trim() || '(no subject)',
      bodyText: body,
      inReplyTo: initial.inReplyTo,
      references: initial.references,
    };
    send(payload, {
      onSuccess: () => {
        onSent?.();
        onClose();
      },
      onError: (err: unknown) => {
        const message =
          err instanceof Error ? err.message : 'Failed to send. Try again.';
        setError(message);
      },
    });
  }

  return (
    <div
      className={cn(
        'fixed inset-0 z-40 flex items-end justify-center sm:items-center',
        'bg-black/30 backdrop-blur-sm'
      )}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={MODE_LABEL[initial.mode]}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className={cn(
          'flex w-full max-w-2xl flex-col overflow-hidden',
          'bg-white shadow-2xl dark:bg-gray-900',
          'rounded-t-2xl sm:rounded-2xl',
          'max-h-[90vh] sm:max-h-[80vh]'
        )}
      >
        {/* Header */}
        <div
          className={cn(
            'flex items-center justify-between border-b border-gray-200 px-4 py-3',
            'dark:border-gray-800'
          )}
        >
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            {MODE_LABEL[initial.mode]}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className={cn(
              'rounded-md p-1 text-gray-400 transition-colors',
              'hover:bg-gray-100 hover:text-gray-700',
              'dark:hover:bg-gray-800 dark:hover:text-gray-200'
            )}
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* Recipients + subject */}
        <div className="flex flex-col">
          <RecipientField
            label="To"
            values={to}
            onChange={setTo}
            placeholder="Add recipients (comma-separated)"
          />
          {showCc && (
            <RecipientField label="Cc" values={cc} onChange={setCc} placeholder="Cc" />
          )}
          {showBcc && (
            <RecipientField label="Bcc" values={bcc} onChange={setBcc} placeholder="Bcc" />
          )}
          {(!showCc || !showBcc) && (
            <div className="flex gap-3 border-b border-gray-200 px-3 py-1 text-xs dark:border-gray-800">
              {!showCc && (
                <button
                  type="button"
                  onClick={() => setShowCc(true)}
                  className="text-primary-600 hover:underline dark:text-primary-400"
                >
                  + Cc
                </button>
              )}
              {!showBcc && (
                <button
                  type="button"
                  onClick={() => setShowBcc(true)}
                  className="text-primary-600 hover:underline dark:text-primary-400"
                >
                  + Bcc
                </button>
              )}
            </div>
          )}

          {/* Subject */}
          <div className="flex items-center gap-2 border-b border-gray-200 px-3 py-2 dark:border-gray-800">
            <label className="w-14 shrink-0 text-xs font-medium text-gray-500 dark:text-gray-400">
              Subject
            </label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Subject"
              className={cn(
                'flex-1 bg-transparent text-sm outline-none',
                'text-gray-900 placeholder:text-gray-400 dark:text-gray-100'
              )}
            />
          </div>
        </div>

        {/* Body */}
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Write your message…"
          className={cn(
            'min-h-[240px] flex-1 resize-none bg-transparent px-4 py-3 text-sm outline-none',
            'text-gray-900 placeholder:text-gray-400 dark:text-gray-100'
          )}
        />

        {/* Footer */}
        <div
          className={cn(
            'flex items-center justify-between gap-3 border-t border-gray-200 px-4 py-3',
            'dark:border-gray-800'
          )}
        >
          <div className="min-w-0 flex-1 text-xs text-red-500 truncate">
            {error ?? ''}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={onClose} disabled={isPending}>
              Discard
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSend}
              disabled={isPending || to.length === 0}
            >
              {isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Send size={14} />
              )}
              Send
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
