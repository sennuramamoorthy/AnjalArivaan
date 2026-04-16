'use client';

import * as React from 'react';
import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';
import { ShieldCheck, Users, ScrollText, Activity } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/store/auth-store';

const TABS = [
  { href: '/admin', label: 'Overview', icon: Activity },
  { href: '/admin/users', label: 'Users', icon: Users },
  { href: '/admin/audit-logs', label: 'Audit log', icon: ScrollText },
];

const ADMIN_ROLES = new Set(['SUPER_ADMIN', 'DEPT_ADMIN']);

/**
 * /admin — Super Admin console. The layout enforces a client-side role
 * guard (the API itself also enforces via _require_admin), renders the
 * shared header and tab nav, and keeps the content in the main pane.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  // Redirect non-admins away from the console. We still show a loading
  // shimmer for the split-second while the hydrated user is being read.
  React.useEffect(() => {
    if (user && !ADMIN_ROLES.has(user.role)) {
      router.replace('/dashboard');
    }
  }, [user, router]);

  if (!user) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-500">
        Loading…
      </div>
    );
  }
  if (!ADMIN_ROLES.has(user.role)) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-500">
        Redirecting…
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-gray-200 px-6 pt-5 dark:border-gray-800">
        <div className="flex items-center gap-2">
          <ShieldCheck size={18} className="text-primary-600" />
          <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">
            Super Admin console
          </h1>
        </div>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Manage pilot users, review the audit trail, and check platform health.
        </p>

        {/* Tabs */}
        <nav className="mt-4 flex gap-1" role="tablist">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive =
              pathname === tab.href ||
              (tab.href !== '/admin' && pathname.startsWith(tab.href));
            return (
              <Link
                key={tab.href}
                href={tab.href}
                role="tab"
                aria-selected={isActive}
                className={cn(
                  'flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'border-primary-600 text-primary-700 dark:text-primary-400'
                    : 'border-transparent text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100'
                )}
              >
                <Icon size={14} />
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-6">{children}</div>
    </div>
  );
}
