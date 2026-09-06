import { Plus, FileText } from 'lucide-react';
import SearchBar from './SearchBar';
import { StatusFilter } from './StatusBadge';
import type { ProjectStatus } from '@/types/api';

interface EmptyStateProps {
  onAction?: () => void;
  actionLabel?: string;
}

export default function EmptyState({ onAction, actionLabel = '新建项目' }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-4">
      <div className="w-16 h-16 rounded-sm bg-accent/10 flex items-center justify-center mb-4">
        <FileText className="w-8 h-8 text-accent" />
      </div>
      <h2 className="text-xl font-medium text-fg text-center mb-2">
        还没有项目
      </h2>
      <p className="text-sm text-muted text-center max-w-sm mb-6">
        创建你的第一个项目，让AI帮你结构化需求管理
      </p>
      {onAction && (
        <button
          onClick={onAction}
          className="btn-primary"
        >
          <Plus className="w-4 h-4" />
          {actionLabel}
        </button>
      )}
    </div>
  );
}

interface LoadingStateProps {
  count?: number;
}

export function LoadingState({ count = 6 }: LoadingStateProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="card p-5 animate-pulse"
        >
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-sm bg-surface-warm" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-surface-warm rounded-sm w-3/4" />
              <div className="h-3 bg-surface-warm rounded-sm w-full" />
              <div className="h-3 bg-surface-warm rounded-sm w-2/3" />
            </div>
          </div>
          <div className="flex justify-between mt-4">
            <div className="h-5 bg-surface-warm rounded-sm w-16" />
            <div className="h-3 bg-surface-warm rounded-sm w-20" />
          </div>
        </div>
      ))}
    </div>
  );
}

interface HeaderProps {
  searchValue: string;
  onSearchChange: (value: string) => void;
  statusValue: ProjectStatus | 'all';
  onStatusChange: (value: ProjectStatus | 'all') => void;
  onNewProject: () => void;
  totalCount: number;
}

export function PageHeader({
  searchValue,
  onSearchChange,
  statusValue,
  onStatusChange,
  onNewProject,
  totalCount,
}: HeaderProps) {
  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-medium text-fg tracking-tight">项目列表</h1>
          <p className="text-sm text-muted mt-0.5">
            共 {totalCount} 个项目
          </p>
        </div>
        <button
          onClick={onNewProject}
          className="btn-primary"
        >
          <Plus className="w-4 h-4" />
          新建项目
        </button>
      </div>

      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <SearchBar
          value={searchValue}
          onChange={onSearchChange}
          placeholder="搜索项目名称或描述..."
        />
        <StatusFilter
          value={statusValue}
          onChange={onStatusChange}
        />
      </div>
    </div>
  );
}
