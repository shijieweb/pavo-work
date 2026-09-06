import { z } from 'zod';

// 项目表单验证Schema
export const projectFormSchema = z.object({
  name: z
    .string()
    .min(1, '项目名称不能为空，长度2-50字符')
    .min(2, '项目名称不能为空，长度2-50字符')
    .max(50, '项目名称不能为空，长度2-50字符'),
  description: z
    .string()
    .max(500, '项目简介不能超过500字符')
    .optional()
    .or(z.literal('')),
});

export type ProjectFormValues = z.infer<typeof projectFormSchema>;

// AI设置表单验证Schema
export const settingsFormSchema = z.object({
  api_url: z
    .string()
    .min(1, '请输入有效的API地址（以http或https开头）')
    .url('请输入有效的API地址（以http或https开头）')
    .refine((val) => val.startsWith('http://') || val.startsWith('https://'), {
      message: '请输入有效的API地址（以http或https开头）',
    }),
  api_key: z
    .string()
    .min(1, 'API Key不能为空且长度不能少于10字符')
    .min(10, 'API Key不能为空且长度不能少于10字符'),
  model_name: z
    .string()
    .min(1, '模型名称格式不正确')
    .regex(/^[a-zA-Z0-9_]+$/, '模型名称格式不正确'),
});

export type SettingsFormValues = z.infer<typeof settingsFormSchema>;
