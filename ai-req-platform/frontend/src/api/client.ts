import axios from 'axios';
import type {
  ApiResponse,
  AISettings,
  UpdateAISettingsRequest,
  TestConnectionResponse,
  AOptimizeResponse,
  ProjectListResponse,
  CreateProjectRequest,
  UpdateProjectRequest,
  ProjectFilters,
  Project,
} from '@/types/api';

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 添加认证Token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('app_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器 - 统一错误处理
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.message || '请求失败，请重试';
    return Promise.reject(new Error(message));
  }
);

export default apiClient;

// ===== AI设置 API =====
export const getSettings = (): Promise<ApiResponse<AISettings>> => {
  return apiClient.get('/settings');
};

export const updateAISettings = (
  data: UpdateAISettingsRequest
): Promise<ApiResponse<null>> => {
  return apiClient.put('/settings/ai-model', data);
};

export const testAIConnection = (): Promise<ApiResponse<TestConnectionResponse>> => {
  return apiClient.post('/settings/ai-model/test');
};

// ===== 项目 API =====
export const createProject = (
  data: CreateProjectRequest
): Promise<ApiResponse<Project>> => {
  return apiClient.post('/projects', data);
};

export const getProjects = (
  params?: ProjectFilters
): Promise<ApiResponse<ProjectListResponse>> => {
  return apiClient.get('/projects', { params });
};

export const getProject = (id: number): Promise<ApiResponse<Project>> => {
  return apiClient.get(`/projects/${id}`);
};

export const updateProject = (
  id: number,
  data: UpdateProjectRequest
): Promise<ApiResponse<null>> => {
  return apiClient.put(`/projects/${id}`, data);
};

export const deleteProject = (id: number): Promise<ApiResponse<null>> => {
  return apiClient.delete(`/projects/${id}`);
};

// ===== AI API =====
export const optimizeProject = (
  projectId: number
): Promise<ApiResponse<AOptimizeResponse>> => {
  return apiClient.post('/ai/optimize-project', { project_id: projectId });
};

export const generateProjectDescription = (
  data: { project_name: string; user_input?: string }
): Promise<ApiResponse<{ generated_description: string; suggestion?: string }>> => {
  return apiClient.post('/ai/generate-description', data);
};
