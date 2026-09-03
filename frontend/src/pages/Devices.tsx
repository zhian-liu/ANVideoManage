import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { Button, Card, Popconfirm, Space, Table, Tag, message } from 'antd';
import { useCallback, useEffect, useState } from 'react';

import * as api from '../api';
import type { Device } from '../api/types';
import DeviceForm from '../components/DeviceForm';

export default function Devices() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Device | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setDevices(await api.listDevices());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const openCreate = () => {
    setEditing(null);
    setOpen(true);
  };

  const openEdit = (d: Device) => {
    setEditing(d);
    setOpen(true);
  };

  const onDelete = async (id: number) => {
    await api.deleteDevice(id);
    message.success('已删除');
    refresh();
  };

  const onSuccess = () => {
    setOpen(false);
    refresh();
  };

  return (
    <Card
      title="设备管理"
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={refresh}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            添加设备
          </Button>
        </Space>
      }
    >
      <Table
        rowKey="id"
        dataSource={devices}
        loading={loading}
        pagination={false}
        columns={[
          { title: '名称', dataIndex: 'name' },
          { title: '厂商', dataIndex: 'vendor', render: (v: string) => v || '-' },
          {
            title: '接入方式',
            dataIndex: 'access_type',
            render: (v: string) => (
              <Tag>{v === 'onvif' ? 'RTSP/ONVIF' : v}</Tag>
            ),
          },
          { title: 'IP', dataIndex: 'ip', render: (v: string) => v || '-' },
          {
            title: '状态',
            dataIndex: 'status',
            render: (s: string) => {
              const color =
                s === 'online' ? 'green' : s === 'offline' ? 'red' : 'default';
              const text =
                s === 'online' ? '在线' : s === 'offline' ? '离线' : '未知';
              return <Tag color={color}>{text}</Tag>;
            },
          },
          {
            title: '云台',
            dataIndex: 'ptz_enabled',
            render: (v: boolean) => (v ? <Tag color="blue">已启用</Tag> : '-'),
          },
          {
            title: '录像',
            dataIndex: 'record_enabled',
            render: (v: boolean) => (v ? <Tag color="green">已启用</Tag> : '-'),
          },
          {
            title: '操作',
            render: (_, record) => (
              <Space>
                <a onClick={() => openEdit(record)}>编辑</a>
                <Popconfirm
                  title="确定删除该设备及其录像？"
                  onConfirm={() => onDelete(record.id)}
                >
                  <a style={{ color: '#cf1322' }}>删除</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <DeviceForm
        open={open}
        device={editing}
        onCancel={() => setOpen(false)}
        onSuccess={onSuccess}
      />
    </Card>
  );
}
