'use client';

import * as React from 'react';
import Link from 'next/link';
import { usePathname, useSearchParams, useRouter } from 'next/navigation';
import {
  Inbox,
  Star,
  AlertTriangle,
  Send,
  FileText,
  Trash2,
  CheckSquare,
  Plane,
  CalendarDays,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
  Plus,
  Sparkles,
  LayoutDashboard,
  Settings,
  ShieldCheck,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUIStore } from '@/store/ui-store';
import { useAuthStore } from '@/store/auth-store';
import { Avatar } from '@/components/ui/avatar';
import { Tooltip } from '@/components/ui/tooltip';

/**
 * App sidebar — modeled on AnjalArivaan_UI_Themes.html `.sidebar`. Three
 * grouped sections:
 *   • Mailbox  — Inbox / Important / Sent / Drafts / Trash
 *   • AI-Powered — Tasks / Travel / Calendar / AI Chat
 *   • Tags — colored dot labels for quick filtering
 *
 * Items that don't have backend support yet route to /mail with a query
 * filter or are flagged `comingSoon` (visually present, click is a no-op).
 * The collapse toggle hides labels and shows icon-only mode.
 */

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  count?: number;
  /** When set, item is active only when ?folder= matches this value. */
  folder?: string;
  /** When set, item is active only when ?filter= matches this value. */
  filter?: string;
  comingSoon?: boolean;
}

interface TagItem {
  label: string;
  color: string;
  filter: string;
}

// Mailbox folders map to Gmail system labels. The list pane reads
// ?folder= from the URL and queries the backend with the matching label
// (see backend/api/src/modules/mail/repositories — _FOLDER_TO_LABEL).
const MAILBOX_ITEMS: NavItem[] = [
  { label: 'Inbox', href: '/mail?folder=inbox', icon: Inbox, folder: 'inbox' },
  { label: 'Starred', href: '/mail?folder=starred', icon: Star, folder: 'starred' },
  { label: 'Important', href: '/mail?folder=important', icon: AlertTriangle, folder: 'important' },
  { label: 'Sent', href: '/mail?folder=sent', icon: Send, folder: 'sent' },
  { label: 'Drafts', href: '/mail?folder=drafts', icon: FileText, folder: 'drafts' },
  { label: 'Trash', href: '/mail?folder=trash', icon: Trash2, folder: 'trash' },
];

const AI_ITEMS: NavItem[] = [
  { label: 'Tasks', href: '/tasks', icon: CheckSquare, count: 12, comingSoon: true },
  { label: 'Travel', href: '/travel', icon: Plane, count: 2, comingSoon: true },
  { label: 'Calendar', href: '/calendar', icon: CalendarDays, comingSoon: true },
  { label: 'AI Chat', href: '/chat', icon: MessageSquare, comingSoon: true },
];

const TAG_ITEMS: TagItem[] = [
  { label: 'Urgent', color: '#ef4444', filter: 'urgent' },
  { label: 'Admissions', color: '#f59e0b', filter: 'admissions' },
  { label: 'Research', color: '#10b981', filter: 'research' },
  { label: 'IQAC', color: '#8b5cf6', filter: 'iqac' },
];

const TOP_NAV: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Settings', href: '/settings', icon: Settings },
];

const ADMIN_NAV: NavItem = { label: 'Admin', href: '/admin', icon: ShieldCheck };
const ADMIN_ROLES = new Set(['SUPER_ADMIN', 'DEPT_ADMIN']);

interface SidebarItemProps {
  item: NavItem;
  isActive: boolean;
  collapsed: boolean;
}

function SidebarItem({ item, isActive, collapsed }: SidebarItemProps) {
  const Icon = item.icon;
  const content = (
    <Link
      href={item.comingSoon ? '#' : item.href}
      onClick={item.comingSoon ? (e) => e.preventDefault() : undefined}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        'group flex items-center rounded-lg text-sm transition-colors',
        collapsed ? 'justify-center p-2.5' : 'gap-3 px-3 py-2',
        isActive
          ? 'bg-primary-50 font-semibold text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-100',
        item.comingSoon && 'cursor-default opacity-60'
      )}
    >
      <Icon
        size={16}
        className={cn(
          'shrink-0 opacity-90',
          isActive && 'text-primary-600 dark:text-primary-300'
        )}
      />
      {!collapsed && (
        <>
          <span className="flex-1 truncate">{item.label}</span>
          {item.count !== undefined && !item.comingSoon && (
            <span
              className={cn(
                'ml-auto rounded-full border px-2 py-px text-[11px] font-medium',
                isActive
                  ? 'border-primary-600 bg-primary-600 text-white dark:border-primary-500 dark:bg-primary-500'
                  : 'border-gray-200 bg-white text-gray-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400'
              )}
            >
              {item.count}
            </span>
          )}
        </>
      )}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip content={item.comingSoon ? `${item.label} (Coming Soon)` : item.label} side="right">
        <div className="relative">{content}</div>
      </Tooltip>
    );
  }
  return content;
}

