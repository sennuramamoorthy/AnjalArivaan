'use client';

import * as React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { DailyBriefingCard } from '@/components/dashboard/daily-briefing-card';
import { UrgentEmailsSection } from '@/components/dashboard/urgent-emails-section';
import { MeetingCard, MeetingCardProps } from '@/components/dashboard/meeting-card';
import { Skeleton } from '@/components/ui/skeleton';
import { useDailyBriefing, useMailList, mailKeys } from '@/lib/hooks/use-mail';
import { useLinkedAccounts } from '@/lib/hooks/use-account-link';
import { useAuthStore } from '@/store/auth-store';
import type { EmailSummary } from '@/lib/api/mail';
import type { EmailCardProps } from '@/components/mail/email-card';

// Meetings are not yet wired to a backend API — show placeholder until calendar integration
const PLACEHOLDER_MEETINGS: MeetingCardProps[] = [];

/** Convert API EmailSummary to EmailCardProps */
function toCardProps(email: EmailSummary): EmailCardProps {
  return {
    id: email.id,
    from: email.from,
    subject: email.subject,
    preview: email.preview,
    receivedAt: new Date(email.receivedAt),
    isRead: email.isRead,
    urgencyLevel: email.urgencyLevel,
    hasAttachment: email.hasAttachment,
    linkedAccount: email.linkedAccount,
  };
}

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { activeAccountId } = useAuthStore();
  const { data: linkedAccounts, isLoading: isLoadingAccounts } = useLinkedAccounts();
  const { data: briefingData, isLoading: briefingLoading } = useDailyBriefing();
  const { data: urgentData, isLoading: urgentLoading } = useMailList({ filter: 'urgent' });

  const hasAccount = activeAccountId || (linkedAccounts && linkedAccounts.length > 0);

  const handleRefreshBriefing = () => {
    queryClient.invalidateQueries({ queryKey: mailKeys.briefing() });
  };

  // Flatten urgent emails from paginated response
  const urgentEmails: EmailCardProps[] = React.useMemo(() => {
    if (!urgentData?.pages) return [];
    return urgentData.pages
      .flatMap((page) => page.emails)
      .slice(0, 5)
      .map(toCardProps);
  }, [urgentData]);

  const totalUrgent = urgentData?.pages?.[0]?.total ?? 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      {/* No account connected banner */}
      {!isLoadingAccounts && !hasAccount && (
        <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-900/20">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-800/40">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-amber-600 dark:text-amber-400"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-amber-900 dark:text-amber-100">
                No email account connected
              </p>
              <p className="mt-0.5 text-sm text-amber-700 dark:text-amber-300">
                Link your Google Workspace account to see your daily briefing, urgent emails, and more.
              </p>
            </div>
            <button
              onClick={() => router.push('/settings')}
              className="shrink-0 rounded-lg bg-amber-600 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-amber-700 transition-colors"
            >
              Connect
            </button>
          </div>
        </div>
      )}

      {/* Daily Briefing — full width */}
      <div className="mb-6">
        <DailyBriefingCard
          content={briefingData?.content ?? ''}
          generatedAt={briefingData?.generatedAt ?? ''}
          isLoading={briefingLoading}
          onRefresh={handleRefreshBriefing}
        />
      </div>

      {/* Two-column grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Urgent emails */}
        <UrgentEmailsSection
          emails={urgentEmails}
          isLoading={urgentLoading}
          totalUrgent={totalUrgent}
        />

        {/* Today's meetings */}
        <section aria-labelledby="meetings-heading">
          <div className="mb-3">
            <h2
              id="meetings-heading"
              className="text-sm font-semibold text-gray-900 dark:text-gray-100"
            >
              Today&apos;s Meetings
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {PLACEHOLDER_MEETINGS.length > 0
                ? `${PLACEHOLDER_MEETINGS.length} meetings scheduled`
                : 'Calendar integration coming soon'}
            </p>
          </div>
          {PLACEHOLDER_MEETINGS.length > 0 ? (
            <div className="space-y-3">
              {PLACEHOLDER_MEETINGS.map((meeting) => (
                <MeetingCard key={meeting.id} {...meeting} />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 py-10 dark:border-gray-700">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                No meetings loaded
              </p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                Google Calendar integration will be available soon
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
