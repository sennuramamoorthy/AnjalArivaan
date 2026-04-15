'use client';

import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight, InboxIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { EmailCard, EmailCardProps } from '@/components/mail/email-card';

interface UrgentEmailsSectionProps {
  emails: EmailCardProps[];
  isLoading: boolean;
  totalUrgent: number;
}

export function UrgentEmailsSection({ emails, isLoading, totalUrgent }: UrgentEmailsSectionProps) {
  const router = useRouter();

  return (
    <section aria-labelledby="urgent-heading">
      {/* Section header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h2
            id="urgent-heading"
            className="text-sm font-semibold text-gray-900 dark:text-gray-100"
          >
            Urgent
          </h2>
          {totalUrgent > 0 && (
            <Badge variant="urgent">{totalUrgent}</Badge>
          )}
        </div>

        {totalUrgent > 0 && (
          <Link
            href="/mail?filter=urgent"
            className={cn(
              'flex items-center gap-1 text-xs font-medium text-primary-600 dark:text-primary-400',
              'hover:text-primary-700 dark:hover:text-primary-300 transition-colors'
            )}
          >
            View all
            <ArrowRight size={12} />
          </Link>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-xl border border-gray-200 p-3.5 dark:border-gray-700">
              <div className="flex gap-3">
                <Skeleton className="h-9 w-9 rounded-full shrink-0" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3.5 w-1/3" />
                  <Skeleton className="h-3.5 w-2/3" />
                  <Skeleton className="h-3 w-full" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : emails.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 py-10 dark:border-gray-700">
          <InboxIcon size={32} className="text-gray-300 dark:text-gray-600 mb-2" />
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">No urgent emails</p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
            All clear — no government or high-priority mail
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {emails.map((email) => (
            <EmailCard
              key={email.id}
              {...email}
              onClick={() => router.push(`/mail/${email.id}`)}
            />
          ))}
        </div>
      )}
    </section>
  );
}
