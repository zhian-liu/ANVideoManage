import { ApiOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import {
  Button,
  Card,
  Empty,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import { useCallback, useEffect, useState } from 'react';

import * as api from '../api';
import type { Device, StreamProtocolsInfo } from '../api/types';
import DeviceForm from '../components/DeviceForm';

export default function Devices() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Device | null>(null);
  const [loading, setLoading] = useState(false);
  const [protocolModalOpen, setProtocolModalOpen] = useState(false);
  const [protocolLoading, setProtocolLoading] = useState(false);
  const [protocolDevice, setProtocolDevice] = useState<Device | null>(null);
  const [protocolInfo, setProtocolInfo] = useState<StreamProtocolsInfo | null>(null);

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

  const openProtocols = async (device: Device) => {
    setProtocolDevice(device);
    setProtocolInfo(null);
    setProtocolModalOpen(true);
    setProtocolLoading(true);
    try {
      setProtocolInfo(await api.getStreamProtocols(device.id));
    } catch {
      message.error('获取流协议地址失败，请确认后端和 ZLMediaKit 正常运行');
    } finally {
      setProtocolLoading(false);
    }
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
                <Tooltip title="查看流地址">
                  <Button
                    type="link"
                    size="small"
                    icon={<ApiOutlined />}
                    aria-label={`查看${record.name}的流地址`}
                    onClick={() => void openProtocols(record)}
                  />
                </Tooltip>
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
      <Modal
        title={`ZLMediaKit 流地址${protocolDevice ? ` - ${protocolDevice.name}` : ''}`}
        open={protocolModalOpen}
        onCancel={() => setProtocolModalOpen(false)}
        footer={null}
        width={920}
        destroyOnClose
      >
        {protocolLoading ? (
          <div style={{ minHeight: 180, display: 'grid', placeItems: 'center' }}>
            <Spin />
          </div>
        ) : protocolInfo ? (
          <>
            <Space style={{ marginBottom: 12 }}>
              <Tag color={protocolInfo.online ? 'green' : 'default'}>
                {protocolInfo.online ? '流在线' : '流未上线'}
              </Tag>
              <Typography.Text code>{protocolInfo.stream}</Typography.Text>
            </Space>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
              地址由 ZLMediaKit 的 app/stream 自动生成；流未上线时，协议地址暂时无法访问。
            </Typography.Paragraph>
            <Table
              rowKey="key"
              size="small"
              pagination={false}
              dataSource={protocolInfo.protocols}
              columns={[
                { title: '协议', dataIndex: 'name', width: 140 },
                {
                  title: '流地址',
                  dataIndex: 'url',
                  render: (url: string) => (
                    <Typography.Text
                      copyable={{ text: url, tooltips: ['复制地址', '已复制'] }}
                      style={{ wordBreak: 'break-all' }}
                    >
                      {url}
                    </Typography.Text>
                  ),
                },
                { title: '说明', dataIndex: 'description', width: 250 },
              ]}
            />
          </>
        ) : (
          <Empty description="暂无协议地址" />
        )}
      </Modal>
    </Card>
  );
}
