# AI驱动需求管理与研发协作平台 - 设计规范

## 1. Visual Theme & Atmosphere

- **视觉主题**：Swiss Minimalism（瑞士极简风）
- **氛围关键词**：专业、克制、高效、可信
- **标杆品牌**：Linear、Notion、Stripe Dashboard
- **寄存器**：Product（产品型）— 设计服务于产品功能，而非营销展示

## 2. Color Palette & Roles

### A1-identity（品牌核心色）

| Token | 色值 | 用途 |
|-------|------|------|
| `--bg` | `#FAFAFA` | 页面背景 |
| `--surface` | `#FFFFFF` | 卡片/容器背景 |
| `--fg` | `#111827` | 主文本 |
| `--muted` | `#6B7280` | 副文本/标题 |
| `--accent` | `#4F46E5` | 品牌强调色（Slate Blue） |
| `--border` | `#E5E7EB` | 边框 |

### A2（派生色）

| Token | 色值 | 默认值来源 |
|-------|------|-----------|
| `--accent-on` | `#FFFFFF` | accent背景上的前景色 |
| `--accent-hover` | `#4338CA` | color-mix(black 8%) |
| `--accent-active` | `#3730A3` | color-mix(black 14%) |
| `--success` | `#16A34A` | 成功状态 |
| `--warn` | `#D97706` | 警告状态 |
| `--danger` | `#DC2626` | 错误状态 |

### B-slot（别名）

| Token | 映射 | 用途 |
|-------|------|------|
| `--fg-2` | `var(--fg)` | 次级文本 |
| `--surface-warm` | `#F3F4F6` | 三级表面 |
| `--meta` | `#9CA3AF` | 元数据/三级前景 |
| `--border-soft` | `#F3F4F6` | 内部行分隔 |

### 色彩使用规则

- 中性色占比 70-90%
- 强调色 `--accent` 每屏 ≤ 2处可见使用
- 语义色仅用于状态指示
- 禁止硬编码颜色值，必须通过 Token 引用

## 3. Typography Rules

### 字体栈

```css
--font-display: "Inter", "Noto Sans SC", -apple-system, sans-serif;
--font-body:    "Inter", "Noto Sans SC", -apple-system, sans-serif;
--font-mono:    "JetBrains Mono", "Fira Code", monospace;
```

### 字号层级（8级）

| Token | 大小 | 用途 |
|-------|------|------|
| `--text-xs` | 12px | 辅助信息、标签 |
| `--text-sm` | 14px | 正文、说明文字 |
| `--text-base` | 16px | 标准正文 |
| `--text-lg` | 18px | 小标题 |
| `--text-xl` | 20px | 标题 |
| `--text-2xl` | 24px | 大标题 |
| `--text-3xl` | 32px | 页面主标题 |
| `--text-4xl` | 40px | Hero/展示标题 |

### 字距规则

| 场景 | 字距 |
|------|------|
| 正文字（14-18px） | `0` |
| 小字（11-13px） | `0.01em` - `0.02em` |
| ALL CAPS | `0.06em` - `0.1em` |
| 标题（≥32px） | `-0.01em` - `-0.02em` |

### 字重系统

| 角色 | 字重 | 用途 |
|------|------|------|
| Read | 400 | 正文、描述 |
| Emphasize | 510 | 小标题、强调 |
| Announce | 590 | 大标题、CTA |

## 4. Spacing & Layout

### 间距系统（4px基准）

| Token | 值 | 用途 |
|-------|-----|------|
| `--space-1` | 4px | 最小间距 |
| `--space-2` | 8px | 组件内间距 |
| `--space-3` | 12px | 组内元素间距 |
| `--space-4` | 16px | 标准间距 |
| `--space-5` | 20px | 卡片内边距 |
| `--space-6` | 24px | 区块间距 |
| `--space-8` | 32px | 节区间距 |
| `--space-10` | 40px | 大间距 |
| `--space-12` | 48px | 节区间距（桌面） |

### 布局约束

- 容器最大宽度：`--container-max` = 1200px
- 桌面栅格：12列，沟槽 24px
- 平板栅格：8列，沟槽 16px
- 手机栅格：4列，沟槽 12px
- 节区节奏：桌面 80px / 平板 48px / 手机 32px

## 5. Border & Radius

| Token | 值 | 用途 |
|-------|-----|------|
| `--radius-sm` | 8px | 按钮、输入框 |
| `--radius-md` | 12px | 卡片、弹窗 |
| `--radius-lg` | 16px | 大容器 |
| `--radius-pill` | 9999px | 徽章、标签 |

## 6. Elevation

