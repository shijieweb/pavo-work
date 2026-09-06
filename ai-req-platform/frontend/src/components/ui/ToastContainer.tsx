import { CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ToastItem {
  id: string;
  title?: string;
  description?: string;
  type: 'success' | 'error' | 'info';
}

interface ToastContainerProps {
  toasts: ToastItem[];
  removeToast: (id: string) => void;
}

const typeIcons = {
  success: CheckCircle,
  error: XCircle,
  info: AlertCircle,
};

const typeColors = {
  success: 'text-[#16A34A]',
  error: 'text-[#DC2626]',
  info: 'text-[#4F46E5]',
};

export default function ToastContainer({ toasts, removeToast }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2" aria-live="polite">
      {toasts.map((toast) => {
        const Icon = typeIcons[toast.type];
        return (
          <div
            key={toast.id}
            className={cn(
              'flex items-start gap-3 p-4 rounded-lg shadow-md border',
              'bg-surface border-border max-w-sm animate-in fade-in slide-in-from-right'
            )}
            role="alert"
          >
            <Icon className={cn('w-5 h-5 flex-shrink-0 mt-0.5', typeColors[toast.type])} />
            <div className="flex-1 min-w-0">
              {toast.title && (
                <p className="text-sm font-medium text-fg">{toast.title}</p>
              )}
              {toast.description && (
                <p className="text-sm text-muted mt-0.5">{toast.description}</p>
              )}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-meta hover:text-fg transition-colors"
              aria-label="关闭"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 6 6 18"/>
                <path d="m6 6 12 12"/>
              </svg>
            </button>
          </div>
        );
      })}
    </div>
  );
}
