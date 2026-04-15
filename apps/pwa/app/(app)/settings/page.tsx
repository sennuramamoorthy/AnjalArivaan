'use client';

import * as React from 'react';
import { User, Shield, Bell } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/store/auth-store';
import { Avatar } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { LinkedAccountsCard } from '@/components/settings/linked-accounts-card';

function ProfileSection() {
  const { user } = useAuthStore();

  if (!user) return null;

  return (
    <section
      className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-900"
      aria-labelledby="profile-heading"
    >
      <h2
        id="profile-heading"
        className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4"
      >
        Profile
      </h2>

      <div className="flex items-start gap-4">
        <Avatar
          src={user.avatarUrl}
          name={user.name}
          size="lg"
          className="shrink-0"
        />
        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              Name
            </label>
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {user.name}
            </p>
          </div>
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              Email
            </label>
            <p className="text-sm text-gray-700 dark:text-gray-300">
              {user.email}
            </p>
          </div>
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              Role
            </label>
            <div className="mt-0.5">
              <Badge variant="default">{user.role}</Badge>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function SecuritySection() {
  return (
    <section
      className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-900"
      aria-labelledby="security-heading"
    >
      <h2
        id="security-heading"
        className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4"
      >
        Security
      </h2>

      <div className="space-y-3">
        <div className="flex items-center justify-between rounded-lg border border-gray-200 p-3 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-100 dark:bg-green-900/30">
              <Shield size={16} className="text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                Multi-Factor Authentication
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                TOTP-based authentication for enhanced security
              </p>
            </div>
          </div>
          <Badge variant="success">Enabled</Badge>
        </div>

        <div className="flex items-center justify-between rounded-lg border border-gray-200 p-3 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/30">
              <Bell size={16} className="text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                WhatsApp Notifications
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Urgent email alerts via WhatsApp
              </p>
            </div>
          </div>
          <Badge variant="default">Configured</Badge>
        </div>
      </div>
    </section>
  );
}

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-6 sm:px-6">
      <div className="mb-6">
        <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">Settings</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
          Manage your profile, accounts, and preferences
        </p>
      </div>

      <div className="space-y-6">
        <ProfileSection />
        <LinkedAccountsCard />
        <SecuritySection />
      </div>
    </div>
  );
}
