import * as React from 'react';
import Image from 'next/image';
import { cn, getInitials } from '@/lib/utils';

export interface AvatarProps {
  src?: string | null;
  name: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeMap = {
  sm: { px: 24, text: 'text-[10px]' },
  md: { px: 36, text: 'text-xs' },
  lg: { px: 48, text: 'text-sm' },
};

const colorPalette = [
  'bg-violet-500',
  'bg-indigo-500',
  'bg-blue-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-rose-500',
  'bg-teal-500',
  'bg-cyan-500',
];

function getColorForName(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colorPalette[Math.abs(hash) % colorPalette.length];
}

export function Avatar({ src, name, size = 'md', className }: AvatarProps) {
  const { px, text } = sizeMap[size];
  const [imgError, setImgError] = React.useState(false);
  const initials = getInitials(name);
  const bgColor = getColorForName(name);

  return (
    <div
      className={cn(
        'relative inline-flex shrink-0 items-center justify-center rounded-full overflow-hidden',
        className
      )}
      style={{ width: px, height: px }}
      aria-label={name}
      role="img"
    >
      {src && !imgError ? (
        <Image
          src={src}
          alt={name}
          fill
          className="object-cover"
          onError={() => setImgError(true)}
          sizes={`${px}px`}
        />
      ) : (
        <span
          className={cn(
            'flex h-full w-full items-center justify-center font-semibold text-white',
            bgColor,
            text
          )}
        >
          {initials}
        </span>
      )}
    </div>
  );
}

export interface AvatarGroupProps {
  avatars: Array<{ src?: string | null; name: string }>;
  max?: number;
  size?: 'sm' | 'md';
}

export function AvatarGroup({ avatars, max = 3, size = 'sm' }: AvatarGroupProps) {
  const visible = avatars.slice(0, max);
  const overflow = avatars.length - max;

  return (
    <div className="flex -space-x-2">
      {visible.map((a, i) => (
        <Avatar
          key={i}
          src={a.src}
          name={a.name}
          size={size}
          className="ring-2 ring-white dark:ring-gray-900"
        />
      ))}
      {overflow > 0 && (
        <div
          className={cn(
            'inline-flex items-center justify-center rounded-full bg-gray-200 ring-2 ring-white text-gray-600 font-medium dark:bg-gray-700 dark:ring-gray-900 dark:text-gray-300',
            size === 'sm' ? 'h-6 w-6 text-[9px]' : 'h-9 w-9 text-xs'
          )}
        >
          +{overflow}
        </div>
      )}
    </div>
  );
}
