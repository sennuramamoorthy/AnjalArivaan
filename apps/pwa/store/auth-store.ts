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
  linkedAccounts: LinkedAccount[];
  activeAccountId: string | null;
  setUser: (user: User) => void;
  setTokens: (access: string) => void;
  setLinkedAccounts: (accounts: LinkedAccount[]) => void;
  switchAccount: (accountId: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      linkedAccounts: [],
      activeAccountId: null,

      setUser: (user) => set({ user }),

      setTokens: (access) => set({ accessToken: access }),

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
          linkedAccounts: [],
          activeAccountId: null,
        }),
    }),
    {
      name: 'anjal-auth',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        linkedAccounts: state.linkedAccounts,
        activeAccountId: state.activeAccountId,
      }),
    }
  )
);
