import { Button, Card, DatePicker, Empty, List, Select, Space } from 'antd';
import dayjs from 'dayjs';
import type { Dayjs } from 'dayjs';
import { useEffect, useState } from 'react';

import * as api from '../api';
import type { Device, Recording } from '../api/types';
import VideoPlayer from '../components/VideoPlayer';

export default function Playback() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [deviceId, setDeviceId] = useState<number | undefined>();
  const [range, setRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [playing, setPlaying] = useState<Recording | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.listDevices().then(setDevices).catch(() => {});
  }, []);

  const query = async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = {};
      if (deviceId) params.device_id = deviceId;
      if (range) {
        params.start = range[0].toISOString();
        params.end = range[1].toISOString();
      }
      setRecordings(await api.listRecordings(params));
    } finally {
      setLoading(false);
    }
  };

  const duration = (r: Recording) =>
    Math.max(
      0,
      Math.round(
        (new Date(r.end_time).getTime() - new Date(r.start_time).getTime()) / 1000
      )
    );

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            style={{ width: 200 }}
            placeholder="选择设备"
            allowClear
            value={deviceId}
            onChange={(v) => setDeviceId(v)}
            options={devices.map((d) => ({ value: d.id, label: d.name }))}
          />
          <DatePicker.RangePicker
            showTime
            value={range}
            onChange={(v) => setRange(v as [Dayjs, Dayjs] | null)}
          />
          <Button type="primary" onClick={query} loading={loading}>
            查询
          </Button>
        </Space>
      </Card>

      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        <Card title="录像列表" style={{ width: 380 }}>
          <List
            dataSource={recordings}
            locale={{ emptyText: <Empty description="暂无录像，请调整查询条件" /> }}
            renderItem={(r) => (
              <List.Item
                onClick={() => setPlaying(r)}
                style={{
                  cursor: 'pointer',
                  background: playing?.id === r.id ? '#e6f4ff' : undefined,
                }}
              >
                <List.Item.Meta
                  title={dayjs(r.start_time).format('YYYY-MM-DD HH:mm:ss')}
                  description={`时长 ${duration(r)} 秒 · ${(r.file_size / 1024 / 1024).toFixed(1)} MB`}
                />
              </List.Item>
            )}
          />
        </Card>
        <Card title="回放" style={{ flex: 1 }}>
          {playing ? (
            <VideoPlayer
              url={api.recordingFileUrl(playing.id)}
              live={false}
              muted={false}
            />
          ) : (
            <Empty description="请选择左侧录像进行回放" />
          )}
        </Card>
      </div>
    </div>
  );
}
