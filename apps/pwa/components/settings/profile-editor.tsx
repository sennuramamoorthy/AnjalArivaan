'use client';

import * as React from 'react';
import { Pencil, Save, X, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Avatar } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { useAuthStore } from '@/store/auth-store';
import { useProfile, useUpdateProfile } from '@/lib/hooks/use-auth';
import { useQueryClient } from '@tanstack/react-query';

/**
 * Editable profile section — displays name, email, role (read-only) plus
 * editable designation, department, and responsibilities.
 */
export function ProfileEditor() {
  const { user, setUser } = useAuthStore();
  const queryClient = useQueryClient();
  const { data: profile } = useProfile();
  const { mutateAsync: updateProfile } = useUpdateProfile();

  const [editing, setEditing] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [success, setSuccess] = React.useState(false);

  // Editable field state — seeded from profile query
  const [designation, setDesignation] = React.useState('');
  const [department, setDepartment] = React.useState('');
  const [responsibilities, setResponsibilities] = React.useState('');

  // Sync from profile query when it loads
  React.useEffect(() => {
    if (profile) {
      setDesignation(profile.designation ?? '');
      setDepartment(profile.department ?? '');
      setResponsibilities(profile.responsibilities ?? '');
    }
  }, [profile]);

  async function handleSave() {
    setError(null);
    setSuccess(false);
    setSaving(true);
    try {
      const updated = await updateProfile({
        designation: designation.trim() || undefined,
        department: department.trim() || undefined,
        responsibilities: responsibilities.trim() || undefined,
      });
      // Sync name back to store if needed
      if (user) {
        setUser({
          ...user,
          name: updated.name ?? user.name,
        });
      }
      queryClient.invalidateQueries({ queryKey: ['profile'] });
      setSuccess(true);
      setEditing(false);
      setTimeout(() => setSuccess(false), 3000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  }

  if (!user) return null;

  return (
    <section
      className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-900"
      aria-labelledby="profile-heading"
    >
      <div className="mb-4 flex items-center justify-between">
        <h2
          id="profile-heading"
          className="text-sm font-semibold text-gray-900 dark:text-gray-100"
        >
          Profile
        </h2>
        {!editing ? (
          <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
            <Pencil size={13} />
            Edit
          </Button>
        ) : (
          <div className="flex items-center gap-1.5">
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)} disabled={saving}>
              <X size={13} />
              Cancel
            </Button>
            <Button size="sm" onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
              Save
            </Button>
          </div>
        )}
      </div>

      {error && (
        <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600 dark:border-red-900 dark:bg-red-950/30 dark:text-red-400">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-600 dark:border-green-900 dark:bg-green-950/30 dark:text-green-400">
          Profile updated successfully
        </div>
      )}

      <div className="flex items-start gap-4">
        <Avatar src={user.avatarUrl} name={user.name} size="lg" className="shrink-0" />

        <div className="min-w-0 flex-1 space-y-3">
          {/* Read-only fields */}
          <Field label="Name" value={user.name} />
          <Field label="Email" value={user.email} />
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              Role
            </label>
            <div className="mt-0.5">
              <Badge variant="default">{user.role}</Badge>
            </div>
          </div>

          {/* Editable fields */}
          <EditableField
            label="Designation"
            value={designation}
            onChange={setDesignation}
            editing={editing}
            placeholder="e.g. Vice-Chancellor, Dean of Sciences"
          />
          <EditableField
            label="Department"
            value={department}
            onChange={setDepartment}
            editing={editing}
            placeholder="e.g. Office of the Vice-Chancellor"
          />
          <EditableField
            label="Roles & Responsibilities"
            value={responsibilities}
            onChange={setResponsibilities}
            editing={editing}
            multiline
            placeholder="Describe your key responsibilities. This helps the AI assistant provide more relevant summaries and draft replies."
          />
        </div>
      </div>
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
        {label}
      </label>
      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{value}</p>
    </div>
  );
}

function EditableField({
  label,
  value,
  onChange,
  editing,
  multiline = false,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  editing: boolean;
  multiline?: boolean;
  placeholder?: string;
}) {
  const inputClasses = cn(
    'w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm',
    'text-gray-900 placeholder:text-gray-400',
    'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
    'dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100',
  );

  return (
    <div>
      <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
        {label}
      </label>
      {editing ? (
        multiline ? (
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            rows={3}
            placeholder={placeholder}
            className={cn(inputClasses, 'resize-y')}
          />
        ) : (
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            className={inputClasses}
          />
        )
      ) : (
        <p className="text-sm text-gray-700 dark:text-gray-300">
          {value || <span className="italic text-gray-400">Not set</span>}
        </p>
      )}
    </div>
  );
}
