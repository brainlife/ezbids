import React from 'react';
import { InfoCircledIcon, CheckCircledIcon, ExclamationTriangleIcon, CrossCircledIcon } from '@radix-ui/react-icons';
import { cn } from '../../lib/cn';

const variants = {
    info: {
        container: 'border-blue-200 bg-blue-50 text-blue-800',
        icon: InfoCircledIcon,
    },
    success: {
        container: 'border-green-200 bg-green-50 text-green-800',
        icon: CheckCircledIcon,
    },
    warning: {
        container: 'border-yellow-200 bg-yellow-50 text-yellow-800',
        icon: ExclamationTriangleIcon,
    },
    error: {
        container: 'border-red-200 bg-red-50 text-red-800',
        icon: CrossCircledIcon,
    },
} as const;

export interface AlertProps {
    variant?: keyof typeof variants;
    title?: string;
    message?: string;
    children?: React.ReactNode;
    className?: string;
}

export function Alert({ variant = 'info', title, message, children, className }: AlertProps) {
    const { container, icon: Icon } = variants[variant];

    return (
        <div role="alert" className={cn('flex gap-3 rounded-md border p-4 text-sm', container, className)}>
            <Icon className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
                {title && <p className="font-medium">{title}</p>}
                {message && <p className={title ? 'mt-1' : ''}>{message}</p>}
                {children}
            </div>
        </div>
    );
}
