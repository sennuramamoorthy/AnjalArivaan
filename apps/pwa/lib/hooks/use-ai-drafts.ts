'use client';

/**
 * useAiDrafts — request 3 AI reply drafts for a mail thread.
 *
 * Wraps POST /api/v1/mail/threads/{threadId}/ai-drafts behind React Query's
 * useMutation. The call returns three drafts (acknowledge / agree / decline),
 * which the UI renders as chips the user can pick from to populate the
 * compose box.
 */

import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { useAuthStore } from '@/store/auth-store';

export type DraftIntent = 'acknowledge' | 'agree' | 'decline' | 'custom';

export interface AiDraftOption {
  intent: string;
  body: string;
  signatureId?: string | null;
}

export interface AiDraftsResponse {
  drafts: AiDraftOption[];
  modelId: string;
  promptTemplateId: string;
}

export interface RequestAiDraftsArgs {
  intent: DraftIntent;
  customInstruction?: string;
}

function useEffectiveAccountId(): string | undefined {
  const { activeAccountId, linkedAccounts } = useAuthStore();
  return activeAccountId ?? linkedAccounts[0]?.id ?? undefined;
}

export function useAiDrafts(threadId: string) {
  const accountId = useEffectiveAccountId();
  return useMutation({
    mutationFn: async (args: RequestAiDraftsArgs) => {
      return apiClient.post<AiDraftsResponse>(
        `/api/v1/mail/threads/${threadId}/ai-drafts`,
        {
          intent: args.intent,
          ...(args.customInstruction
            ? { customInstruction: args.customInstruction }
            : {}),
        },
        { params: { accountId } },
      );
    },
  });
}
