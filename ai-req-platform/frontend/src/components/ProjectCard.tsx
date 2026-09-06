import { Project } from '@/types/api';
import { FileText, ArrowRight } from 'lucide-react';
import { StatusBadge } from './StatusBadge';
import { cn } from '@/lib/utils';

interface ProjectCardProps {
  project: Project;
  onNavigate: (id: number) => void;
  onDelete?: (id: number) => void;
}

export default function ProjectCard({ project, onNavigate, onDelete }: ProjectCardProps) {
  return (
    <div
      className={cn(
        'card p-5 cursor-pointer group',
        'focus-within:ring-2 focus-within:ring-accent focus-within:ring-opacity-30'
      )}
      onClick={() => onNavigate(project.id)}
      onKeyDown={(e) => e.key === 'Enter' && onNavigate(project.id)}
      tabIndex={0}
      role="link"
      aria-label={`查看项目：${project.name}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div
            className={cn(
              'w-10 h-10 rounded-sm flex items-center justify-center',
              'bg-accent/10 text-accent flex-shrink-0'
            )}
          >
            <FileText className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h3 className="text-base font-medium text-fg truncate group-hover:text-accent transition-colors">
              {project.name}
            </h3>
            <p className="text-sm text-muted mt-0.5 line-clamp-2">
              {project.description || '暂无描述'}
            </p>
          </div>
        </div>
        <ArrowRight
          className="w-4 h-4 text-meta opacity-0 group-hover:opacity-100 transition-opacity"
          aria-hidden="true"
        />
      </div>

      <div className="flex items-center justify-between mt-4">
        <StatusBadge status={project.status} />
        <span className="text-xs text-meta">
          {new Date(project.created_at).toLocaleDateString('zh-CN')}
        </span>
      </div>

      {onDelete && (
        <button
          className={cn(
            'mt-3 w-full py-1.5 text-sm text-danger opacity-0',
            'group-hover:opacity-100 transition-opacity',
            'hover:bg-danger/10 rounded-sm'
          )}
          onClick={(e) => {
            e.stopPropagation();
            onDelete(project.id);
          }}
          aria-label={`删除项目：${project.name}`}
        >
          删除项目
        </button>
      )}
    </div>
  );
}
