'use client';

import * as React from 'react';
import { Plus, Save, Trash2, X, Loader2, Star, FileSignature } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useAuthStore } from '@/store/auth-store';
import {
  useSignatures,
  useCreateSignature,
  useUpdateSignature,
  useDeleteSignature,
} from '@/lib/hooks/use-auth';
import * as authApi from '@/lib/api/auth';
import type { Signature } from '@/lib/api/auth';
import { useQueryClient } from '@tanstack/react-query';

/**
 * Email signature management — CRUD per linked account.
 * Supports multiple signatures per account with one marked as default.
 */
export function SignatureEditor() {
  const { linkedAccounts, activeAccountId } = useAuthStore();
  const queryClient = useQueryClient();

  const accountId = activeAccountId ?? linkedAccounts[0]?.id;
  const activeAccount = linkedAccounts.find((a) => a.id === accountId);

  const { data: signatures = [], isLoading: loading } = useSignatures(accountId);
  const { mutateAsync: createSig } = useCreateSignature();
  const { mutateAsync: updateSig } = useUpdateSignature();
  const { mutateAsync: deleteSig } = useDeleteSignature();

  const [error, setError] = React.useState<string | null>(null);
  const [editId, setEditId] = React.useState<string | null>(null);

  // New signature form state
  const [showNew, setShowNew] = React.useState(false);
  const [newName, setNewName] = React.useState('');
  const [newHtml, setNewHtml] = React.useState('');
  const [newDefault, setNewDefault] = React.useState(false);
  const [saving, setSaving] = React.useState(false);

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['signatures', accountId] });
  }

  async function handleCreate() {
    if (!accountId || !newName.trim() || !newHtml.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await createSig({
        accountId,
        name: newName.trim(),
        htmlTemplate: newHtml.trim(),
        isDefault: newDefault,
      });
      invalidate();
      setShowNew(false);
      setNewName('');
      setNewHtml('');
      setNewDefault(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create signature');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(sigId: string) {
    setError(null);
    try {
      await deleteSig(sigId);
      invalidate();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to delete');
    }
  }

  async function handleSetDefault(sigId: string) {
    setError(null);
    try {
      await updateSig({ sigId, data: { isDefault: true } });
      invalidate();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to update');
    }
  }

  return (
    <section
      className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-900"
      aria-labelledby="signature-heading"
    >
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-100 dark:bg-amber-900/30">
            <FileSignature size={14} className="text-amber-600 dark:text-amber-400" />
          </div>
          <div>
            <h2
              id="signature-heading"
              className="text-sm font-semibold text-gray-900 dark:text-gray-100"
            >
              Email Signatures
            </h2>
            {activeAccount && (
              <p className="text-[10px] text-gray-400">{activeAccount.googleEmail}</p>
            )}
          </div>
        </div>
        {!showNew && (
          <Button variant="ghost" size="sm" onClick={() => setShowNew(true)}>
            <Plus size={13} />
            New Signature
          </Button>
        )}
      </div>

      {error && (
        <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600 dark:border-red-900 dark:bg-red-950/30 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Existing signatures */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-20 animate-pulse rounded-lg border border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800"
            />
          ))}
        </div>
      ) : signatures.length === 0 && !showNew ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6 text-center dark:border-gray-700 dark:bg-gray-800/50">
          <FileSignature size={24} className="mx-auto mb-2 text-gray-400" />
          <p className="text-sm text-gray-500 dark:text-gray-400">No signatures yet</p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Create a signature to automatically append to your emails
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {signatures.map((sig) => (
            <SignatureCard
              key={sig.id}
              signature={sig}
              isEditing={editId === sig.id}
              onEdit={() => setEditId(editId === sig.id ? null : sig.id)}
              onDelete={() => handleDelete(sig.id)}
              onSetDefault={() => handleSetDefault(sig.id)}
              onSave={async (data) => {
                await updateSig({ sigId: sig.id, data });
                invalidate();
                setEditId(null);
              }}
            />
          ))}
        </div>
      )}

      {/* New signature form */}
      {showNew && (
        <div className="mt-3 rounded-lg border border-primary-200 bg-primary-50/30 p-4 dark:border-primary-900/50 dark:bg-primary-950/10">
          <h3 className="mb-3 text-xs font-semibold text-gray-700 dark:text-gray-300">
            New Signature
          </h3>
          <div className="space-y-3">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Signature name (e.g. 'Formal', 'Internal')"
              className={cn(
                'w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm',
                'text-gray-900 placeholder:text-gray-400',
                'focus:outline-none focus:ring-2 focus:ring-primary-500',
                'dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100',
              )}
            />
            <textarea
              value={newHtml}
              onChange={(e) => setNewHtml(e.target.value)}
              rows={5}
              placeholder={'Warm regards,\nDr. Priya Sharma\nVice-Chancellor, Takshashila University\n+91 44 2815 xxxx'}
              className={cn(
                'w-full resize-y rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-mono',
                'text-gray-900 placeholder:text-gray-400',
                'focus:outline-none focus:ring-2 focus:ring-primary-500',
                'dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100',
              )}
            />
            <label className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
              <input
                type="checkbox"
                checked={newDefault}
                onChange={(e) => setNewDefault(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-gray-300"
              />
              Set as default signature
            </label>
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setShowNew(false);
                setNewName('');
                setNewHtml('');
                setNewDefault(false);
              }}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleCreate}
              disabled={saving || !newName.trim() || !newHtml.trim()}
            >
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
              Create
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}

