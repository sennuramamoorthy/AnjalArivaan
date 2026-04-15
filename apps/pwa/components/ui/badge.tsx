import * as React from 'react';
import { cn } from '@/lib/utils';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'urgent' | 'success' | 'warning' | 'outline';
}

const variantClasses: Record<NonNullable<BadgeProps['variant']>, string> = {
  default:
    'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  urgent:
    'bg-red-100 text-red-700 animate-pulse-urgent dark:bg-red-900/40 dark:text-red-400',
  success:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400',
  warning:
    'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400',
  outline:
    'border border-gray-300 text-gray-700 bg-transparent dark:border-gray-600 dark:text-gray-300',
};

const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', ...props }, ref) => (
    <span
      ref={ref}
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        variantClasses[variant],
        className
      )}
      {...props}
    />
  )
);
Badge.displayName = 'Badge';

export { Badge };
