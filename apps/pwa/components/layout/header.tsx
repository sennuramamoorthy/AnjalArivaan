'use client';

import * as React from 'react';
import { Menu, Bell, Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUIStore } from '@/store/ui-store';
import { AccountSwitcher } from './account-switcher';

// Demo urgent count — in production this would come from a query
const URGENT_COUNT = 2;

export function Header() {
  const { toggleSidebar, setMobileNavOpen } = useUIStore();
  const [searchOpen, setSearchOpen] = React.useState(false);
  const searchRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (searchOpen) {
      searchRef.current?.focus();
    }
  }, [searchOpen]);

  return (
    <header
      className={cn(
        'sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-gray-200',
        'bg-white/95 px-4 backdrop-blur-sm',
        'dark:border-gray-800 dark:bg-gray-950/95'
      )}
    >
      {/* Mobile menu toggle */}
      <button
        onClick={() => setMobileNavOpen(true)}
        className={cn(
          'lg:hidden flex h-9 w-9 items-center justify-center rounded-lg',
          'text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500',
          'transition-colors'
        )}
        aria-label="Open menu"
      >
        <Menu size={20} />
      </button>

      {/* Desktop sidebar toggle */}
      <button
        onClick={toggleSidebar}
        className={cn(
          'hidden lg:flex h-9 w-9 items-center justify-center rounded-lg',
          'text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500',
          'transition-colors'
        )}
        aria-label="Toggle sidebar"
      >
        <Menu size={20} />
      </button>

      {/* Search — full width on mobile when open */}
      <div
        className={cn(
          'flex-1 transition-all',
          searchOpen ? 'flex' : 'hidden sm:flex'
        )}
      >
        <div className="relative w-full max-w-md">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
          />
          <input
            ref={searchRef}
            type="search"
            placeholder="Search emails, meetings..."
            className={cn(
              'w-full rounded-lg border border-gray-200 bg-gray-50 py-2 pl-9 pr-4 text-sm',
              'placeholder:text-gray-400 text-gray-900',
              'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent focus:bg-white',
              'dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 dark:focus:bg-gray-900',
              'transition-colors'
            )}
          />
          {searchOpen && (
            <button
              onClick={() => setSearchOpen(false)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 sm:hidden"
              aria-label="Close search"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Mobile search toggle */}
      {!searchOpen && (
        <button
          onClick={() => setSearchOpen(true)}
          className={cn(
            'sm:hidden flex h-9 w-9 items-center justify-center rounded-lg',
            'text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500'
          )}
          aria-label="Open search"
        >
          <Search size={20} />
        </button>
      )}

      <div className="flex items-center gap-1 ml-auto">
        {/* Notification bell */}
        <button
          className={cn(
            'relative flex h-9 w-9 items-center justify-center rounded-lg',
            'text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500',
            'transition-colors'
          )}
          aria-label={`${URGENT_COUNT} notifications`}
        >
          <Bell size={20} />
          {URGENT_COUNT > 0 && (
            <span
              className={cn(
                'absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center',
                'rounded-full bg-red-500 text-[9px] font-bold text-white'
              )}
              aria-hidden
            >
              {URGENT_COUNT}
            </span>
          )}
        </button>

        {/* Account switcher */}
        <AccountSwitcher />
      </div>
    </header>
  );
}
