import AISettingsCard from './AISettingsCard';

export default function Settings() {
  return (
    <div className="max-w-[800px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-medium text-fg tracking-tight">设置</h1>
        <p className="text-sm text-muted mt-1">配置AI模型和系统参数</p>
      </div>

      <AISettingsCard />
    </div>
  );
}
