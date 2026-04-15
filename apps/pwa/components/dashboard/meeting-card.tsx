import * as React from 'react';
import { MapPin, Video } from 'lucide-react';
import { cn, formatTime } from '@/lib/utils';
import { AvatarGroup } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export interface MeetingCardProps {
  id: string;
  title: string;
  startTime: Date;
  endTime: Date;
  location?: string;
  isOnline?: boolean;
  attendees: Array<{ name: string; avatarUrl?: string }>;
  joinUrl?: string;
}

export function MeetingCard({
  title,
  startTime,
  endTime,
  location,
  isOnline,
  attendees,
  joinUrl,
}: MeetingCardProps) {
  const now = new Date();
  const isHappeningNow = startTime <= now && now <= endTime;
  const isUpcoming = startTime > now;

  return (
    <div
      className={cn(
        'rounded-xl border p-4',
        'bg-white dark:bg-gray-900',
        isHappeningNow
          ? 'border-emerald-300 ring-1 ring-emerald-200 dark:border-emerald-700 dark:ring-emerald-900'
          : 'border-gray-200 dark:border-gray-700',
        'transition-shadow hover:shadow-sm'
      )}
    >
      {/* Time + status */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-xs font-semibold text-primary-600 dark:text-primary-400">
          {formatTime(startTime)} – {formatTime(endTime)}
        </span>
        {isHappeningNow && (
          <Badge variant="success" className="text-[10px] shrink-0">
            Now
          </Badge>
        )}
      </div>

      {/* Title */}
      <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2 leading-snug">
        {title}
      </h3>

      {/* Location */}
      {(location || isOnline) && (
        <div className="flex items-center gap-1.5 mb-3">
          {isOnline ? (
            <Video size={12} className="text-gray-400 shrink-0" />
          ) : (
            <MapPin size={12} className="text-gray-400 shrink-0" />
          )}
          <span className="text-xs text-gray-500 dark:text-gray-400 truncate">
            {isOnline ? 'Online meeting' : location}
          </span>
          {location && (
            <Badge variant="outline" className="ml-1 text-[10px] shrink-0">
              {location}
            </Badge>
          )}
        </div>
      )}

      {/* Footer: attendees + join */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AvatarGroup avatars={attendees} max={3} size="sm" />
          {attendees.length > 0 && (
            <span className="text-xs text-gray-400">
              {attendees.length} attendee{attendees.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {(isHappeningNow || isUpcoming) && (
          <Button
            variant={isHappeningNow ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => joinUrl && window.open(joinUrl, '_blank')}
          >
            {isHappeningNow ? 'Join now' : 'Join'}
          </Button>
        )}
      </div>
    </div>
  );
}
