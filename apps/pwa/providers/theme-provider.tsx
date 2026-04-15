'use client';

import { useEffect } from 'react';
import { useUIStore } from '@/store/ui-store';

/**
 * Applies one of the two supported themes — "Classic Light" or "Midnight Dark" —
 * by toggling the `dark` class on <html>. Color tokens for both themes live in
 * `app/globals.css` (see :root and .dark blocks) and mirror the reference in
 * AnjalArivaan_UI_Themes.html. No system/auto mode is supported by design.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { theme } = useUIStore();

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      root.dataset.theme = 'midnight';
    } else {
      root.classList.remove('dark');
      root.dataset.theme = 'classic';
    }
  }, [theme]);

  return <>{children}</>;
}
