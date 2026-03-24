import React from 'react';
import { cn } from '../../lib/cn';

const variantStyles = {
    default: 'border-gray-200 bg-gray-100 text-gray-700',
    success: 'border-green-200 bg-green-100 text-green-700',
    warning: 'border-yellow-200 bg-yellow-100 text-yellow-700',
    error: 'border-red-200 bg-red-100 text-red-700',
} as const;

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
    variant?: keyof typeof variantStyles;
}

export function Badge({ variant = 'default', className, ...props }: BadgeProps) {
    return (
        <span
            className={cn(
                'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
                variantStyles[variant],
                className
            )}
            {...props}
        />
    );
}
