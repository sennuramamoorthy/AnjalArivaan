import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  avatarUrl?: string;
}

interface LinkedAccount {
  id: string;
  googleEmail: string;
  workspaceDomain: string;
  avatarUrl?: string;
  displayName?: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  linkedAccounts: LinkedAccount[];
  activeAccountId: string | null;
  setUser: (user: User) => void;
  /**
   * Persist both tokens. `refresh` is optional so legacy call-sites that
   * only pass an access token keep working, but the login/MFA flow should
   * always pass both so we can silently refresh the short-lived access
   * token without kicking the user back to /login every 15 minutes.
   */
  setTokens: (access: string, refresh?: string) => void;
  setLinkedAccounts: (accounts: LinkedAccount[]) => void;
  switchAccount: (accountId: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      linkedAccounts: [],
      activeAccountId: null,

      setUser: (user) => set({ user }),

      setTokens: (access, refresh) =>
        set((state) => ({
          accessToken: access,
          refreshToken: refresh ?? state.refreshToken,
        })),

      setLinkedAccounts: (accounts) =>
        set((state) => {
          const stillExists =
            state.activeAccountId &&
            accounts.some((a) => a.id === state.activeAccountId);
          return {
            linkedAccounts: accounts,
            activeAccountId: stillExists
              ? state.activeAccountId
              : accounts.length > 0
              ? accounts[0].id
              : null,
          };
        }),

      switchAccount: (accountId) => set({ activeAccountId: accountId }),

      logout: () =>
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          linkedAccounts: [],
          activeAccountId: null,
        }),
    }),
    {
      name: 'anjal-auth',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        linkedAccounts: state.linkedAccounts,
        activeAccountId: state.activeAccountId,
      }),
    }
  )
);
