'use client';

import * as React from 'react';
import { Shield, Bell } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { ProfileEditor } from '@/components/settings/profile-editor';
import { SignatureEditor } from '@/components/settings/signature-editor';
import { LinkedAccountsCard } from '@/components/settings/linked-accounts-card';

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
          Manage your profile, signatures, accounts, and preferences
        </p>
      </div>

      <div className="space-y-6">
        <ProfileEditor />
        <SignatureEditor />
        <LinkedAccountsCard />
        <SecuritySection />
      </div>
    </div>
  );
}
