import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { ConfigProvider, theme as antdTheme } from 'antd';
import type { ThemeConfig } from 'antd';
import { darkTheme, lightTheme, type Theme } from './colors';

type ThemeMode = 'light' | 'dark';

interface ThemeContextValue {
  mode: ThemeMode;
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used within ThemeProvider');
  return context;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(() => {
    const stored = localStorage.getItem('theme-mode');
    return (stored as ThemeMode) || 'dark';
  });

  const theme = mode === 'dark' ? darkTheme : lightTheme;

  useEffect(() => {
    localStorage.setItem('theme-mode', mode);
    document.documentElement.setAttribute('data-theme', mode);
  }, [mode]);

  const toggleTheme = () => {
    setMode(prev => prev === 'dark' ? 'light' : 'dark');
  };

  // Ant Design 主题配置
  const antdThemeConfig: ThemeConfig = {
    algorithm: mode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: theme.primary.main,
      colorSuccess: theme.status.success,
      colorWarning: theme.status.warning,
      colorError: theme.status.error,
      colorInfo: theme.status.info,
      borderRadius: 8,
      colorBgBase: theme.bg.base,
      colorTextBase: theme.text.primary,
    },
    components: {
      Layout: {
        headerBg: theme.bg.header,
        siderBg: theme.bg.elevated,
        bodyBg: theme.bg.base,
      },
      Menu: {
        darkItemBg: theme.bg.elevated,
        darkItemSelectedBg: theme.primary.dim,
        darkItemHoverBg: theme.bg.hover,
      },
      Card: {
        colorBgContainer: theme.bg.elevated,
      },
    },
  };

  return (
    <ThemeContext.Provider value={{ mode, theme, toggleTheme }}>
      <ConfigProvider theme={antdThemeConfig}>
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}
