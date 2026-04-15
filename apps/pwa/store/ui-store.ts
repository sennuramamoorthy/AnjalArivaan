import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Only two themes are supported: Classic Light and Midnight Dark.
// See AnjalArivaan_UI_Themes.html for the canonical color tokens.
export type AppTheme = 'light' | 'dark';

interface UIState {
  sidebarOpen: boolean;
  theme: AppTheme;
  aiPanelOpen: boolean;
  mobileNavOpen: boolean;
  /** Width of the mail list pane in px (desktop only). User-resizable. */
  mailListWidth: number;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setTheme: (theme: AppTheme) => void;
  setAiPanelOpen: (open: boolean) => void;
  setMobileNavOpen: (open: boolean) => void;
  setMailListWidth: (width: number) => void;
}

export const MAIL_LIST_MIN_WIDTH = 280;
export const MAIL_LIST_MAX_WIDTH = 640;
export const MAIL_LIST_DEFAULT_WIDTH = 360;

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      theme: 'light',
      aiPanelOpen: false,
      mobileNavOpen: false,
      mailListWidth: MAIL_LIST_DEFAULT_WIDTH,

      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setTheme: (theme) => set({ theme }),
      setAiPanelOpen: (open) => set({ aiPanelOpen: open }),
      setMobileNavOpen: (open) => set({ mobileNavOpen: open }),
      setMailListWidth: (width) =>
        set({
          mailListWidth: Math.min(
            MAIL_LIST_MAX_WIDTH,
            Math.max(MAIL_LIST_MIN_WIDTH, Math.round(width))
          ),
        }),
    }),
    {
      name: 'anjal-ui',
      partialize: (state) => ({
        sidebarOpen: state.sidebarOpen,
        theme: state.theme,
        mailListWidth: state.mailListWidth,
      }),
      // Migrate any persisted legacy 'system' value to 'light' (Classic Light).
      // We only support the two named themes now.
      migrate: (persisted: unknown) => {
        const p = persisted as { theme?: string } | null;
        if (p && p.theme !== 'light' && p.theme !== 'dark') {
          return { ...p, theme: 'light' } as Partial<UIState>;
        }
        return p as Partial<UIState>;
      },
      version: 2,
    }
  )
);
