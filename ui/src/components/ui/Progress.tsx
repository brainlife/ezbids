import React from 'react';
import * as ProgressPrimitive from '@radix-ui/react-progress';
import { cn } from '../../lib/cn';

export interface ProgressProps extends React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> {
    value?: number;
}

export const Progress = React.forwardRef<React.ComponentRef<typeof ProgressPrimitive.Root>, ProgressProps>(
    ({ className, value = 0, ...props }, ref) => (
        <ProgressPrimitive.Root
            ref={ref}
            className={cn('relative h-2 w-full overflow-hidden rounded-full bg-gray-200', className)}
            {...props}
        >
            <ProgressPrimitive.Indicator
                className="h-full bg-blue-600 transition-all duration-300 ease-in-out"
                style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
            />
        </ProgressPrimitive.Root>
    )
);
Progress.displayName = 'Progress';
