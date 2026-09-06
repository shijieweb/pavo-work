import { useState, useCallback } from 'react';

interface ToastItem {
  id: string;
  title?: string;
  description?: string;
  type: 'success' | 'error' | 'info';
  duration?: number;
}

export function useToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const toast = useCallback((props: Omit<ToastItem, 'id'>) => {
    const id = Math.random().toString(36).slice(2);
    const duration = props.duration || 3000;

    setToasts((prev: ToastItem[]) => [...prev, { ...props, id, duration }]);

    setTimeout(() => {
      setToasts((prev: ToastItem[]) => prev.filter((t: ToastItem) => t.id !== id));
    }, duration);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev: ToastItem[]) => prev.filter((t: ToastItem) => t.id !== id));
  }, []);

  return { toast, toasts, removeToast };
}
