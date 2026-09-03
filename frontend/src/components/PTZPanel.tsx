import {
  ArrowDownOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
  ArrowUpOutlined,
  PauseOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons';
import { Button, Space, Typography } from 'antd';
import type { ReactNode } from 'react';

import * as api from '../api';

interface PTZPanelProps {
  deviceId: number;
}

function HoldButton({
  icon,
  onStart,
  onStop,
}: {
  icon: ReactNode;
  onStart: () => void;
  onStop: () => void;
}) {
  return (
    <Button
      icon={icon}
      onMouseDown={(e) => {
        e.preventDefault();
        onStart();
      }}
      onMouseUp={onStop}
      onMouseLeave={onStop}
      onTouchStart={(e) => {
        e.preventDefault();
        onStart();
      }}
      onTouchEnd={onStop}
    />
  );
}

export default function PTZPanel({ deviceId }: PTZPanelProps) {
  const move = (dir: 'left' | 'right' | 'up' | 'down') => () =>
    api.ptzMove(deviceId, dir).catch(() => {});
  const zoom = (dir: 'in' | 'out') => () =>
    api.ptzZoom(deviceId, dir).catch(() => {});
  const stop = () => api.ptzStop(deviceId).catch(() => {});

  return (
    <Space direction="vertical" align="center">
      <Typography.Text type="secondary">云台控制</Typography.Text>
      <Space>
        <HoldButton icon={<ArrowLeftOutlined />} onStart={move('left')} onStop={stop} />
        <HoldButton icon={<ArrowUpOutlined />} onStart={move('up')} onStop={stop} />
        <HoldButton icon={<ArrowDownOutlined />} onStart={move('down')} onStop={stop} />
        <HoldButton icon={<ArrowRightOutlined />} onStart={move('right')} onStop={stop} />
      </Space>
      <Space>
        <HoldButton icon={<ZoomOutOutlined />} onStart={zoom('out')} onStop={stop} />
        <Button icon={<PauseOutlined />} onClick={stop} />
        <HoldButton icon={<ZoomInOutlined />} onStart={zoom('in')} onStop={stop} />
      </Space>
    </Space>
  );
}
