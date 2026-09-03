import { AppstoreOutlined, BorderOutlined, ReloadOutlined } from '@ant-design/icons';
import { Button, Card, Empty, Modal, Tree } from 'antd';
import type { DataNode } from 'antd/es/tree';
import { useCallback, useEffect, useState } from 'react';

import * as api from '../api';
import type { Device, StreamInfo } from '../api/types';
import PTZPanel from '../components/PTZPanel';
import VideoPlayer from '../components/VideoPlayer';
import { useTheme } from '../theme/ThemeProvider';

type LayoutType = 1 | 4 | 9 | 16;

export default function Live() {
  const { theme } = useTheme();
  const [devices, setDevices] = useState<Device[]>([]);
  const [streams, setStreams] = useState<Record<number, StreamInfo>>({});
  const [selected, setSelected] = useState<Device | null>(null);
  const [loading, setLoading] = useState(false);
  const [layout, setLayout] = useState<LayoutType>(4);
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<number[]>([]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const ds = await api.listDevices();
      setDevices(ds);
      const infos = await Promise.all(
        ds.filter((d) => d.enabled).map((d) => api.getStreamInfo(d.id).catch(() => null))
      );
      const map: Record<number, StreamInfo> = {};
      infos.forEach((info) => {
        if (info) map[info.device_id] = info;
      });
      setStreams(map);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const enabledDevices = devices.filter((d) => d.enabled);

  // 构建设备树数据
  const treeData: DataNode[] = enabledDevices.map((d) => ({
    key: d.id.toString(),
    title: d.name,
    icon: streams[d.id]?.online ? (
      <span style={{ color: '#52c41a' }}>●</span>
    ) : (
      <span style={{ color: '#d9d9d9' }}>●</span>
    ),
  }));

  // 处理设备选择
  const onDeviceSelect = (selectedKeys: React.Key[]) => {
    const ids = selectedKeys.map((k) => parseInt(k.toString())).filter((id) => !isNaN(id));
    setSelectedDeviceIds(ids.slice(0, layout));
  };

  // 处理双击设备 - 打开详情弹窗
  const onDeviceDoubleClick = (deviceId: number) => {
    const device = devices.find((d) => d.id === deviceId);
    if (device) {
      setSelected(device);
    }
  };

  // 获取布局列数
  const getLayoutCols = (type: LayoutType): number => {
    switch (type) {
      case 1:
        return 1;
      case 4:
        return 2;
      case 9:
        return 3;
      case 16:
        return 4;
    }
  };

  // 渲染视频窗口
  const renderVideoGrid = () => {
    const cols = getLayoutCols(layout);
    const cells: JSX.Element[] = [];

    for (let i = 0; i < layout; i++) {
      const deviceId = selectedDeviceIds[i];
      const device = deviceId ? devices.find((d) => d.id === deviceId) : null;
      const info = device ? streams[device.id] : null;

      cells.push(
        <div
          key={i}
          className="video-cell"
          style={{
            position: 'relative',
            aspectRatio: '16 / 9',
            background: theme.bg.base,
            border: `2px solid ${theme.border.default}`,
            borderRadius: 8,
            overflow: 'hidden',
            cursor: device ? 'pointer' : 'default',
            transition: 'all 0.3s',
          }}
          onClick={() => device && onDeviceDoubleClick(device.id)}
          onMouseEnter={(e) => {
            if (device) {
              e.currentTarget.style.transform = 'scale(1.02)';
              e.currentTarget.style.borderColor = theme.primary.main;
              e.currentTarget.style.boxShadow = `0 4px 16px ${theme.primary.dim}`;
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'scale(1)';
            e.currentTarget.style.borderColor = theme.border.default;
            e.currentTarget.style.boxShadow = 'none';
          }}
        >
          {device && info?.online ? (
            <>
              <VideoPlayer url={info.flv_url} live muted />
              <div
                style={{
                  position: 'absolute',
                  top: 8,
                  left: 8,
                  zIndex: 2,
                  padding: '4px 12px',
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: 600,
                  color: '#fff',
                  background: 'rgba(0,0,0,0.7)',
                  backdropFilter: 'blur(4px)',
                }}
              >
                {device.name}
              </div>
            </>
          ) : device ? (
            <div
              style={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                color: theme.text.tertiary,
                gap: 8,
              }}
            >
              <div style={{ fontSize: 32 }}>📹</div>
              <div>{device.name}</div>
              <div style={{ fontSize: 12 }}>设备离线</div>
            </div>
          ) : (
            <div
              style={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                color: theme.text.tertiary,
                gap: 8,
              }}
            >
              <div style={{ fontSize: 32 }}>📺</div>
              <div style={{ fontSize: 12 }}>窗口 {i + 1}</div>
            </div>
          )}
        </div>
      );
    }

    return (
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${cols}, 1fr)`,
          gap: 12,
          padding: 16,
        }}
      >
        {cells}
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 64px)', gap: 16, padding: 16 }}>
      {/* 左侧设备树 */}
      <Card
        title="实时预览"
        extra={
          <Button icon={<ReloadOutlined />} loading={loading} onClick={refresh} size="small">
            刷新
          </Button>
        }
        style={{
          width: 280,
          height: '100%',
          background: theme.bg.elevated,
          border: `1px solid ${theme.border.default}`,
        }}
        bodyStyle={{
          padding: '12px 0',
          height: 'calc(100% - 57px)',
          overflow: 'auto',
        }}
      >
        {enabledDevices.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无启用设备"
            style={{ marginTop: 60 }}
          />
        ) : (
          <Tree
            showIcon
            treeData={treeData}
            onSelect={onDeviceSelect}
            selectedKeys={selectedDeviceIds.map((id) => id.toString())}
            style={{
              background: 'transparent',
              color: theme.text.primary,
            }}
          />
        )}
      </Card>

      {/* 右侧视频区域 */}
      <Card
        style={{
          flex: 1,
          height: '100%',
          background: theme.bg.elevated,
          border: `1px solid ${theme.border.default}`,
          position: 'relative',
        }}
        bodyStyle={{
          padding: 0,
          height: '100%',
          overflow: 'auto',
        }}
      >
        {renderVideoGrid()}

        {/* 布局切换按钮 - 右下角 */}
        <div
            className="slide-in-up"
            style={{
              position: 'absolute',
              bottom: 20,
              right: 20,
              display: 'flex',
              gap: 8,
              background: theme.bg.elevated,
              padding: 8,
              borderRadius: 12,
              border: `1px solid ${theme.border.default}`,
              boxShadow: '0 4px 16px rgba(0, 0, 0, 0.1)',
            }}
          >
            <Button
              type={layout === 1 ? 'primary' : 'default'}
              icon={<BorderOutlined />}
              onClick={() => {
                setLayout(1);
                setSelectedDeviceIds((prev) => prev.slice(0, 1));
              }}
              style={{
                background: layout === 1 ? theme.primary.main : theme.bg.elevated,
                borderColor: layout === 1 ? theme.primary.main : theme.border.default,
              }}
            >
              单窗口
            </Button>
            <Button
              type={layout === 4 ? 'primary' : 'default'}
              icon={<AppstoreOutlined />}
              onClick={() => {
                setLayout(4);
                setSelectedDeviceIds((prev) => prev.slice(0, 4));
              }}
              style={{
                background: layout === 4 ? theme.primary.main : theme.bg.elevated,
                borderColor: layout === 4 ? theme.primary.main : theme.border.default,
              }}
            >
              4窗口
            </Button>
            <Button
              type={layout === 9 ? 'primary' : 'default'}
              icon={<AppstoreOutlined />}
              onClick={() => {
                setLayout(9);
                setSelectedDeviceIds((prev) => prev.slice(0, 9));
              }}
              style={{
                background: layout === 9 ? theme.primary.main : theme.bg.elevated,
                borderColor: layout === 9 ? theme.primary.main : theme.border.default,
              }}
            >
              9窗口
            </Button>
            <Button
              type={layout === 16 ? 'primary' : 'default'}
              icon={<AppstoreOutlined />}
              onClick={() => {
                setLayout(16);
                setSelectedDeviceIds((prev) => prev.slice(0, 16));
              }}
              style={{
                background: layout === 16 ? theme.primary.main : theme.bg.elevated,
                borderColor: layout === 16 ? theme.primary.main : theme.border.default,
              }}
            >
              16窗口
            </Button>
          </div>
        )
      </Card>

      {/* 设备详情弹窗 */}
      <Modal
        open={!!selected}
        onCancel={() => setSelected(null)}
        footer={null}
        title={selected?.name}
        width={820}
        destroyOnClose
      >
        {selected && (
          <div style={{ display: 'flex', gap: 16 }}>
            <div
              style={{
                flex: 1,
                aspectRatio: '16 / 9',
                background: '#000',
                borderRadius: 4,
                overflow: 'hidden',
              }}
            >
              {streams[selected.id]?.online ? (
                <VideoPlayer url={streams[selected.id].flv_url} live muted={false} />
              ) : (
                <div
                  style={{
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#999',
                  }}
                >
                  离线
                </div>
              )}
            </div>
            {selected.ptz_enabled && <PTZPanel deviceId={selected.id} />}
          </div>
        )}
      </Modal>
    </div>
  );
}
