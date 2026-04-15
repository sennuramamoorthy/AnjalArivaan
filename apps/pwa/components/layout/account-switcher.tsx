'use client';

import * as React from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Check, ChevronDown, Plus, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/store/auth-store';
import { Avatar } from '@/components/ui/avatar';
import { useInitiateLink } from '@/lib/hooks/use-account-link';

export function AccountSwitcher() {
  const { linkedAccounts: allAccounts, activeAccountId, switchAccount } = useAuthStore();
  const { mutate: initiateLink, isPending: isLinking } = useInitiateLink();
  // Defensive: only show accounts that are active. Revoked entries can
  // linger in the persisted store until the next /accounts/linked refetch.
  const linkedAccounts = allAccounts.filter(
    (a: any) => !a.status || a.status === 'ACTIVE',
  );
  const activeAccount = linkedAccounts.find((a) => a.id === activeAccountId) ?? linkedAccounts[0];

  if (!activeAccount) {
    return null;
  }

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          className={cn(
            'flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm',
            'hover:bg-gray-100 dark:hover:bg-gray-800',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500',
            'transition-colors'
          )}
          aria-label="Switch account"
        >
          <Avatar
            src={activeAccount.avatarUrl}
            name={activeAccount.displayName ?? activeAccount.googleEmail}
            size="sm"
          />
          <div className="hidden sm:flex flex-col items-start min-w-0">
            <span className="text-xs font-medium text-gray-900 dark:text-gray-100 truncate max-w-[140px]">
              {activeAccount.displayName ?? activeAccount.googleEmail.split('@')[0]}
            </span>
            <span className="text-[10px] text-gray-500 dark:text-gray-400 truncate max-w-[140px]">
              {activeAccount.googleEmail}
            </span>
          </div>
          <ChevronDown size={14} className="text-gray-400 shrink-0" />
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className={cn(
            'z-50 min-w-[220px] rounded-xl border border-gray-200 bg-white p-1.5 shadow-lg',
            'dark:border-gray-700 dark:bg-gray-900',
            'animate-in fade-in-0 zoom-in-95'
          )}
        >
          <div className="px-2 py-1 mb-1">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
              Linked Accounts
            </p>
          </div>

          {linkedAccounts.map((account) => (
            <DropdownMenu.Item
              key={account.id}
              onSelect={() => switchAccount(account.id)}
              className={cn(
                'flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm cursor-pointer',
                'hover:bg-gray-100 dark:hover:bg-gray-800',
                'focus:outline-none focus:bg-gray-100 dark:focus:bg-gray-800',
                'transition-colors'
              )}
            >
              <Avatar
                src={account.avatarUrl}
                name={account.displayName ?? account.googleEmail}
                size="sm"
              />
              <div className="flex flex-col min-w-0 flex-1">
                <span className="font-medium text-gray-900 dark:text-gray-100 truncate">
                  {account.displayName ?? account.googleEmail.split('@')[0]}
                </span>
                <span className="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {account.googleEmail}
                </span>
              </div>
              {account.id === activeAccountId && (
                <Check size={14} className="text-primary-600 shrink-0" />
              )}
            </DropdownMenu.Item>
          ))}

          <DropdownMenu.Separator className="my-1 h-px bg-gray-200 dark:bg-gray-700" />

          <DropdownMenu.Item
            onSelect={(e) => {
              e.preventDefault();
              initiateLink();
            }}
            disabled={isLinking}
            className={cn(
              'flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm cursor-pointer',
              'text-primary-600 hover:bg-primary-50 dark:text-primary-400 dark:hover:bg-primary-900/20',
              'focus:outline-none focus:bg-primary-50 dark:focus:bg-primary-900/20',
              'transition-colors',
              isLinking && 'opacity-50 cursor-wait'
            )}
          >
            <div className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-dashed border-primary-300 dark:border-primary-700">
              {isLinking ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
            </div>
            <span className="font-medium">{isLinking ? 'Redirecting...' : 'Link another account'}</span>
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
