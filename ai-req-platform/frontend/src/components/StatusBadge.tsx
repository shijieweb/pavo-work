import { cn } from '@/lib/utils';
import type { ProjectStatus } from '@/types/api';

const statusConfig = {
  active: { label: '进行中', color: 'bg-accent/10 text-accent' },
  completed: { label: '已完成', color: 'bg-[#16A34A]/10 text-[#16A34A]' },
  archived: { label: '已归档', color: 'bg-meta/10 text-meta' },
};

interface StatusBadgeProps {
  status: ProjectStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status];
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5',
        'text-xs font-medium rounded-sm',
        config.color,
        className
      )}
    >
      {config.label}
    </span>
  );
}

interface StatusFilterProps {
  value: ProjectStatus | 'all';
  onChange: (value: ProjectStatus | 'all') => void;
}

const statuses: Array<{ value: ProjectStatus | 'all'; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'active', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'archived', label: '已归档' },
];

export function StatusFilter({ value, onChange }: StatusFilterProps) {
  return (
    <div className="flex items-center gap-1" role="radiogroup" aria-label="状态筛选">
      {statuses.map((s) => (
        <button
          key={s.value}
          onClick={() => onChange(s.value)}
          className={cn(
            'px-3 py-1.5 text-sm rounded-sm transition-colors duration-150',
            'focus:outline-none focus:ring-2 focus:ring-accent focus:ring-opacity-30',
            value === s.value
              ? 'bg-accent/10 text-accent font-medium'
              : 'text-muted hover:text-fg hover:bg-surface-warm'
          )}
          role="radio"
          aria-checked={value === s.value}
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}
