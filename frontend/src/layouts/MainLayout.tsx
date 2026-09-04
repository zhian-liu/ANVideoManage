import {
  DashboardOutlined,
  DatabaseOutlined,
  LogoutOutlined,
  PlaySquareOutlined,
  SettingOutlined,
  UserOutlined,
  VideoCameraOutlined,
  BulbOutlined,
  BulbFilled,
} from '@ant-design/icons';
import { Avatar, Dropdown, Layout, Menu, Button, Space, Badge } from 'antd';
import type { MenuProps } from 'antd';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../store/auth';
import { useTheme } from '../theme/ThemeProvider';
import InkLandscape from '../components/InkLandscape';

const { Header, Sider, Content } = Layout;

const menuItems: MenuProps['items'] = [
  { key: '/', icon: <DashboardOutlined />, label: '设备总览' },
  { key: '/live', icon: <VideoCameraOutlined />, label: '实时预览' },
  { key: '/playback', icon: <PlaySquareOutlined />, label: '录像回放' },
  { key: '/devices', icon: <DatabaseOutlined />, label: '设备管理' },
  { key: '/settings', icon: <SettingOutlined />, label: '设置' },
];

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { mode, theme, toggleTheme } = useTheme();

  const selectedKey = location.pathname || '/';

  const userMenu: MenuProps['items'] = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: () => {
        logout();
        navigate('/login');
      },
    },
  ];

  return (
    <div
      style={{
        position: 'relative',
        minHeight: '100vh',
        background: theme.bg.base,
      }}
    >
      <InkLandscape theme={theme} />
      <Layout style={{ minHeight: '100vh', position: 'relative', zIndex: 1, background: 'transparent' }}>
      <Sider
        width={220}
        style={{
          background: `${theme.bg.elevated}e8`,
          borderRight: `1px solid ${theme.border.default}`,
          boxShadow: '2px 0 8px rgba(0, 0, 0, 0.08)',
        }}
      >
        {/* Logo 区域 */}
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '0 20px',
            borderBottom: `1px solid ${theme.border.default}`,
            background: `${theme.bg.header}e8`,
            cursor: 'pointer',
          }}
          onClick={() => navigate('/')}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <div className="brand-mark scale-pulse">
              <img src="/an-video-manage-logo.png" alt="ANVideoManage" />
            </div>
            <div>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 700,
                  color: theme.text.primary,
                  lineHeight: 1.2,
                }}
              >
                ANVideoManage
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: theme.text.tertiary,
                  marginTop: 2,
                }}
              >
                Video Management
              </div>
            </div>
          </div>
        </div>

        {/* 菜单 */}
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(String(key))}
          style={{
            background: 'transparent',
            border: 'none',
            marginTop: 12,
          }}
        />

        {/* 底部信息 */}
        <div
          style={{
            position: 'absolute',
            bottom: 20,
            left: 20,
            right: 20,
            padding: 12,
            background: theme.bg.hover,
            borderRadius: 8,
            border: `1px solid ${theme.border.default}`,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="status-indicator status-online"></span>
            <span style={{ fontSize: 12, color: theme.text.secondary }}>
              系统运行正常
            </span>
          </div>
        </div>
      </Sider>

      <Layout style={{ background: 'transparent' }}>
        {/* 顶部导航 */}
        <Header
          style={{
            background: `${theme.bg.header}e8`,
            padding: '0 32px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: `1px solid ${theme.border.default}`,
            boxShadow: '0 1px 4px rgba(0, 0, 0, 0.04)',
            height: 64,
          }}
        >
          {/* 面包屑或页面标题 */}
          <div style={{ fontSize: 18, fontWeight: 500, color: theme.text.primary }}>
            {selectedKey === '/' && '设备总览'}
            {selectedKey === '/live' && '实时预览'}
            {selectedKey === '/playback' && '录像回放'}
            {selectedKey === '/devices' && '设备管理'}
            {selectedKey === '/settings' && '设置'}
            {!['/','/live','/playback','/devices','/settings'].includes(selectedKey) && '设备总览'}
          </div>

          {/* 右侧工具栏 */}
          <Space size={16}>
            {/* 主题切换按钮 */}
            <Button
              type="text"
              icon={mode === 'dark' ? <BulbFilled /> : <BulbOutlined />}
              onClick={toggleTheme}
              style={{
                color: theme.text.secondary,
                borderRadius: 8,
                transition: 'all 0.25s',
              }}
            />

            {/* 通知 */}
            <Badge count={0} showZero={false}>
              <Button
                type="text"
                shape="circle"
                style={{
                  color: theme.text.secondary,
                }}
              >
                🔔
              </Button>
            </Badge>

            {/* 用户菜单 */}
            <Dropdown menu={{ items: userMenu }} placement="bottomRight">
              <Space style={{ cursor: 'pointer' }}>
                <Avatar
                  size={32}
                  icon={<UserOutlined />}
                  style={{
                    background: theme.primary.main,
                    color: theme.text.inverse,
                  }}
                />
                <span style={{ color: theme.text.primary, fontWeight: 500 }}>
                  {user?.username ?? '用户'}
                </span>
              </Space>
            </Dropdown>
          </Space>
        </Header>

        {/* 主内容区 */}
        <Content
          style={{
            margin: 24,
            padding: 24,
            background: `${theme.bg.base}b8`,
            backdropFilter: 'blur(2px)',
            minHeight: 'calc(100vh - 112px)',
          }}
        >
          <div className="fade-in">
            <Outlet />
          </div>
        </Content>
      </Layout>
      </Layout>
    </div>
  );
}
