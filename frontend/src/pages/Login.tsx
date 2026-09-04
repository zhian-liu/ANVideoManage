import { LockOutlined, UserOutlined, BulbOutlined, BulbFilled } from '@ant-design/icons';
import { Button, Card, Form, Input, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';

import { useAuth } from '../store/auth';
import { useTheme } from '../theme/ThemeProvider';
import InkLandscape from '../components/InkLandscape';

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
        background: theme.bg.base,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <InkLandscape theme={theme} className="ink-landscape--login" />

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
          <div className="login-brand-mark scale-pulse">
            <img src="/an-video-manage-logo.png" alt="ANVideoManage" />
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
            ANVideoManage
          </h2>
          <p style={{ color: theme.text.tertiary, margin: 0, fontSize: 14 }}>
            Video Management Platform
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
              className="ripple"
              style={{
                height: 48,
                borderRadius: 8,
                fontSize: 16,
                fontWeight: 600,
                background: theme.primary.main,
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
