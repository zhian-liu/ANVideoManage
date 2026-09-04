import type { ReactElement } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Spin } from 'antd';

import MainLayout from './layouts/MainLayout';
import Dashboard from './pages/Dashboard';
import Devices from './pages/Devices';
import Live from './pages/Live';
import Login from './pages/Login';
import Playback from './pages/Playback';
import Settings from './pages/Settings';
import { useAuth } from './store/auth';

function RequireAuth({ children }: { children: ReactElement }) {
  const { token, loading } = useAuth();
  if (loading) {
    return (
      <div
        style={{
          height: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Spin size="large" />
      </div>
    );
  }
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <MainLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="live" element={<Live />} />
        <Route path="playback" element={<Playback />} />
        <Route path="devices" element={<Devices />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
