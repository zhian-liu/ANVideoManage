import { DeleteOutlined } from '@ant-design/icons';
import {
  Button,
  Card,
  Checkbox,
  DatePicker,
  Empty,
  List,
  Modal,
  Select,
  Space,
  message,
} from 'antd';
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
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [deleting, setDeleting] = useState(false);
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
      setSelectedIds([]);
    } finally {
      setLoading(false);
    }
  };

  const deleteSelected = async () => {
    setDeleting(true);
    try {
      const results = await Promise.allSettled(
        selectedIds.map((id) => api.deleteRecording(id))
      );
      const deletedIds = selectedIds.filter(
        (_, index) => results[index].status === 'fulfilled'
      );
      const failedCount = results.length - deletedIds.length;
      if (deletedIds.length > 0) {
        setRecordings((current) => current.filter((r) => !deletedIds.includes(r.id)));
        setSelectedIds((current) => current.filter((id) => !deletedIds.includes(id)));
        if (playing && deletedIds.includes(playing.id)) setPlaying(null);
        message.success(`已删除 ${deletedIds.length} 条录像`);
      }
      if (failedCount > 0) {
        message.error(`${failedCount} 条录像删除失败，请稍后重试`);
      }
    } finally {
      setDeleting(false);
    }
  };

  const confirmDeleteSelected = () => {
    if (selectedIds.length === 0) return;
    Modal.confirm({
      title: `删除选中的 ${selectedIds.length} 条录像？`,
      content: '录像文件和数据库记录都会删除，此操作不可恢复。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: deleteSelected,
    });
  };

  const allSelected = recordings.length > 0 && selectedIds.length === recordings.length;
  const someSelected = selectedIds.length > 0 && !allSelected;

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
        <Card
          title="录像列表"
          style={{ width: 380 }}
          extra={
            <Space>
              <Checkbox
                checked={allSelected}
                indeterminate={someSelected}
                onChange={(event) =>
                  setSelectedIds(event.target.checked ? recordings.map((r) => r.id) : [])
                }
              >
                全选
              </Checkbox>
              <Button
                danger
                icon={<DeleteOutlined />}
                disabled={selectedIds.length === 0}
                loading={deleting}
                onClick={confirmDeleteSelected}
              >
                删除选中
              </Button>
            </Space>
          }
        >
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
                <Checkbox
                  checked={selectedIds.includes(r.id)}
                  aria-label={`选择${dayjs(r.start_time).format('YYYY-MM-DD HH:mm:ss')}录像`}
                  onClick={(event) => event.stopPropagation()}
                  onChange={(event) => {
                    setSelectedIds((current) =>
                      event.target.checked
                        ? [...current, r.id]
                        : current.filter((id) => id !== r.id)
                    );
                  }}
                  style={{ marginRight: 8 }}
                />
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
