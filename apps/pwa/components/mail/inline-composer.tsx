'use client';

import * as React from 'react';
import { X, Send, Loader2, Sparkles, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useSendReply, useRequestAiDraft } from '@/lib/hooks/use-mail';
import { useDefaultSignature } from '@/lib/hooks/use-auth';
import { useAuthStore } from '@/store/auth-store';
import type { ComposeMode, SendReplyPayload } from '@/lib/api/mail';

export interface InlineComposerInitial {
  mode: ComposeMode;
  to: string[];
  cc: string[];
  subject: string;
  body: string;
  inReplyTo?: string;
  references?: string[];
}

interface InlineComposerProps {
  threadId: string;
  initial: InlineComposerInitial;
  onClose: () => void;
  onSent?: () => void;
}

const MODE_LABEL: Record<ComposeMode, string> = {
  reply: 'Reply',
  replyAll: 'Reply all',
  forward: 'Forward',
  compose: 'New Message',
};

/**
 * Chip-style recipient editor.
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
              'dark:bg-primary-900/30 dark:text-primary-300',
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
            'text-gray-900 placeholder:text-gray-400 dark:text-gray-100',
          )}
        />
      </div>
    </div>
  );
}

/**
 * Inline composer — rendered below the email thread in the same right pane.
 * Supports Reply / Reply All / Forward, with an AI Draft action that accepts
 * optional user instructions to steer the generation.
 */
export function InlineComposer({ threadId, initial, onClose, onSent }: InlineComposerProps) {
  const [to, setTo] = React.useState<string[]>(initial.to);
  const [cc, setCc] = React.useState<string[]>(initial.cc);
  const [bcc, setBcc] = React.useState<string[]>([]);
  const [showCc, setShowCc] = React.useState(initial.cc.length > 0);
  const [showBcc, setShowBcc] = React.useState(false);
  const [subject, setSubject] = React.useState(initial.subject);
  const [body, setBody] = React.useState(initial.body);
  const [error, setError] = React.useState<string | null>(null);

  // AI Draft context toggle + instructions
  const [aiOpen, setAiOpen] = React.useState(false);
  const [instructions, setInstructions] = React.useState('');

  // Signature — auto-appended server-side, shown as preview here
  const { activeAccountId } = useAuthStore();
  const defaultSignature = useDefaultSignature(activeAccountId ?? undefined);

  const { mutate: send, isPending } = useSendReply(threadId);
  const { mutate: requestDraft, isPending: draftLoading } = useRequestAiDraft(threadId);

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
        const message = err instanceof Error ? err.message : 'Failed to send. Try again.';
        setError(message);
      },
    });
  }

  function handleAiDraft() {
    setError(null);
    const draftArgs = threadId === 'new'
      ? { instructions: instructions.trim() || undefined, subject, to: to.join(', ') }
      : (instructions.trim() || undefined);
    requestDraft(draftArgs, {
      onSuccess: (draft) => {
        // Prefill the composer body. Preserve any user text as a suffix so
        // they don't silently lose typed content.
        setBody((prev) => {
          const base = draft.draftText ?? '';
          if (!prev.trim()) return base;
          return `${base}\n\n---\n${prev}`;
        });
      },
      onError: (err: unknown) => {
        const message =
          err instanceof Error ? err.message : 'AI draft failed. Try again.';
        setError(message);
      },
    });
  }

  return (
    <section
      className={cn(
        'mt-4 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm',
        'dark:border-gray-700 dark:bg-gray-900',
      )}
      aria-label={MODE_LABEL[initial.mode]}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-800">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
          {MODE_LABEL[initial.mode]}
        </h2>
        <button
          type="button"
          onClick={onClose}
          className={cn(
            'rounded-md p-1 text-gray-400 transition-colors',
            'hover:bg-gray-100 hover:text-gray-700',
            'dark:hover:bg-gray-800 dark:hover:text-gray-200',
          )}
          aria-label="Close composer"
        >
          <X size={16} />
        </button>
      </div>

      {/* Recipients + subject */}
      <RecipientField
        label="To"
        values={to}
        onChange={setTo}
        placeholder="Add recipients (comma-separated)"
      />
      {showCc && <RecipientField label="Cc" values={cc} onChange={setCc} placeholder="Cc" />}
      {showBcc && <RecipientField label="Bcc" values={bcc} onChange={setBcc} placeholder="Bcc" />}
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
            'text-gray-900 placeholder:text-gray-400 dark:text-gray-100',
          )}
        />
      </div>

      {/* AI Draft strip */}
      <div className="border-b border-gray-200 bg-primary-50/40 dark:border-gray-800 dark:bg-primary-950/20">
        <button
          type="button"
          onClick={() => setAiOpen((v) => !v)}
          className={cn(
            'flex w-full items-center justify-between px-3 py-2 text-xs font-medium',
            'text-primary-700 hover:bg-primary-100/50',
            'dark:text-primary-300 dark:hover:bg-primary-900/20',
          )}
        >
          <span className="flex items-center gap-2">
            <Sparkles size={13} />
            AI Draft
            <span className="text-[10px] font-normal text-gray-500 dark:text-gray-400">
              {aiOpen ? 'Add optional context, then generate' : 'Generate a reply with AI'}
            </span>
          </span>
          {aiOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>

        {aiOpen && (
          <div className="space-y-2 px-3 pb-3">
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={2}
              placeholder="Optional context — e.g. 'Decline politely, cite calendar conflict on Friday' or 'Accept and ask for agenda'"
              className={cn(
                'w-full resize-none rounded-md border border-primary-200 bg-white px-3 py-2 text-xs',
                'text-gray-800 placeholder:text-gray-400',
                'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
                'dark:border-primary-900/50 dark:bg-gray-900 dark:text-gray-200',
              )}
              aria-label="AI draft instructions"
            />
            <div className="flex justify-end">
              <Button
                size="sm"
                onClick={handleAiDraft}
                isLoading={draftLoading}
                disabled={draftLoading}
              >
                <Sparkles size={13} />
                {body.trim() ? 'Regenerate Draft' : 'Generate Draft'}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Body */}
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Write your message…"
        rows={10}
        className={cn(
          'min-h-[200px] w-full resize-y bg-transparent px-4 py-3 text-sm outline-none',
          'text-gray-900 placeholder:text-gray-400 dark:text-gray-100',
        )}
      />

      {/* Signature preview — appended server-side on send */}
      {defaultSignature && (
        <div className="border-t border-dashed border-gray-200 px-4 py-3 dark:border-gray-800">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
            Signature
          </p>
          <pre className="whitespace-pre-wrap text-xs leading-relaxed text-gray-500 dark:text-gray-400">
            {defaultSignature.htmlTemplate}
          </pre>
        </div>
      )}

      {/* Footer */}
      <div
        className={cn(
          'flex items-center justify-between gap-3 border-t border-gray-200 px-4 py-3',
          'dark:border-gray-800',
        )}
      >
        <div className="min-w-0 flex-1 truncate text-xs text-red-500">{error ?? ''}</div>
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
            {isPending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            Send
          </Button>
        </div>
      </div>
    </section>
  );
}
