import { useEffect } from 'react';
import { Form, Input, InputNumber, Modal, Select, Switch, message } from 'antd';

import * as api from '../api';
import type { Device, DeviceInput } from '../api/types';

interface DeviceFormProps {
  open: boolean;
  device: Device | null;
  onCancel: () => void;
  onSuccess: () => void;
}

export default function DeviceForm({
  open,
  device,
  onCancel,
  onSuccess,
}: DeviceFormProps) {
  const [form] = Form.useForm<DeviceInput>();

  useEffect(() => {
    if (open) {
      form.resetFields();
      if (device) {
        form.setFieldsValue(device);
      } else {
        form.setFieldsValue({
          vendor: 'generic',
          access_type: 'onvif',
          port: 554,
          onvif_port: 80,
          ptz_enabled: false,
          record_enabled: true,
          enabled: true,
          ip: '',
          username: '',
          password: '',
          rtsp_url: '',
          name: '',
        });
      }
    }
  }, [open, device, form]);

  const submit = async () => {
    const values = await form.validateFields();
    try {
      if (device) {
        await api.updateDevice(device.id, values);
      } else {
        await api.createDevice(values);
      }
      message.success('保存成功');
      onSuccess();
    } catch (err) {
      message.error('保存失败');
    }
  };

  return (
    <Modal
      title={device ? '编辑设备' : '添加设备'}
      open={open}
      onCancel={onCancel}
      onOk={submit}
      width={560}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item
          name="name"
          label="设备名称"
          rules={[{ required: true, message: '请输入设备名称' }]}
        >
          <Input placeholder="例如：客厅摄像头" />
        </Form.Item>
        <Form.Item name="vendor" label="厂商">
          <Input placeholder="例如：海康 / 大华 / TP-Link（可留空）" />
        </Form.Item>
        <Form.Item name="access_type" label="接入方式" rules={[{ required: true }]}>
          <Select
            options={[
              { value: 'onvif', label: 'RTSP/ONVIF 标准协议' },
              { value: 'cloud', label: '厂商云 API（预留）' },
              { value: 'sdk', label: '厂商私有 SDK（预留）' },
            ]}
          />
        </Form.Item>
        <Form.Item name="rtsp_url" label="RTSP 地址（可选，填写则优先使用）">
          <Input placeholder="rtsp://user:pass@ip:554/stream" />
        </Form.Item>
        <div style={{ display: 'flex', gap: 12 }}>
          <Form.Item name="ip" label="IP 地址" style={{ flex: 1 }}>
            <Input placeholder="192.168.1.10" />
          </Form.Item>
          <Form.Item name="port" label="RTSP 端口">
            <InputNumber min={1} max={65535} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item name="onvif_port" label="ONVIF 端口">
            <InputNumber min={1} max={65535} style={{ width: 120 }} />
          </Form.Item>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <Form.Item name="username" label="用户名" style={{ flex: 1 }}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="密码" style={{ flex: 1 }}>
            <Input.Password />
          </Form.Item>
        </div>
        <div style={{ display: 'flex', gap: 32 }}>
          <Form.Item name="ptz_enabled" label="启用云台" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="record_enabled" label="启用录像" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="enabled" label="启用设备" valuePropName="checked">
            <Switch />
          </Form.Item>
        </div>
      </Form>
    </Modal>
  );
}
