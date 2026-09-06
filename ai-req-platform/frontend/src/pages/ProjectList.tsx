import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProjectStore } from '@/store';
import { useToast } from '@/hooks/use-toast';
import ProjectCard from '@/components/ProjectCard';
import EmptyState from '@/components/EmptyState';
import { LoadingState, PageHeader } from '@/components/EmptyState';
import type { ProjectStatus } from '@/types/api';

export default function ProjectList() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { projects, loading, fetchProjects, deleteProject, setFilters } = useProjectStore();

  const [searchValue, setSearchValue] = useState('');
  const [statusValue, setStatusValue] = useState<ProjectStatus | 'all'>('all');
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

  useEffect(() => {
    fetchProjects({ search: searchValue || undefined, status: statusValue === 'all' ? undefined : statusValue });
  }, [statusValue]);

  const handleSearch = (value: string) => {
    setSearchValue(value);
    setFilters({ search: value || undefined });
  };

  const handleStatusChange = (value: ProjectStatus | 'all') => {
    setStatusValue(value);
    setFilters({ status: value === 'all' ? undefined : value });
  };

  const handleDelete = async (id: number) => {
    if (!confirmDeleteId) {
      setConfirmDeleteId(id);
      return;
    }

    if (confirmDeleteId === id) {
      const success = await deleteProject(id);
      if (success) {
        toast({ title: '项目已删除', type: 'success' });
      } else {
        toast({ title: '删除失败，请重试', type: 'error' });
      }
      setConfirmDeleteId(null);
    } else {
      setConfirmDeleteId(id);
    }
  };

  const handleNewProject = () => {
    navigate('/new');
  };

  const handleNavigate = (id: number) => {
    navigate(`/projects/${id}`);
  };

  return (
    <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageHeader
        searchValue={searchValue}
        onSearchChange={handleSearch}
        statusValue={statusValue}
        onStatusChange={handleStatusChange}
        onNewProject={handleNewProject}
        totalCount={projects.length}
      />

      <div className="mt-8">
        {loading ? (
          <LoadingState count={6} />
        ) : projects.length === 0 ? (
          <EmptyState
            onAction={handleNewProject}
            actionLabel="新建项目"
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                onNavigate={handleNavigate}
                onDelete={confirmDeleteId === project.id ? undefined : handleDelete}
              />
            ))}
          </div>
        )}
      </div>

      {confirmDeleteId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-dialog-title"
        >
          <div className="card max-w-sm w-full p-6">
            <h2 id="delete-dialog-title" className="text-lg font-medium text-fg mb-2">
              确认删除
            </h2>
            <p className="text-sm text-muted mb-6">
              此操作不可撤销，确定要删除这个项目吗？
            </p>
            <div className="flex justify-end gap-2">
              <button
                className="btn-secondary"
                onClick={() => setConfirmDeleteId(null)}
              >
                取消
              </button>
              <button
                className="btn-danger"
                onClick={() => handleDelete(confirmDeleteId)}
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
