import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowLeft, Sparkles, RefreshCw, Pencil, Save } from 'lucide-react';
import { useProjectStore } from '@/store';
import { useToast } from '@/hooks/use-toast';
import { projectFormSchema, type ProjectFormValues } from '@/lib/validators';

export default function ProjectDetail() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { toast } = useToast();
  const { fetchProject, updateProject, optimizeProject } = useProjectStore();

  const [project, setProject] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [optimizing, setOptimizing] = useState(false);
  const [optimizedContent, setOptimizedContent] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<ProjectFormValues>({
    resolver: zodResolver(projectFormSchema),
  });

  useEffect(() => {
    if (id) {
      fetchProject(Number(id)).then((p) => {
        if (p) {
          setProject(p);
          reset({ name: p.name, description: p.description || '' });
        } else {
          navigate('/');
        }
      }).finally(() => setLoading(false));
    }
  }, [id]);

  const handleOptimize = async () => {
    if (!id) return;

    const settings = localStorage.getItem('settings-store');
    if (!settings) {
      toast({ title: '请先配置AI模型', type: 'error' });
      return;
    }

    setOptimizing(true);
    try {
      const result = await optimizeProject(Number(id));
      if (result) {
        setOptimizedContent(result);
        toast({ title: 'AI优化完成', type: 'success' });
      }
    } catch {
      toast({ title: 'AI优化失败，请重试', type: 'error' });
    } finally {
      setOptimizing(false);
    }
  };

  const handleApply = () => {
    if (optimizedContent) {
      reset({ name: project.name, description: optimizedContent });
      setOptimizedContent(null);
      toast({ title: '已应用优化内容', type: 'success' });
    }
  };

  const handleDiscard = () => {
    setOptimizedContent(null);
  };

  const onSubmit = async (data: ProjectFormValues) => {
    if (!id) return;

    const success = await updateProject(Number(id), {
      name: data.name,
      description: data.description,
    });

    if (success) {
      toast({ title: '项目更新成功', type: 'success' });
      setIsEditing(false);
    } else {
      toast({ title: '更新失败，请重试', type: 'error' });
    }
  };

  if (loading) {
    return (
      <div className="max-w-[800px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="skeleton h-8 w-32 mb-6" />
        <div className="skeleton h-10 w-48 mb-2" />
        <div className="skeleton h-4 w-64 mb-8" />
        <div className="space-y-4">
          <div className="skeleton h-12 w-full" />
          <div className="skeleton h-32 w-full" />
        </div>
      </div>
    );
  }

  if (!project) return null;

  return (
    <div className="max-w-[800px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <button
        onClick={() => navigate(-1)}
        className="btn-ghost mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        返回列表
      </button>

      <div className="mb-8">
        <h1 className="text-2xl font-medium text-fg tracking-tight">
          {project.name}
        </h1>
        <p className="text-sm text-muted mt-1">
          创建时间：{new Date(project.created_at).toLocaleDateString('zh-CN')}
        </p>
      </div>

      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-medium text-fg">项目描述</h2>
          <button
            onClick={() => setIsEditing(!isEditing)}
            className="btn-ghost"
            aria-label={isEditing ? '保存编辑' : '编辑项目'}
          >
            {isEditing ? (
              <>
                <Save className="w-4 h-4" />
                保存
              </>
            ) : (
              <>
                <Pencil className="w-4 h-4" />
                编辑
              </>
            )}
          </button>
        </div>

        {isEditing ? (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label htmlFor="edit-name" className="form-label">
                项目名称 <span className="text-danger">*</span>
              </label>
              <input
                id="edit-name"
                type="text"
                {...register('name')}
                className="input-field"
                maxLength={50}
              />
              {errors.name && (
                <p className="form-error">
                  <svg className="w-3.5 h-3.5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  {errors.name.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="edit-description" className="form-label">
                项目描述
              </label>
              <textarea
                id="edit-description"
                {...register('description')}
                className="input-field min-h-[120px] resize-y"
                maxLength={500}
              />
              {errors.description && (
                <p className="form-error">
                  <svg className="w-3.5 h-3.5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  {errors.description.message}
                </p>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                type="submit"
                disabled={isSubmitting}
                className="btn-primary"
              >
                {isSubmitting ? '保存中...' : '保存修改'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsEditing(false);
                  reset({ name: project.name, description: project.description || '' });
                }}
                className="btn-secondary"
              >
                取消
              </button>
            </div>
          </form>
        ) : (
          <p className="text-sm text-fg whitespace-pre-wrap">
            {project.description || '暂无描述'}
          </p>
        )}
      </div>

      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-medium text-fg">AI优化</h2>
          <button
            onClick={handleOptimize}
            disabled={optimizing}
            className="btn-secondary"
          >
            {optimizing ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                AI正在优化中...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                AI优化
              </>
            )}
          </button>
        </div>

        {optimizedContent ? (
          <div className="space-y-4">
            <div className="p-4 bg-surface-warm rounded-sm">
              <p className="text-sm text-fg whitespace-pre-wrap">{optimizedContent}</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleApply}
                className="btn-primary"
              >
                应用优化
              </button>
              <button
                onClick={handleDiscard}
                className="btn-secondary"
              >
                放弃
              </button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted">
            点击"AI优化"按钮，让AI帮您优化项目描述
          </p>
        )}
      </div>
    </div>
  );
}
