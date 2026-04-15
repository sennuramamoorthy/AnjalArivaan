'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Mail, CalendarDays, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';

const URGENT_MAIL_COUNT = 2;

const navItems = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Mail', href: '/mail', icon: Mail, badge: URGENT_MAIL_COUNT },
  { label: 'Meetings', href: '/meetings', icon: CalendarDays },
  { label: 'Settings', href: '/settings', icon: Settings },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className={cn(
        'fixed bottom-0 inset-x-0 z-40 lg:hidden',
        'flex h-16 items-stretch border-t border-gray-200',
        'bg-white/95 backdrop-blur-sm dark:border-gray-800 dark:bg-gray-950/95'
      )}
      aria-label="Bottom navigation"
    >
      {navItems.map((item) => {
        const isActive = pathname.startsWith(item.href);
        const Icon = item.icon;

        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={isActive ? 'page' : undefined}
            className={cn(
              'relative flex flex-1 flex-col items-center justify-center gap-0.5 py-2',
              'transition-colors',
              isActive
                ? 'text-primary-600 dark:text-primary-400'
                : 'text-gray-500 dark:text-gray-400'
            )}
          >
            <div className="relative">
              <Icon size={22} />
              {item.badge && item.badge > 0 && (
                <span
                  className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white"
                  aria-label={`${item.badge} urgent`}
                >
                  {item.badge}
                </span>
              )}
            </div>
            <span
              className={cn(
                'text-[10px] font-medium',
                isActive ? 'text-primary-600 dark:text-primary-400' : 'text-gray-400 dark:text-gray-500'
              )}
            >
              {item.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
