'use client';

import * as React from 'react';
import { Plus, Unlink, Loader2, CheckCircle2, AlertTriangle, XCircle, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Avatar } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useLinkedAccounts,
  useInitiateLink,
  useRevokeAccount,
  useSyncAccount,
} from '@/lib/hooks/use-account-link';
import type { LinkedAccountDetail } from '@/lib/api/auth';

const STATUS_CONFIG: Record<string, { label: string; variant: 'success' | 'warning' | 'urgent'; icon: React.ElementType }> = {
  ACTIVE: { label: 'Active', variant: 'success', icon: CheckCircle2 },
  SYNC_ERROR: { label: 'Sync Error', variant: 'warning', icon: AlertTriangle },
  REVOKED: { label: 'Revoked', variant: 'urgent', icon: XCircle },
};

function AccountRow({
  account,
  onRevoke,
  isRevoking,
  onSync,
  isSyncing,
}: {
  account: LinkedAccountDetail;
  onRevoke: (id: string) => void;
  isRevoking: boolean;
  onSync: (id: string) => void;
  isSyncing: boolean;
}) {
  const [confirmUnlink, setConfirmUnlink] = React.useState(false);
  const config = STATUS_CONFIG[account.status] ?? STATUS_CONFIG.ACTIVE;
  const StatusIcon = config.icon;

  const handleRevoke = () => {
    if (!confirmUnlink) {
      setConfirmUnlink(true);
      return;
    }
    onRevoke(account.id);
    setConfirmUnlink(false);
  };

  return (
    <div className="flex items-center gap-3 rounded-lg border border-gray-200 p-3 dark:border-gray-700">
      <Avatar
        name={account.displayName ?? account.googleEmail}
        size="md"
        className="shrink-0"
      />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
            {account.googleEmail}
          </span>
          <Badge variant={config.variant} className="shrink-0 text-[10px]">
            <StatusIcon size={10} className="mr-0.5" />
            {config.label}
          </Badge>
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
          <span>{account.workspaceDomain}</span>
          {account.lastSyncAt && (
            <>
              <span className="text-gray-300 dark:text-gray-600">|</span>
              <span>
                Last synced {new Date(account.lastSyncAt).toLocaleDateString('en-IN', {
                  day: 'numeric',
                  month: 'short',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </>
          )}
        </div>
      </div>

      {account.status === 'ACTIVE' && (
        <div className="shrink-0 flex items-center gap-1">
          {!confirmUnlink && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSync(account.id)}
              disabled={isSyncing}
              className="text-gray-500 hover:text-primary-600"
              title="Sync account"
            >
              {isSyncing ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <RefreshCw size={14} />
              )}
              Sync
            </Button>
          )}
          {confirmUnlink ? (
            <div className="flex items-center gap-1.5">
              <Button
                variant="destructive"
                size="sm"
                onClick={handleRevoke}
                disabled={isRevoking}
              >
                {isRevoking ? <Loader2 size={12} className="animate-spin" /> : <Unlink size={12} />}
                Confirm
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setConfirmUnlink(false)}
              >
                Cancel
              </Button>
            </div>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRevoke}
              className="text-gray-400 hover:text-red-500"
            >
              <Unlink size={14} />
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function AccountsSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2].map((i) => (
        <div key={i} className="flex items-center gap-3 rounded-lg border border-gray-200 p-3 dark:border-gray-700">
          <Skeleton className="h-9 w-9 rounded-full shrink-0" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-48" />
            <Skeleton className="h-3 w-32" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function LinkedAccountsCard() {
  const { data: accounts, isLoading, isError, error } = useLinkedAccounts();
  const { mutate: initiateLink, isPending: isLinking } = useInitiateLink();
  const { mutate: revokeAccount, isPending: isRevoking } = useRevokeAccount();
  const { mutate: syncAccount, isPending: isSyncing, variables: syncingId } = useSyncAccount();

  // Treat empty data or error as "no accounts linked" — show the empty CTA
  const hasNoAccounts = !accounts || accounts.length === 0;

  return (
    <section
      className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-900"
      aria-labelledby="linked-accounts-heading"
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2
            id="linked-accounts-heading"
            className="text-sm font-semibold text-gray-900 dark:text-gray-100"
          >
            Linked Google Accounts
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Connect your Google Workspace accounts for mail sync
          </p>
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={() => initiateLink()}
          disabled={isLinking}
        >
          {isLinking ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Plus size={14} />
          )}
          Link Account
        </Button>
      </div>

      {isLoading ? (
        <AccountsSkeleton />
      ) : isError || hasNoAccounts ? (
        <div className="rounded-lg border border-dashed border-gray-200 py-8 text-center dark:border-gray-700">
          <div className="flex justify-center mb-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-100 dark:bg-gray-800">
              <Plus size={20} className="text-gray-400" />
            </div>
          </div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
            No accounts linked yet
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Link a Google Workspace account to start syncing emails
          </p>
          <Button
            variant="primary"
            size="sm"
            className="mt-4"
            onClick={() => initiateLink()}
            disabled={isLinking}
          >
            {isLinking ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            Link Your First Account
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          {accounts.map((account) => (
            <AccountRow
              key={account.id}
              account={account}
              onRevoke={(id) => revokeAccount(id)}
              isRevoking={isRevoking}
              onSync={(id) => syncAccount(id)}
              isSyncing={isSyncing && syncingId === account.id}
            />
          ))}
        </div>
      )}
    </section>
  );
}