export function Sidebar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const currentFilter = searchParams.get('filter');
  const currentFolder = searchParams.get('folder') ?? 'inbox';
  const { sidebarOpen, toggleSidebar } = useUIStore();
  const { user } = useAuthStore();
  const collapsed = !sidebarOpen;

  /** Match logic: an item is active when its base path matches AND, if it
   *  declares a `folder`/`filter`, the URL's matching param agrees. */
  function isItemActive(item: NavItem): boolean {
    const [base] = item.href.split('?');
    if (!pathname.startsWith(base)) return false;
    // Folder-scoped items (mailbox rows) — must match ?folder= AND must
    // not have an active cross-cut filter set, so the filter pills don't
    // light multiple sidebar items at once.
    if (item.folder) return currentFolder === item.folder && !currentFilter;
    if (item.filter) return currentFilter === item.filter;
    if (base === '/mail') return !currentFilter && currentFolder === 'inbox';
    return true;
  }

  return (
    <aside
      className={cn(
        'sticky top-0 hidden h-screen shrink-0 flex-col lg:flex',
        'border-r border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900',
        'transition-[width] duration-300 ease-in-out',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Brand */}
      <div
        className={cn(
          'flex h-14 shrink-0 items-center border-b border-gray-200 dark:border-gray-800',
          collapsed ? 'justify-center px-0' : 'gap-2.5 px-4'
        )}
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary-600 to-accent text-[13px] font-extrabold text-white">
          Aa
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-gray-900 dark:text-gray-100">
              AnjalArivaan
            </p>
            <p className="truncate text-[10px] text-gray-500 dark:text-gray-400">
              Takshashila University
            </p>
          </div>
        )}
      </div>

      {/* Compose */}
      <div className={cn(collapsed ? 'p-2' : 'p-3')}>
        <button
          type="button"
          onClick={() => router.push('/mail/compose')}
          className={cn(
            'flex w-full items-center justify-center gap-2 rounded-lg bg-primary-600 px-3 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-700',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2'
          )}
          aria-label="Compose new email"
        >
          <Plus size={16} />
          {!collapsed && <span>Compose</span>}
        </button>
      </div>

      {/* Sections */}
      <nav className="flex-1 overflow-y-auto px-2 pb-3" aria-label="Main navigation">
        {/* Mailbox */}
        <div className="mt-1">
          {!collapsed && (
            <p className="px-3 pb-1.5 pt-2 text-[10px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500">
              Mailbox
            </p>
          )}
          <ul className="space-y-0.5">
            {MAILBOX_ITEMS.map((item) => (
              <li key={item.label}>
                <SidebarItem item={item} isActive={isItemActive(item)} collapsed={collapsed} />
              </li>
            ))}
          </ul>
        </div>

        {/* AI-Powered */}
        <div className="mt-4">
          {!collapsed && (
            <p className="px-3 pb-1.5 pt-2 text-[10px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500">
              AI-Powered
            </p>
          )}
          <ul className="space-y-0.5">
            {AI_ITEMS.map((item) => (
              <li key={item.label}>
                <SidebarItem item={item} isActive={isItemActive(item)} collapsed={collapsed} />
              </li>
            ))}
          </ul>
        </div>

        {/* Tags */}
        {!collapsed && (
          <div className="mt-4">
            <p className="px-3 pb-1.5 pt-2 text-[10px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500">
              Tags
            </p>
            <ul className="space-y-0.5">
              {TAG_ITEMS.map((tag) => (
                <li key={tag.label}>
                  <Link
                    href={`/mail?filter=${tag.filter}`}
                    className={cn(
                      'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                      currentFilter === tag.filter
                        ? 'bg-primary-50 font-semibold text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-100'
                    )}
                  >
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ background: tag.color }}
                    />
                    <span className="flex-1 truncate">{tag.label}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Top-level (Dashboard / Settings) — kept available so the sidebar
            doubles as the global app nav. */}
        <div className="mt-4 border-t border-gray-200 pt-3 dark:border-gray-800">
          <ul className="space-y-0.5">
            {TOP_NAV.map((item) => (
              <li key={item.label}>
                <SidebarItem item={item} isActive={isItemActive(item)} collapsed={collapsed} />
              </li>
            ))}
            {user && ADMIN_ROLES.has(user.role) && (
              <li>
                <SidebarItem
                  item={ADMIN_NAV}
                  isActive={pathname.startsWith('/admin')}
                  collapsed={collapsed}
                />
              </li>
            )}
          </ul>
        </div>
      </nav>

      {/* User card + collapse */}
      <div className="border-t border-gray-200 p-2 dark:border-gray-800">
        {user ? (
          <div
            className={cn(
              'flex items-center rounded-lg px-2 py-2',
              collapsed ? 'justify-center' : 'gap-3'
            )}
          >
            <Avatar src={user.avatarUrl} name={user.name} size="sm" className="shrink-0" />
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
                  {user.name}
                </p>
                <p className="truncate text-xs text-gray-500 dark:text-gray-400">{user.role}</p>
              </div>
            )}
          </div>
        ) : null}

        <button
          onClick={toggleSidebar}
          className={cn(
            'mt-1 flex w-full items-center rounded-lg px-2 py-2 text-xs text-gray-500 transition-colors',
            'hover:bg-gray-100 dark:hover:bg-gray-800',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500',
            collapsed ? 'justify-center' : 'gap-2'
          )}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <ChevronRight size={14} />
          ) : (
            <>
              <ChevronLeft size={14} />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
