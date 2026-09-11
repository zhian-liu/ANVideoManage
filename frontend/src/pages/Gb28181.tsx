import { PlusOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Col, Form, Input, InputNumber, Modal, Row, Select, Space, Switch, Table, Tabs, Tag, Typography, message } from 'antd';
import { isAxiosError } from 'axios';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import * as api from '../api';
import type { GbChannel, GbConfig, GbConfigResponse, GbDevice, GbDeviceInput } from '../api/types';
import { useAuth } from '../store/auth';

function failure(error: unknown, fallback: string) {
  const detail = isAxiosError(error) ? error.response?.data?.detail : undefined;
  message.error(typeof detail === 'string' ? detail : fallback);
}

export default function Gb28181() {
  const [form] = Form.useForm<GbConfig>();
  const [deviceForm] = Form.useForm<GbDeviceInput>();
  const [state, setState] = useState<GbConfigResponse | null>(null);
  const [devices, setDevices] = useState<GbDevice[]>([]);
  const [channels, setChannels] = useState<GbChannel[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const selectedRef = useRef<string | null>(null);
  const [editing, setEditing] = useState<GbDevice | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deviceSaving, setDeviceSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const navigate = useNavigate();
  selectedRef.current = selected;

  const refresh = useCallback(async () => {
    const [config, list] = await Promise.all([api.getGbConfig(), api.listGbDevices()]);
    setState(config);
    setDevices(list);
    const id = selectedRef.current;
    if (id) {
      const rows = await api.listGbChannels(id);
      if (selectedRef.current === id) setChannels(rows);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    void api.getGbConfig().then((result) => {
      setState(result);
      form.setFieldsValue(result.config);
    }).catch((error) => failure(error, '读取国标配置失败'));
    void refresh().catch((error) => failure(error, '读取国标设备失败')).finally(() => setLoading(false));
    const timer = window.setInterval(() => void refresh().catch(() => undefined), 5000);
    return () => window.clearInterval(timer);
  }, [form, refresh]);

  const save = async (values: GbConfig) => {
    setSaving(true);
    try {
      const result = await api.saveGbConfig(values);
      setState(result);
      form.setFieldsValue(result.config);
      message.success(values.enabled ? '国标服务已启动，等待设备注册' : '国标服务已关闭');
      await refresh();
    } catch (error) {
      failure(error, '保存国标配置失败');
      await refresh().catch(() => undefined);
    } finally { setSaving(false); }
  };
  const openDevice = (device: GbDevice | null) => {
    setEditing(device);
    deviceForm.resetFields();
    deviceForm.setFieldsValue(device ? { id: device.id, name: device.name, enabled: device.enabled, password: '' }
      : { id: '', name: '', password: '', enabled: true });
    setModalOpen(true);
  };
  const saveDevice = async () => {
    const values = await deviceForm.validateFields();
    setDeviceSaving(true);
    try {
      if (editing) {
        const input: Partial<Omit<GbDeviceInput, 'id'>> = { name: values.name, enabled: values.enabled };
        if (values.password) input.password = values.password;
        await api.updateGbDevice(editing.id, input);
      } else await api.createGbDevice(values);
      setModalOpen(false);
      message.success('设备配置已保存，请在摄像机或 NVR 上填写对应注册信息');
      await refresh();
    } catch (error) { failure(error, '保存国标设备失败'); }
    finally { setDeviceSaving(false); }
  };
  const choose = async (id: string) => {
    selectedRef.current = id;
    setSelected(id);
    setChannels([]);
    try {
      const rows = await api.listGbChannels(id);
      if (selectedRef.current === id) setChannels(rows);
    } catch (error) { failure(error, '读取通道失败'); }
  };
  const sync = async (id: string) => {
    try { await api.syncGbCatalog(id); message.success('目录查询已发送'); await refresh(); }
    catch (error) { failure(error, '同步目录失败'); }
  };
  const toggleChannel = async (channel: GbChannel, enabled: boolean) => {
    if (channel.device_id == null) return;
    try { await api.updateDevice(channel.device_id, { enabled }); await refresh(); }
    catch (error) { failure(error, '修改通道失败'); await refresh().catch(() => undefined); }
  };
  const catalogLabel = (device: GbDevice) => {
    const labels: Record<string, string> = { idle: '未查询', syncing: '同步中', complete: '已完成', error: '同步失败' };
    return `${labels[device.catalog_state] ?? device.catalog_state} ${device.catalog_received}/${device.catalog_expected ?? '-'}`;
  };

  return <Space direction="vertical" size="large" style={{ width: '100%' }}>
    <Card title="国标接入 · GB/T 28181" extra={<Tag color={state?.service.ready ? 'green' : state?.service.state === 'error' ? 'red' : 'default'}>
      {state?.service.ready ? '服务运行中' : state?.service.state === 'error' ? '服务异常' : state?.service.state === 'starting' ? '启动中' : '服务未启用'}
    </Tag>}>
      {state?.service.error && <Alert type="error" showIcon message={state.service.error} style={{ marginBottom: 16 }} />}
      <Tabs items={[
        { key: 'devices', label: '注册设备与通道', children: <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Alert type="info" showIcon message="先预置设备编码和密码，再在摄像机或 NVR 中配置平台参数。注册成功后自动同步目录，视频通道会出现在设备管理和实时预览中。" />
          <Space>
            <Button type="primary" icon={<PlusOutlined />} disabled={!isAdmin} onClick={() => openDevice(null)}>预置设备</Button>
            <Button icon={<ReloadOutlined />} onClick={() => void refresh().catch((error) => failure(error, '刷新失败'))}>刷新</Button>
          </Space>
          <Table<GbDevice> rowKey="id" loading={loading} dataSource={devices} size="small" scroll={{ x: 1000 }}
            rowSelection={{ type: 'radio', selectedRowKeys: selected ? [selected] : [], onChange: (keys) => void choose(String(keys[0])) }}
            columns={[
              { title: '名称 / 国标编码', render: (_, d) => <><div>{d.name}</div><Typography.Text type="secondary" copyable>{d.id}</Typography.Text></> },
              { title: '状态', render: (_, d) => <Tag color={d.online ? 'green' : 'default'}>{!d.enabled ? '已停用' : d.online ? '在线' : '待注册 / 离线'}</Tag> },
              { title: '连接来源', render: (_, d) => d.remote_ip ? `${d.remote_ip}:${d.remote_port} ${d.transport}` : '-' },
              { title: '目录', render: (_, d) => catalogLabel(d) },
              { title: '操作', render: (_, d) => <Space>
                <Button type="link" size="small" onClick={() => void choose(d.id)}>通道</Button>
                <Button type="link" size="small" icon={<SyncOutlined />} disabled={!isAdmin || !d.online || d.catalog_state === 'syncing'} onClick={() => void sync(d.id)}>同步</Button>
                <Button type="link" size="small" disabled={!isAdmin} onClick={() => openDevice(d)}>编辑</Button>
              </Space> },
            ]} />
          {selected && <>
            <Typography.Title level={5}>{devices.find((d) => d.id === selected)?.name} · 通道目录</Typography.Title>
            {devices.find((d) => d.id === selected)?.last_error && <Alert type="warning" showIcon message={devices.find((d) => d.id === selected)?.last_error} />}
            <Table<GbChannel> rowKey="id" dataSource={channels} size="small" scroll={{ x: 750 }} columns={[
              { title: '名称', dataIndex: 'name' },
              { title: '通道编码', dataIndex: 'channel_id' },
              { title: '状态', render: (_, c) => <Tag color={c.online && c.present ? 'green' : 'default'}>{!c.present ? '目录中缺失' : c.device_id == null ? '目录节点' : c.online ? '在线' : '离线'}</Tag> },
              { title: '启用', render: (_, c) => c.device_id != null ? <Switch size="small" checked={c.enabled} disabled={!isAdmin} onChange={(value) => void toggleChannel(c, value)} /> : '-' },
              { title: '操作', render: (_, c) => <Button type="link" disabled={c.device_id == null || !c.enabled || !c.online || !c.present} onClick={() => navigate(`/live?device_id=${c.device_id}`)}>实时预览</Button> },
            ]} />
          </>}
        </Space> },
        { key: 'config', label: '平台配置', children: <Form form={form} layout="vertical" onFinish={save} disabled={!isAdmin || saving}>
          <Alert type="info" showIcon message="公告地址和媒体接收地址必须能从设备所在网络访问。SIP 支持 UDP/TCP；媒体传输可独立选择。保存配置会重启国标服务，设备随后需要重新注册。" style={{ marginBottom: 20 }} />
          <Form.Item name="enabled" label="启用国标接入" valuePropName="checked"><Switch /></Form.Item>
          <Row gutter={24}>
            <Col xs={24} md={12}><Form.Item name="sip_id" label="平台 SIP 编码" rules={[{ required: true, pattern: /^[0-9]{20}$/, message: '请输入 20 位数字编码' }]}><Input maxLength={20} /></Form.Item></Col>
            <Col xs={24} md={12}><Form.Item name="realm" label="SIP 域" rules={[{ required: true, pattern: /^[0-9]{10}$/, message: '请输入 10 位数字域编码' }]}><Input maxLength={10} /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item name="listen_ip" label="SIP 监听地址" rules={[{ required: true }]}><Input placeholder="0.0.0.0" /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item name="advertise_ip" label="设备访问的平台 IP"><Input placeholder="例如 192.168.1.100" /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item name="sip_port" label="SIP 端口" rules={[{ required: true }]}><InputNumber min={1} max={65535} style={{ width: '100%' }} /></Form.Item></Col>
            <Col xs={24} md={12}><Form.Item name="media_ip" label="媒体接收 IP"><Input placeholder="设备可达的流媒体服务器 IP" /></Form.Item></Col>
            <Col xs={24} md={12}><Form.Item name="media_transport" label="媒体传输" rules={[{ required: true }]}><Select options={[{ value: 'udp', label: 'RTP / UDP' }, { value: 'tcp-passive', label: 'RTP / TCP（设备主动连接平台）' }]} /></Form.Item></Col>
            <Col xs={24} md={6}><Form.Item name="heartbeat_timeout" label="心跳超时（秒）"><InputNumber min={10} max={3600} /></Form.Item></Col>
            <Col xs={24} md={6}><Form.Item name="catalog_timeout" label="目录超时（秒）"><InputNumber min={5} max={120} /></Form.Item></Col>
            <Col xs={24} md={6}><Form.Item name="invite_timeout" label="点播响应超时（秒）"><InputNumber min={3} max={60} /></Form.Item></Col>
            <Col xs={24} md={6}><Form.Item name="media_timeout" label="媒体到达超时（秒）"><InputNumber min={3} max={60} /></Form.Item></Col>
          </Row>
          <Button type="primary" htmlType="submit" loading={saving}>保存平台配置</Button>
        </Form> },
      ]} />
    </Card>
    <Modal title={editing ? '编辑注册设备' : '预置注册设备'} open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => void saveDevice()} confirmLoading={deviceSaving} destroyOnClose>
      <Form form={deviceForm} layout="vertical" style={{ marginTop: 20 }}>
        <Form.Item name="id" label="设备国标编码" rules={[{ required: true, pattern: /^[0-9]{20}$/, message: '请输入 20 位设备编码' }]}><Input disabled={!!editing} maxLength={20} /></Form.Item>
        <Form.Item name="name" label="设备名称" rules={[{ required: true }]}><Input maxLength={128} /></Form.Item>
        <Form.Item name="password" label={editing ? '新注册密码（留空保留原密码）' : '注册密码'} rules={[{ required: !editing }]}><Input.Password autoComplete="new-password" maxLength={128} /></Form.Item>
        <Form.Item name="enabled" label="允许注册" valuePropName="checked"><Switch /></Form.Item>
      </Form>
    </Modal>
  </Space>;
}
