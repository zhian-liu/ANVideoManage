import { LockOutlined, UserOutlined, BulbOutlined, BulbFilled } from '@ant-design/icons';
import { Button, Card, Form, Input, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';

import { useAuth } from '../store/auth';
import { useTheme } from '../theme/ThemeProvider';
import { useMousePosition } from '../hooks/useAnimations';

interface LoginForm {
  username: string;
  password: string;
}

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { mode, theme, toggleTheme } = useTheme();
  const [form] = Form.useForm<LoginForm>();
  const [isLoading, setIsLoading] = useState(false);
  const mousePosition = useMousePosition();

  const onFinish = async (values: LoginForm) => {
    setIsLoading(true);
    try {
      await login(values.username, values.password);
      message.success('登录成功！');
      navigate('/', { replace: true });
    } catch {
      message.error('用户名或密码错误');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: mode === 'dark'
          ? 'linear-gradient(135deg, #0A0D12 0%, #0F131C 50%, #161D2B 100%)'
          : 'linear-gradient(135deg, #F8FAFC 0%, #E2E8F0 100%)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* 背景装饰 - 跟随鼠标移动 */}
      <div
        style={{
          position: 'absolute',
          top: '-50%',
          left: '-10%',
          width: '500px',
          height: '500px',
          borderRadius: '50%',
          background: `radial-gradient(circle, ${theme.primary.main}30 0%, transparent 70%)`,
          filter: 'blur(60px)',
          animation: 'float 8s ease-in-out infinite',
          transform: `translate(${mousePosition.x * 0.02}px, ${mousePosition.y * 0.02}px)`,
          transition: 'transform 0.3s ease-out',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: '-30%',
          right: '-10%',
          width: '400px',
          height: '400px',
          borderRadius: '50%',
          background: `radial-gradient(circle, ${theme.accent.main}30 0%, transparent 70%)`,
          filter: 'blur(60px)',
          animation: 'float 10s ease-in-out infinite reverse',
          transform: `translate(${mousePosition.x * -0.03}px, ${mousePosition.y * -0.03}px)`,
          transition: 'transform 0.3s ease-out',
        }}
      />

      {/* 网格背景 */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: mode === 'dark'
            ? 'linear-gradient(rgba(56, 189, 248, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(56, 189, 248, 0.05) 1px, transparent 1px)'
            : 'linear-gradient(rgba(14, 165, 233, 0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(14, 165, 233, 0.08) 1px, transparent 1px)',
          backgroundSize: '50px 50px',
          opacity: 0.5,
        }}
      />

      <style>
        {`
          @keyframes float {
            0%, 100% {
              transform: translate(0, 0) scale(1);
            }
            50% {
              transform: translate(20px, -20px) scale(1.1);
            }
          }
        `}
      </style>

      {/* 主题切换按钮 */}
      <Button
        type="text"
        size="large"
        icon={mode === 'dark' ? <BulbFilled /> : <BulbOutlined />}
        onClick={toggleTheme}
        className="ripple"
        style={{
          position: 'absolute',
          top: 24,
          right: 24,
          color: theme.text.secondary,
          background: theme.bg.elevated,
          border: `1px solid ${theme.border.default}`,
          borderRadius: 12,
          width: 48,
          height: 48,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 20,
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
          transition: 'all 0.3s',
          zIndex: 10,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'rotate(15deg) scale(1.1)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'rotate(0deg) scale(1)';
        }}
      />

      {/* 登录卡片 */}
      <Card
        className="slide-in-up"
        style={{
          width: 420,
          background: theme.bg.elevated,
          border: `1px solid ${theme.border.default}`,
          borderRadius: 16,
          boxShadow: mode === 'dark'
            ? '0 20px 60px rgba(0, 0, 0, 0.4)'
            : '0 20px 60px rgba(0, 0, 0, 0.1)',
          backdropFilter: 'blur(10px)',
          position: 'relative',
          zIndex: 1,
        }}
        bordered={false}
      >
        {/* Logo 和标题 */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div
            className="scale-pulse"
            style={{
              width: 72,
              height: 72,
              margin: '0 auto 16px',
              borderRadius: 16,
              background: `linear-gradient(135deg, ${theme.primary.main} 0%, ${theme.accent.main} 100%)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 36,
              boxShadow: `0 8px 24px ${theme.primary.dim}`,
            }}
          >
            📹
          </div>
          <h2
            style={{
              fontSize: 24,
              fontWeight: 700,
              color: theme.text.primary,
              margin: 0,
              marginBottom: 8,
            }}
          >
            视频监控管理平台
          </h2>
          <p style={{ color: theme.text.tertiary, margin: 0, fontSize: 14 }}>
            Video Surveillance Management System
          </p>
        </div>

        {/* 登录表单 */}
        <Form form={form} onFinish={onFinish} initialValues={{ username: 'admin' }} size="large">
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              prefix={<UserOutlined style={{ color: theme.text.tertiary }} />}
              placeholder="用户名"
              style={{
                borderRadius: 8,
                background: theme.bg.hover,
                border: `1px solid ${theme.border.default}`,
              }}
            />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: theme.text.tertiary }} />}
              placeholder="密码"
              style={{
                borderRadius: 8,
                background: theme.bg.hover,
                border: `1px solid ${theme.border.default}`,
              }}
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              type="primary"
              htmlType="submit"
              block
              loading={isLoading}
              className="ripple gradient-animate"
              style={{
                height: 48,
                borderRadius: 8,
                fontSize: 16,
                fontWeight: 600,
                background: `linear-gradient(135deg, ${theme.primary.main} 0%, ${theme.accent.main} 100%)`,
                border: 'none',
                boxShadow: `0 4px 16px ${theme.primary.dim}`,
                transition: 'all 0.3s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = `0 6px 20px ${theme.primary.main}50`;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = `0 4px 16px ${theme.primary.dim}`;
              }}
            >
              {isLoading ? '登录中...' : '登录'}
            </Button>
          </Form.Item>
        </Form>

        {/* 底部提示 */}
        <div
          style={{
            marginTop: 24,
            padding: 16,
            borderRadius: 8,
            background: theme.bg.hover,
            border: `1px solid ${theme.border.default}`,
          }}
        >
          <div style={{ fontSize: 12, color: theme.text.tertiary, textAlign: 'center' }}>
            💡 默认账号: <code style={{
              padding: '2px 6px',
              background: theme.bg.base,
              borderRadius: 4,
              color: theme.text.secondary,
              fontFamily: 'Monaco, Consolas, monospace',
            }}>admin / admin123</code>
          </div>
        </div>
      </Card>
    </div>
  );
}
