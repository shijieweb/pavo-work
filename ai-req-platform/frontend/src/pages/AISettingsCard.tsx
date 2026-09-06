import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Settings as SettingsIcon, Wifi, WifiOff } from 'lucide-react';
import { useSettingsStore } from '@/store';
import { useToast } from '@/hooks/use-toast';
import { settingsFormSchema, type SettingsFormValues } from '@/lib/validators';
import { cn } from '@/lib/utils';

export default function AISettingsCard() {
  const { toast } = useToast();
  const { settings, fetchSettings, updateSettings, testConnection } = useSettingsStore();

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<'success' | 'error' | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsFormSchema),
  });

  useEffect(() => {
    fetchSettings().then(() => {
      if (settings) {
        reset({
          api_url: settings.ai_api_url || '',
          api_key: settings.ai_api_key || '',
          model_name: settings.ai_model_name || '',
        });
      }
    });
  }, []);

  const onSubmit = async (data: SettingsFormValues) => {
    const success = await updateSettings({
      api_url: data.api_url,
      api_key: data.api_key,
      model_name: data.model_name,
    });

    if (success) {
      toast({ title: '设置已保存', type: 'success' });
    } else {
      toast({ title: '保存失败，请重试', type: 'error' });
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);

    try {
      const connected = await testConnection();
      setTestResult(connected ? 'success' : 'error');
      if (connected) {
        toast({ title: '连接成功', type: 'success' });
      } else {
        toast({ title: '连接失败，请检查配置', type: 'error' });
      }
    } catch {
      setTestResult('error');
      toast({ title: '测试失败，请重试', type: 'error' });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="card p-6 max-w-[600px]">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-sm bg-accent/10 flex items-center justify-center">
          <SettingsIcon className="w-5 h-5 text-accent" />
        </div>
        <div>
          <h2 className="text-lg font-medium text-fg">AI模型配置</h2>
          <p className="text-sm text-muted">配置您的AI模型端点以启用优化功能</p>
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label htmlFor="api_url" className="form-label">
            API地址 <span className="text-danger">*</span>
          </label>
          <input
            id="api_url"
            type="url"
            {...register('api_url')}
            className={cn('input-field', errors.api_url && 'error')}
            placeholder="https://api.openai.com/v1"
          />
          {errors.api_url && (
            <p className="form-error">
              <svg className="w-3.5 h-3.5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              {errors.api_url.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="api_key" className="form-label">
            API Key <span className="text-danger">*</span>
          </label>
          <input
            id="api_key"
            type="password"
            {...register('api_key')}
            className={cn('input-field', errors.api_key && 'error')}
            placeholder="sk-..."
          />
          {errors.api_key && (
            <p className="form-error">
              <svg className="w-3.5 h-3.5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              {errors.api_key.message}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="model_name" className="form-label">
            模型名称 <span className="text-danger">*</span>
          </label>
          <input
            id="model_name"
            type="text"
            {...register('model_name')}
            className={cn('input-field', errors.model_name && 'error')}
            placeholder="gpt-4"
          />
          {errors.model_name && (
            <p className="form-error">
              <svg className="w-3.5 h-3.5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              {errors.model_name.message}
            </p>
          )}
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={isSubmitting}
            className="btn-primary"
          >
            {isSubmitting ? '保存中...' : '保存配置'}
          </button>
          <button
            type="button"
            onClick={handleTest}
            disabled={testing}
            className="btn-secondary"
          >
            {testing ? (
              <>
                <svg className="animate-spin w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
                </svg>
                测试中...
              </>
            ) : (
              <>
                {testResult === 'success' ? (
                  <Wifi className="w-4 h-4 text-success" />
                ) : testResult === 'error' ? (
                  <WifiOff className="w-4 h-4 text-danger" />
                ) : (
                  <Wifi className="w-4 h-4" />
                )}
                测试连接
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
