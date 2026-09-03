// 深色主题调色板 - 基于青蓝色调
export const darkTheme = {
  // 背景层级 - 从最深到最浅
  bg: {
    base: '#0A0D12',      // 基础背景
    elevated: '#0F131C',  // 卡片/面板
    hover: '#161D2B',     // 悬停状态
    active: '#1E2636',    // 激活状态
    header: '#0D1117',    // 头部背景
  },
  // 主色 - 青蓝色
  primary: {
    main: '#38BDF8',      // 主色
    hover: '#7DD3FC',     // 悬停
    active: '#0EA5E9',    // 激活
    dim: 'rgba(56, 189, 248, 0.1)', // 半透明背景
  },
  // 辅助色 - 翡翠绿
  accent: {
    main: '#6EE7B7',
    hover: '#A7F3D0',
    dim: 'rgba(110, 231, 183, 0.1)',
  },
  // 文字颜色
  text: {
    primary: '#F8FAFC',
    secondary: '#94A3B8',
    tertiary: '#64748B',
    inverse: '#0F172A',
  },
  // 边框
  border: {
    default: 'rgba(148, 163, 184, 0.1)',
    hover: 'rgba(148, 163, 184, 0.2)',
  },
  // 状态色
  status: {
    success: '#6EE7B7',
    warning: '#FCD34D',
    error: '#F87171',
    info: '#38BDF8',
  },
};

// 亮色主题调色板
export const lightTheme = {
  bg: {
    base: '#FFFFFF',
    elevated: '#F8FAFC',
    hover: '#F1F5F9',
    active: '#E2E8F0',
    header: '#FFFFFF',
  },
  primary: {
    main: '#0EA5E9',
    hover: '#0284C7',
    active: '#0C4A6E',
    dim: 'rgba(14, 165, 233, 0.1)',
  },
  accent: {
    main: '#10B981',
    hover: '#059669',
    dim: 'rgba(16, 185, 129, 0.1)',
  },
  text: {
    primary: '#0F172A',
    secondary: '#475569',
    tertiary: '#64748B',
    inverse: '#FFFFFF',
  },
  border: {
    default: '#E2E8F0',
    hover: '#CBD5E1',
  },
  status: {
    success: '#10B981',
    warning: '#F59E0B',
    error: '#EF4444',
    info: '#0EA5E9',
  },
};

export type Theme = typeof darkTheme;
