'use client';

import * as React from 'react';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { MailListPane } from '@/components/mail/mail-list-pane';
import {
  useUIStore,
  MAIL_LIST_MIN_WIDTH,
  MAIL_LIST_MAX_WIDTH,
} from '@/store/ui-store';

/**
 * Mail route layout — implements the desktop 3-pane email-client shell from
 * AnjalArivaan_UI_Themes.html. Combined with the global app sidebar:
 *
 *   [ App Sidebar  ][ Mail List Pane (resizable) ][ Detail Pane (1fr) ]
 *
 * The vertical divider between the list and detail panes is draggable on
 * lg+ — the chosen width is persisted in the UI store. On mobile (<lg) we
 * fall back to the route-based flow (list at /mail, detail at /mail/[id]).
 */
export default function MailLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isDetailRoute = pathname !== '/mail' && pathname.startsWith('/mail/');
  const selectedId = isDetailRoute ? pathname.split('/')[2] : undefined;

  const { mailListWidth, setMailListWidth } = useUIStore();
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = React.useState(false);

  // Track whether we're on a desktop viewport. The dynamic width and the
  // resize divider only apply at lg+ — on mobile the list takes the full
  // screen and the detail swaps in via routing.
  const [isLg, setIsLg] = React.useState(false);
  React.useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)');
    const sync = () => setIsLg(mq.matches);
    sync();
    mq.addEventListener('change', sync);
    return () => mq.removeEventListener('change', sync);
  }, []);

  // Pointer-based resize. We listen on the window so the drag survives the
  // pointer briefly leaving the thin divider hit area.
  React.useEffect(() => {
    if (!isDragging) return;

    function onMove(e: PointerEvent) {
      const container = containerRef.current;
      if (!container) return;
      // The list pane sits at the left edge of the container, so the new
      // width is simply the pointer's offset from that edge.
      const newWidth = e.clientX - container.getBoundingClientRect().left;
      setMailListWidth(newWidth);
    }
    function onUp() {
      setIsDragging(false);
    }

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    // Block text selection / change cursor globally during the drag.
    const prevUserSelect = document.body.style.userSelect;
    const prevCursor = document.body.style.cursor;
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';

    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      document.body.style.userSelect = prevUserSelect;
      document.body.style.cursor = prevCursor;
    };
  }, [isDragging, setMailListWidth]);

  // Keyboard a11y — left/right arrows nudge the divider 16px at a time when
  // it's focused. Home/End jump to the min/max bounds.
  function onDividerKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    const step = e.shiftKey ? 48 : 16;
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      setMailListWidth(mailListWidth - step);
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      setMailListWidth(mailListWidth + step);
    } else if (e.key === 'Home') {
      e.preventDefault();
      setMailListWidth(MAIL_LIST_MIN_WIDTH);
    } else if (e.key === 'End') {
      e.preventDefault();
      setMailListWidth(MAIL_LIST_MAX_WIDTH);
    }
  }

  return (
    <div
      ref={containerRef}
      className="flex h-[calc(100vh-3.5rem-4rem)] overflow-hidden lg:h-[calc(100vh-3.5rem)]"
    >
      {/* List pane — full width on mobile, user-controlled pixel width on lg+ */}
      <aside
        style={isLg ? { width: mailListWidth } : undefined}
        className={cn(
          'w-full shrink-0 overflow-hidden border-r border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950',
          isDetailRoute ? 'hidden lg:block' : 'block'
        )}
      >
        <MailListPane selectedId={selectedId} />
      </aside>

      {/* Resize handle — desktop only, sits between the two panes */}
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize email list"
        aria-valuenow={mailListWidth}
        aria-valuemin={MAIL_LIST_MIN_WIDTH}
        aria-valuemax={MAIL_LIST_MAX_WIDTH}
        tabIndex={0}
        onPointerDown={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onKeyDown={onDividerKeyDown}
        className={cn(
          'hidden lg:block',
          'group relative w-1 shrink-0 cursor-col-resize bg-transparent',
          'hover:bg-primary-200/60 dark:hover:bg-primary-700/40',
          'focus:outline-none focus-visible:bg-primary-400/60',
          isDragging && 'bg-primary-400/70 dark:bg-primary-500/60'
        )}
      >
        {/* Wider invisible hit area so users don't have to pixel-hunt */}
        <span className="absolute inset-y-0 -left-1.5 -right-1.5" />
      </div>

      {/* Detail pane */}
      <section
        className={cn(
          'flex-1 overflow-hidden bg-white dark:bg-gray-950',
          isDetailRoute ? 'block' : 'hidden lg:block'
        )}
      >
        {children}
      </section>
    </div>
  );
}
