'use client';

import * as React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Mail,
  CalendarDays,
  CheckSquare,
  Settings,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUIStore } from '@/store/ui-store';
import { useAuthStore } from '@/store/auth-store';
import { Avatar } from '@/components/ui/avatar';
import { Tooltip } from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';

const URGENT_MAIL_COUNT = 2;

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  badge?: number | string;
  badgeVariant?: 'urgent' | 'default' | 'warning';
  comingSoon?: boolean;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  {
    label: 'Mail',
    href: '/mail',
    icon: Mail,
    badge: URGENT_MAIL_COUNT,
    badgeVariant: 'urgent',
  },
  {
    label: 'Meetings',
    href: '/meetings',
    icon: CalendarDays,
    comingSoon: true,
  },
  {
    label: 'Tasks',
    href: '/tasks',
    icon: CheckSquare,
    comingSoon: true,
  },
  { label: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar } = useUIStore();
  const { user } = useAuthStore();

  return (
    <aside
      className={cn(
        'hidden lg:flex flex-col shrink-0 h-screen sticky top-0',
        'border-r border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950',
        'transition-all duration-300 ease-in-out',
        sidebarOpen ? 'w-60' : 'w-16'
      )}
    >
      {/* Logo */}
      <div
        className={cn(
          'flex h-14 items-center border-b border-gray-200 dark:border-gray-800',
          sidebarOpen ? 'px-4 gap-2.5' : 'justify-center px-0'
        )}
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-600">
          <Sparkles size={16} className="text-white" />
        </div>
        {sidebarOpen && (
          <div className="min-w-0">
            <p className="text-sm font-bold text-gray-900 dark:text-gray-100 truncate">
              AnjalArivaan
            </p>
            <p className="text-[10px] text-gray-400 truncate">Takshashila University</p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-2" aria-label="Main navigation">
        <ul className="space-y-0.5">
          {navItems.map((item) => {
            const isActive = pathname.startsWith(item.href);
            const Icon = item.icon;

            const linkContent = (
              <Link
                href={item.comingSoon ? '#' : item.href}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'group flex items-center rounded-lg transition-colors',
                  sidebarOpen ? 'gap-3 px-3 py-2' : 'justify-center p-2.5',
                  isActive
                    ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-100',
                  item.comingSoon && 'cursor-default opacity-60'
                )}
                onClick={item.comingSoon ? (e) => e.preventDefault() : undefined}
              >
                <Icon
                  size={18}
                  className={cn(
                    'shrink-0',
                    isActive
                      ? 'text-primary-600 dark:text-primary-400'
                      : 'text-gray-500 group-hover:text-gray-700 dark:text-gray-500 dark:group-hover:text-gray-300'
                  )}
                />
                {sidebarOpen && (
                  <>
                    <span className="flex-1 text-sm font-medium truncate">{item.label}</span>
                    {item.badge && !item.comingSoon && (
                      <Badge variant={item.badgeVariant ?? 'default'} className="ml-auto">
                        {item.badge}
                      </Badge>
                    )}
                    {item.comingSoon && (
                      <Badge variant="default" className="ml-auto text-[10px]">
                        Soon
                      </Badge>
                    )}
                  </>
                )}
              </Link>
            );

            return (
              <li key={item.href}>
                {!sidebarOpen ? (
                  <Tooltip content={item.comingSoon ? `${item.label} (Coming Soon)` : item.label} side="right">
                    <div className="relative">
                      {linkContent}
                      {item.badge && !item.comingSoon && (
                        <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white">
                          {item.badge}
                        </span>
                      )}
                    </div>
                  </Tooltip>
                ) : (
                  linkContent
                )}
              </li>
            );
          })}
        </ul>
      </nav>

      {/* User */}
      <div className={cn('border-t border-gray-200 dark:border-gray-800 p-2')}>
        {user ? (
          <div
            className={cn(
              'flex items-center rounded-lg px-2 py-2',
              sidebarOpen ? 'gap-3' : 'justify-center'
            )}
          >
            <Avatar
              src={user.avatarUrl}
              name={user.name}
              size="sm"
              className="shrink-0"
            />
            {sidebarOpen && (
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                  {user.name}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{user.role}</p>
              </div>
            )}
          </div>
        ) : null}

        {/* Collapse toggle */}
        <button
          onClick={toggleSidebar}
          className={cn(
            'mt-1 flex w-full items-center rounded-lg px-2 py-2 text-xs text-gray-500',
            'hover:bg-gray-100 dark:hover:bg-gray-800',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500',
            'transition-colors',
            sidebarOpen ? 'gap-2' : 'justify-center'
          )}
          aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          {sidebarOpen ? (
            <>
              <ChevronLeft size={14} />
              <span>Collapse</span>
            </>
          ) : (
            <ChevronRight size={14} />
          )}
        </button>
      </div>
    </aside>
  );
}
