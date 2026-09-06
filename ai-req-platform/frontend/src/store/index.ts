import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Project, AISettings, ProjectFilters, ProjectStatus } from '@/types/api';
import {
  createProject as apiCreateProject,
  getProjects as apiGetProjects,
  getProject as apiGetProject,
  updateProject as apiUpdateProject,
  deleteProject as apiDeleteProject,
  optimizeProject as apiOptimizeProject,
  getSettings as apiGetSettings,
  updateAISettings as apiUpdateAISettings,
  testAIConnection as apiTestAIConnection,
} from '@/api/client';

// ===== 项目Store =====
interface ProjectState {
  projects: Project[];
  currentProject: Project | null;
  loading: boolean;
  filters: ProjectFilters;
  fetchProjects: (filters?: ProjectFilters) => Promise<void>;
  fetchProject: (id: number) => Promise<Project | null>;
  createProject: (data: { name: string; description?: string }) => Promise<Project | null>;
  updateProject: (id: number, data: { name?: string; description?: string; status?: string }) => Promise<boolean>;
  deleteProject: (id: number) => Promise<boolean>;
  optimizeProject: (id: number) => Promise<string | null>;
  setFilters: (filters: Partial<ProjectFilters>) => void;
}

export const useProjectStore = create<ProjectState>()(
  persist(
    (set, get) => ({
      projects: [],
      currentProject: null,
      loading: false,
      filters: {},

      fetchProjects: async (filters?) => {
        set({ loading: true });
        try {
          const res = await apiGetProjects(filters || get().filters);
          if (res.ok && res.data) {
            set({ projects: res.data.data });
          }
        } catch (error) {
          console.error('Failed to fetch projects:', error);
        } finally {
          set({ loading: false });
        }
      },

      fetchProject: async (id) => {
        try {
          const res = await apiGetProject(id);
          if (res.ok && res.data) {
            set({ currentProject: res.data });
            return res.data;
          }
        } catch (error) {
          console.error('Failed to fetch project:', error);
        }
        return null;
      },

      createProject: async (data) => {
        try {
          const res = await apiCreateProject(data);
          if (res.ok && res.data) {
            set((state) => ({ projects: [res.data!, ...state.projects] }));
            return res.data;
          }
        } catch (error) {
          console.error('Failed to create project:', error);
        }
        return null;
      },

      updateProject: async (id, data) => {
        try {
          const res = await apiUpdateProject(id, {
            name: data.name,
            description: data.description,
            status: data.status as ProjectStatus | undefined,
          });
          if (res.ok) {
            set((state) => ({
              projects: state.projects.map((p: Project) =>
                p.id === id ? { ...p, name: data.name || p.name, description: data.description || p.description, status: (data.status as ProjectStatus) || p.status, updated_at: new Date().toISOString() } : p
              ),
            }));
            return true;
          }
        } catch (error) {
          console.error('Failed to update project:', error);
        }
        return false;
      },

      deleteProject: async (id) => {
        try {
          const res = await apiDeleteProject(id);
          if (res.ok) {
            set((state) => ({
              projects: state.projects.filter((p) => p.id !== id),
            }));
            return true;
          }
        } catch (error) {
          console.error('Failed to delete project:', error);
        }
        return false;
      },

      optimizeProject: async (id) => {
        try {
          const res = await apiOptimizeProject(id);
          if (res.ok && res.data) {
            return res.data.optimized_description || null;
          }
        } catch (error) {
          console.error('Failed to optimize project:', error);
        }
        return null;
      },

      setFilters: (filters) => {
        set({ filters: { ...get().filters, ...filters } });
      },
    }),
    {
      name: 'project-store',
    }
  )
);

// ===== 设置Store =====
interface SettingsState {
  settings: AISettings | null;
  loading: boolean;
  fetchSettings: () => Promise<void>;
  updateSettings: (data: { api_url: string; api_key: string; model_name: string }) => Promise<boolean>;
  testConnection: () => Promise<boolean>;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      settings: null,
      loading: false,

      fetchSettings: async () => {
        set({ loading: true });
        try {
          const res = await apiGetSettings();
          if (res.ok && res.data) {
            set({ settings: res.data });
          }
        } catch (error) {
          console.error('Failed to fetch settings:', error);
        } finally {
          set({ loading: false });
        }
      },

      updateSettings: async (data) => {
        try {
          const res = await apiUpdateAISettings(data);
          if (res.ok) {
            return true;
          }
        } catch (error) {
          console.error('Failed to update settings:', error);
        }
        return false;
      },

      testConnection: async () => {
        try {
          const res = await apiTestAIConnection();
          if (res.ok && res.data) {
            return res.data.connected;
          }
        } catch (error) {
          console.error('Failed to test connection:', error);
        }
        return false;
      },
    }),
    {
      name: 'settings-store',
    }
  )
);
