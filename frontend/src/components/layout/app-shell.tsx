"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Inbox,
  CalendarDays,
  ListChecks,
  Plane,
  Users,
  Search,
  Sparkles,
  ShieldCheck,
  Settings,
  LogOut,
  LayoutDashboard,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { logout } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { initials } from "@/lib/format";
import { AccountSwitcher } from "@/components/features/account-switcher";

type NavItem = { href: string; label: string; icon: React.ComponentType<{ size?: number; className?: string }>; adminOnly?: boolean };

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/briefing", label: "Briefing", icon: Sparkles },
  { href: "/mail", label: "Mail", icon: Inbox },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/tasks", label: "Tasks", icon: ListChecks },
  { href: "/travel", label: "Travel", icon: Plane },
  { href: "/contacts", label: "Contacts", icon: Users },
  { href: "/search", label: "Search", icon: Search },
  { href: "/admin", label: "Admin", icon: ShieldCheck, adminOnly: true },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth({ required: true });
  const router = useRouter();
  const pathname = usePathname();

  async function onLogout() {
    await logout();
    router.replace("/login");
  }

  if (isLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center text-ink-500 text-sm">
        Loading…
      </div>
    );
  }

  return (
    <div className="min-h-screen flex">
      <aside className="w-64 bg-white border-r border-ink-200 flex flex-col">
        <div className="px-5 py-4 border-b border-ink-200">
          <Link href="/dashboard" className="inline-flex items-center gap-2">
            <span className="w-8 h-8 rounded-full bg-brand-500 text-white inline-flex items-center justify-center font-semibold">
              அ
            </span>
            <span className="font-semibold text-ink-900">AnjalArivaan</span>
          </Link>
          <p className="text-xs text-ink-500 mt-1">Takshashila University</p>
        </div>

        <div className="px-3 py-3 border-b border-ink-200">
          <AccountSwitcher />
        </div>

        <nav className="flex-1 overflow-y-auto py-3">
          {NAV.filter((n) => !n.adminOnly || user.is_super_admin || user.is_dept_admin).map((n) => {
            const active = pathname === n.href || pathname.startsWith(n.href + "/");
            const Icon = n.icon;
            return (
              <Link
                key={n.href}
                href={n.href}
                className={cn(
                  "flex items-center gap-3 px-5 py-2 text-sm font-medium",
                  active
                    ? "bg-brand-50 text-brand-700 border-r-2 border-brand-500"
                    : "text-ink-700 hover:bg-ink-100"
                )}
              >
                <Icon size={18} />
                <span>{n.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="px-3 py-3 border-t border-ink-200">
          <div className="flex items-center gap-3 px-2 py-2">
            <div className="w-9 h-9 rounded-full bg-brand-100 text-brand-700 inline-flex items-center justify-center font-semibold text-sm">
              {initials(user.full_name || user.email)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-ink-900 truncate">
                {user.full_name || user.email}
              </p>
              <p className="text-xs text-ink-500 truncate">
                {user.designation || "Member"}
              </p>
            </div>
            <button
              onClick={onLogout}
              className="text-ink-500 hover:text-brand-600 p-1.5 rounded hover:bg-ink-100"
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      <main className="flex-1 min-w-0">
        <div className="max-w-6xl mx-auto p-8">{children}</div>
      </main>
    </div>
  );
}
