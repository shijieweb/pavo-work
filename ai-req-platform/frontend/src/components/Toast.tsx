import { CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ToastProps {
  id: string;
  title?: string;
  description?: string;
  type?: 'success' | 'error' | 'info';
  onClose?: (id: string) => void;
}

const icons = {
  success: CheckCircle,
  error: XCircle,
  info: AlertCircle,
};

const colors = {
  success: 'text-success',
  error: 'text-danger',
  info: 'text-accent',
};

export default function Toast({ id, title, description, type = 'info', onClose }: ToastProps) {
  const Icon = icons[type];

  return (
    <div
      className={cn(
        'flex items-start gap-3 p-4 rounded-lg shadow-md border animate-in fade-in slide-in-from-right',
        'bg-surface border-border max-w-sm'
      )}
      role="alert"
    >
      <Icon className={cn('w-5 h-5 flex-shrink-0 mt-0.5', colors[type])} />
      <div className="flex-1 min-w-0">
        {title && <p className="text-sm font-medium text-fg">{title}</p>}
        {description && <p className="text-sm text-muted mt-0.5">{description}</p>}
      </div>
      <button
        onClick={() => onClose?.(id)}
        className="text-meta hover:text-fg transition-colors"
        aria-label="关闭"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 6 6 18"/><path d="m6 6 12 12"/>
        </svg>
      </button>
    </div>
  );
}
