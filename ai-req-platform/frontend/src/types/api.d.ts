// API响应基础类型
export interface ApiResponse<T> {
  ok: boolean;
  data?: T;
  error?: string;
  message?: string;
}

// 项目状态枚举
export type ProjectStatus = 'active' | 'completed' | 'archived';

// 项目类型
export interface Project {
  id: number;
  name: string;
  description: string;
  target_users: string[];
  core_functions: string[];
  key_scenarios: string[];
  architecture_snapshot: Record<string, unknown> | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

// 项目列表响应
export interface ProjectListResponse {
  data: Project[];
  total: number;
  page: number;
  page_size: number;
}

// 创建项目请求
export interface CreateProjectRequest {
  name: string;
  description?: string;
}

// 更新项目请求
export interface UpdateProjectRequest {
  name?: string;
  description?: string;
  status?: ProjectStatus;
}

// 搜索筛选参数
export interface ProjectFilters {
  search?: string;
  status?: ProjectStatus | 'all';
}

// AI设置类型
export interface AISettings {
  id: number;
  ai_api_url: string;
  ai_api_key: string;
  ai_model_name: string;
  frontend_stack: string | null;
  backend_stack: string | null;
  database_stack: string | null;
  created_at: string;
  updated_at: string;
}

// 更新AI设置请求
export interface UpdateAISettingsRequest {
  api_url: string;
  api_key: string;
  model_name: string;
}

// 测试连接响应
export interface TestConnectionResponse {
  ok: boolean;
  connected: boolean;
  message?: string;
}

// AI优化响应
export interface AOptimizeResponse {
  ok: boolean;
  optimized_description: string;
  target_users?: string[];
  core_functions?: string[];
  key_scenarios?: string[];
}
