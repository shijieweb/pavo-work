import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Sparkles } from 'lucide-react';
import { useProjectStore } from '@/store';
import { useToast } from '@/hooks/use-toast';
import apiClient from '@/api/client';

export default function ProjectNew() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { createProject } = useProjectStore();
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [optimizationResult, setOptimizationResult] = useState<{
    description: string;
    target_users: string[];
    core_functions: string[];
    key_scenarios: string[];
  } | null>(null);

  const handleOptimize = async () => {
    const nameEl = document.getElementById('name') as HTMLInputElement;
    const descEl = document.getElementById('description') as HTMLTextAreaElement;

    if (!nameEl?.value.trim()) {
      toast({ title: '请先输入项目名称', type: 'error' });
      return;
    }

    const currentDesc = descEl?.value || '';
    if (!currentDesc.trim()) {
      toast({ title: '请先输入项目简介草稿', type: 'error' });
      return;
    }

    setIsOptimizing(true);
    try {
      const response = await apiClient.post('/ai/generate-description', {
        project_name: nameEl.value,
        user_input: currentDesc,
      });

      if (response.data.success) {
        setOptimizationResult({
          description: response.data.generated_description || currentDesc,
          target_users: [],
          core_functions: [],
          key_scenarios: [],
        });
        toast({ title: 'AI优化完成，可预览后应用', type: 'success' });
      } else {
        toast({ title: response.data.message || '优化失败', type: 'error' });
      }
    } catch (error: any) {
      const msg = error?.response?.data?.detail || '优化失败，请检查AI配置';
      toast({ title: msg, type: 'error' });
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleApplyOptimization = () => {
    if (optimizationResult) {
      const descEl = document.getElementById('description') as HTMLTextAreaElement;
      if (descEl) {
        descEl.value = optimizationResult.description;
        setOptimizationResult(null);
        toast({ title: '已应用AI优化结果', type: 'success' });
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const name = formData.get('name') as string;
    const description = formData.get('description') as string;

    if (!name.trim()) {
      toast({ title: '项目名称不能为空，长度2-50字符', type: 'error' });
      return;
    }

    if (name.length < 2 || name.length > 50) {
      toast({ title: '项目名称不能为空，长度2-50字符', type: 'error' });
      return;
    }

    if (description.length > 500) {
      toast({ title: '项目简介不能超过500字符', type: 'error' });
      return;
    }

    const project = await createProject({ name, description });
    if (project) {
      toast({ title: '项目创建成功', type: 'success' });
      navigate(`/projects/${project.id}`);
    } else {
      toast({ title: '创建失败，请重试', type: 'error' });
    }
  };

  return (
    <div className="max-w-[640px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <button
        onClick={() => navigate(-1)}
        className="btn-ghost mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        返回列表
      </button>

      <div className="mb-8">
        <h1 className="text-2xl font-medium text-fg tracking-tight">新建项目</h1>
        <p className="text-sm text-muted mt-1">填写项目基本信息，AI将帮助您优化需求描述</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label htmlFor="name" className="form-label">
            项目名称 <span className="text-danger">*</span>
          </label>
          <input
            id="name"
            name="name"
            type="text"
            className="input-field"
            placeholder="例如：电商平台重构项目"
            maxLength={50}
            required
            minLength={2}
          />
        </div>

        <div>
          <label htmlFor="description" className="form-label">
            项目简介 <span className="text-muted">(可输入草稿，AI会优化)</span>
          </label>
          <textarea
            id="description"
            name="description"
            className="input-field min-h-[120px] resize-y"
            placeholder="简要描述项目目标、核心功能和关键场景..."
            maxLength={500}
          />
          <div className="flex items-center justify-between mt-1">
            <span />
            <span className="text-xs text-meta">0/500</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleOptimize}
            disabled={isOptimizing}
            className="btn-secondary flex items-center gap-2"
          >
            {isOptimizing ? (
              <>
                <span className="animate-spin">⟳</span>
                优化中...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                AI优化简介
              </>
            )}
          </button>
        </div>

        {optimizationResult && (
          <div className="p-4 bg-surface-warm rounded-md border border-border">
            <p className="text-sm text-fg-2 mb-3 whitespace-pre-wrap">
              {optimizationResult.description}
            </p>
            <button
              type="button"
              onClick={handleApplyOptimization}
              className="btn-primary text-sm py-1.5 px-3"
            >
              应用此优化
            </button>
          </div>
        )}

        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            className="btn-primary"
          >
            创建项目
          </button>
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="btn-secondary"
          >
            取消
          </button>
        </div>
      </form>
    </div>
  );
}

