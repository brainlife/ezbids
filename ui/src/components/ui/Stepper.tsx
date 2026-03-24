import React from 'react';
import { CheckIcon } from '@radix-ui/react-icons';
import { cn } from '../../lib/cn';

export interface StepperProps {
    steps: string[];
    activeStep: number;
    className?: string;
}

export function Stepper({ steps, activeStep, className }: StepperProps) {
    return (
        <div className={cn('flex items-center gap-2', className)}>
            {steps.map((label, index) => {
                const isCompleted = index < activeStep;
                const isActive = index === activeStep;

                return (
                    <React.Fragment key={index}>
                        {index > 0 && (
                            <div className={cn('h-px flex-1', isCompleted ? 'bg-blue-600' : 'bg-gray-300')} />
                        )}
                        <div className="flex flex-col items-center gap-1">
                            <div
                                className={cn(
                                    'flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium',
                                    isCompleted && 'bg-blue-600 text-white',
                                    isActive && 'border-2 border-blue-600 text-blue-600',
                                    !isCompleted && !isActive && 'border-2 border-gray-300 text-gray-400'
                                )}
                            >
                                {isCompleted ? <CheckIcon className="h-4 w-4" /> : index + 1}
                            </div>
                            <span
                                className={cn(
                                    'text-xs whitespace-nowrap',
                                    isActive ? 'font-medium text-blue-600' : 'text-gray-500'
                                )}
                            >
                                {label}
                            </span>
                        </div>
                    </React.Fragment>
                );
            })}
        </div>
    );
}
