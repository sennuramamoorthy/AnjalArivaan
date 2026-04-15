'use client';

import * as React from 'react';
import { X, Sparkles, LayoutDashboard, Mail, CalendarDays, CheckSquare, Settings } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { useUIStore } from '@/store/ui-store';
import { useAuthStore } from '@/store/auth-store';
import { Sidebar } from './sidebar';
import { BottomNav } from './bottom-nav';
import { Header } from './header';
import { Avatar } from '@/components/ui/avatar';

const mobileNavItems = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Mail', href: '/mail', icon: Mail },
  { label: 'Meetings', href: '/meetings', icon: CalendarDays, comingSoon: true },
  { label: 'Tasks', href: '/tasks', icon: CheckSquare, comingSoon: true },
  { label: 'Settings', href: '/settings', icon: Settings },
];

function MobileDrawer() {
  const pathname = usePathname();
  const { mobileNavOpen, setMobileNavOpen } = useUIStore();
  const { user } = useAuthStore();

  return (
    <AnimatePresence>
      {mobileNavOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 bg-black/50 lg:hidden"
            onClick={() => setMobileNavOpen(false)}
            aria-hidden
          />

          {/* Drawer */}
          <motion.div
            key="drawer"
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ type: 'tween', duration: 0.25, ease: 'easeOut' }}
            className={cn(
              'fixed inset-y-0 left-0 z-50 w-72 lg:hidden',
              'flex flex-col border-r border-gray-200 bg-white',
              'dark:border-gray-800 dark:bg-gray-950'
            )}
          >
            {/* Header */}
            <div className="flex h-14 items-center justify-between border-b border-gray-200 px-4 dark:border-gray-800">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600">
                  <Sparkles size={16} className="text-white" />
                </div>
                <div>
                  <p className="text-sm font-bold text-gray-900 dark:text-gray-100">AnjalArivaan</p>
                  <p className="text-[10px] text-gray-400">Takshashila University</p>
                </div>
              </div>
              <button
                onClick={() => setMobileNavOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                aria-label="Close menu"
              >
                <X size={18} />
              </button>
            </div>

            {/* Nav */}
            <nav className="flex-1 overflow-y-auto p-3">
              <ul className="space-y-0.5">
                {mobileNavItems.map((item) => {
                  const isActive = pathname.startsWith(item.href);
                  const Icon = item.icon;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.comingSoon ? '#' : item.href}
                        onClick={() => !item.comingSoon && setMobileNavOpen(false)}
                        className={cn(
                          'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                          isActive
                            ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400'
                            : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
                          item.comingSoon && 'opacity-50 cursor-default'
                        )}
                      >
                        <Icon size={18} />
                        <span>{item.label}</span>
                        {item.comingSoon && (
                          <span className="ml-auto text-[10px] font-normal text-gray-400">Soon</span>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </nav>

            {/* User */}
            {user && (
              <div className="border-t border-gray-200 p-4 dark:border-gray-800">
                <div className="flex items-center gap-3">
                  <Avatar src={user.avatarUrl} name={user.name} size="md" />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">{user.name}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{user.role}</p>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-gray-950">
      {/* Desktop sidebar */}
      <Sidebar />

      {/* Mobile drawer */}
      <MobileDrawer />

      {/* Main content */}
      <div className="flex flex-1 flex-col min-w-0">
        <Header />
        <main
          className="flex-1 overflow-y-auto pb-16 lg:pb-0"
          id="main-content"
        >
          {children}
        </main>
      </div>

      {/* Mobile bottom nav */}
      <BottomNav />
    </div>
  );
}