function SignatureCard({
  signature,
  isEditing,
  onEdit,
  onDelete,
  onSetDefault,
  onSave,
}: {
  signature: Signature;
  isEditing: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onSetDefault: () => void;
  onSave: (data: authApi.UpdateSignaturePayload) => Promise<void>;
}) {
  const [name, setName] = React.useState(signature.name);
  const [html, setHtml] = React.useState(signature.htmlTemplate);
  const [saving, setSaving] = React.useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await onSave({ name: name.trim(), htmlTemplate: html.trim() });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className={cn(
        'rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800',
        signature.isDefault && 'border-amber-300 bg-amber-50/30 dark:border-amber-800 dark:bg-amber-950/10',
      )}
    >
      {isEditing ? (
        <div className="space-y-2">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={cn(
              'w-full rounded border border-gray-200 bg-white px-2 py-1.5 text-sm',
              'dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100',
              'focus:outline-none focus:ring-2 focus:ring-primary-500',
            )}
          />
          <textarea
            value={html}
            onChange={(e) => setHtml(e.target.value)}
            rows={4}
            className={cn(
              'w-full resize-y rounded border border-gray-200 bg-white px-2 py-1.5 text-sm font-mono',
              'dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100',
              'focus:outline-none focus:ring-2 focus:ring-primary-500',
            )}
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={onEdit} disabled={saving}>
              <X size={12} /> Cancel
            </Button>
            <Button size="sm" onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
              Save
            </Button>
          </div>
        </div>
      ) : (
        <div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                {signature.name}
              </p>
              {signature.isDefault && (
                <Badge variant="warning" className="text-[10px]">Default</Badge>
              )}
            </div>
            <div className="flex items-center gap-1">
              {!signature.isDefault && (
                <button
                  type="button"
                  onClick={onSetDefault}
                  className="rounded p-1 text-gray-400 transition-colors hover:bg-amber-100 hover:text-amber-600 dark:hover:bg-amber-900/30"
                  aria-label="Set as default"
                  title="Set as default"
                >
                  <Star size={13} />
                </button>
              )}
              <button
                type="button"
                onClick={onEdit}
                className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-200 hover:text-gray-700 dark:hover:bg-gray-700"
                aria-label="Edit"
              >
                <Plus size={13} className="rotate-45" />
              </button>
              <button
                type="button"
                onClick={onDelete}
                className="rounded p-1 text-gray-400 transition-colors hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900/30"
                aria-label="Delete"
              >
                <Trash2 size={13} />
              </button>
            </div>
          </div>
          <pre className="mt-2 whitespace-pre-wrap text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
            {signature.htmlTemplate}
          </pre>
        </div>
      )}
    </div>
  );
}