| Token | 值 | 用途 |
|-------|-----|------|
| `--elev-flat` | `none` | 默认层级 |
| `--elev-ring` | `0 0 0 1px var(--border)` | 边框环 |
| `--elev-raised` | `0 1px 2px rgba(0,0,0,0.04), 0 4px 8px rgba(0,0,0,0.06)` | 悬浮卡片 |

## 7. Focus & Motion

| Token | 值 | 用途 |
|-------|-----|------|
| `--focus-ring` | `0 0 0 3px rgba(79,70,229,0.3)` | 焦点环 |
| `--motion-fast` | `150ms` | 即时反馈 |
| `--motion-base` | `200ms` | 状态切换 |
| `--ease-standard` | `cubic-bezier(0.2, 0, 0, 1)` | 标准缓动 |

## 8. Component Stylings

### 按钮

| 变体 | 背景 | 文字 | 圆角 | 内边距 |
|------|------|------|------|--------|
| Primary | `var(--accent)` | `var(--accent-on)` | `--radius-sm` | 10px 16px |
| Secondary | 透明 + 1px border | `var(--accent)` | `--radius-sm` | 10px 16px |
| Ghost | `rgba(255,255,255,0.02)` | `var(--fg)` | `--radius-sm` | 舒适 |
| Danger | `var(--danger)` | `#fff` | `--radius-sm` | 10px 16px |

### 卡片

```css
background: var(--surface);
border: 1px solid var(--border);
border-radius: var(--radius-md);
padding: var(--space-5);
box-shadow: var(--elev-raised);
```

### 输入框

```css
background: var(--surface);
border: 1px solid var(--border);
border-radius: var(--radius-sm);
color: var(--fg);
padding: 8px 12px;
transition: border-color var(--motion-fast) var(--ease-standard);

&:focus {
  border-color: var(--accent);
  box-shadow: var(--focus-ring);
}

&.error {
  border-color: var(--danger);
}
```

## 9. Do's and Don'ts

### ✅ 允许的设计模式

- 纯色背景 + 品牌色光晕（opacity < 0.12）
- 几何图形装饰
- 同色系深浅渐变（如 `#4F46E5 → #4338CA`）
- 真实产品界面截图作为 Hero
- 非对称布局（Variance > 4）

### ❌ 禁止的设计模式

- 紫色→粉色渐变（`#7C3AED → #EC4899`）
- emoji 作为功能图标
- "Welcome to" / "Lorem ipsum" 等空洞占位
- 千篇一律 Hero（大标题+副标题+居中CTA+抽象3D图形）
- 硬编码颜色值
- 圆形+左边框强调的卡片模式
- 虚构指标（"10,000+用户信赖"）
- 装饰性毛玻璃效果
- 过度圆角（≥24px）
- 每节相同淡入动效

## 10. Responsive Behavior

### 断点定义

| 断点 | 宽度 | 典型设备 | 布局策略 |
|------|------|----------|----------|
| xs | <640px | 手机 | 单列，底部导航 |
| sm | ≥640px | 手机横屏 | 单列或双列 |
| md | ≥768px | 平板竖屏 | 双列，侧边导航 |
| lg | ≥1024px | 笔记本 | 多列，左侧 Sidebar |
| xl | ≥1280px | 桌面 | 完整布局 |

### 导航策略

- 移动端：底部 TabBar（≤5项）
- 桌面端：左侧 Sidebar

### 触摸目标

- 最小点击区域：44×44px

## 11. Icon System

### 锁定图标库

**lucide-react v0.469.0**

### 尺寸规范

| 场景 | 尺寸 |
|------|------|
| 行内图标 | 16px |
| 按钮内图标 | 20px |
| 独立图标 | 24px |

### 使用规则

- 统一描边风格
- 统一色值（继承当前文本颜色）
- 禁止混用其他图标库
- 禁止使用 emoji 替代图标

## 12. Agent Prompt Guide

### 给前端 Agent 的实现提示

1. **Token引用**：所有颜色、间距、圆角必须通过 CSS 变量引用，禁止硬编码
2. **图标使用**：从 `lucide-react` 导入，禁止使用 emoji
3. **状态覆盖**：每个交互组件必须覆盖 9 态（Default/Hover/Focus/Active/Disabled/Loading/Error/Empty/Success）
4. **无障碍**：focus-visible ring、键盘可达、ARIA标签
5. **响应式**：mobile-first，断点使用 Tailwind 预设
6. **文件组织**：单文件 ≤ 300 行，按功能分包

### 关键注意点

- Hero 区域展示真实产品界面，不用口号+抽象图形
- 空状态必须有引导文案和操作按钮
- 错误状态必须包含具体错误信息和重试按钮
- AI优化加载时显示 spinner + 禁用按钮防重复提交
- 表单验证实时显示，错误信息在字段下方

---

*设计规范版本：v1.0*
*撰写人：颜好看（UI/UX设计师）*
*日期：2026-08-23*
