import {
  CheckCircleOutlined,
  CloudServerOutlined,
  FolderOpenOutlined,
  GlobalOutlined,
  SaveOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Space,
  Spin,
  Tabs,
  Typography,
  message,
} from 'antd';
import { useEffect, useState } from 'react';

import * as api from '../api';
import type { StorageSettings } from '../api/types';
import { useTheme } from '../theme/ThemeProvider';

interface StorageForm {
  recording_path: string;
  snapshot_path: string;
}

export default function Settings() {
  const { theme } = useTheme();
  const [form] = Form.useForm<StorageForm>();
  const [settings, setSettings] = useState<StorageSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await api.getSettings();
      setSettings(data);
      form.setFieldsValue({
        recording_path: data.recording_path,
        snapshot_path: data.snapshot_path,
      });
    } catch {
      message.error('读取设置失败，请确认后端已启动');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSettings();
  }, []);

  const save = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const data = await api.updateStorageSettings(values);
      setSettings(data);
      form.setFieldsValue({
        recording_path: data.recording_path,
        snapshot_path: data.snapshot_path,
      });
      message.success('存储设置已保存');
    } catch {
      message.error('保存失败，请检查路径格式和权限');
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    form.setFieldsValue({
      recording_path: settings?.recording_path_default ?? '',
      snapshot_path: settings?.snapshot_path_default ?? '',
    });
  };

  const basicContent = loading ? (
    <div style={{ minHeight: 280, display: 'grid', placeItems: 'center' }}>
      <Spin />
    </div>
  ) : (
    <Form form={form} layout="vertical" style={{ maxWidth: 760 }}>
      <Alert
        type="info"
        showIcon
        message="文件路径由后端所在 Windows 主机解释"
        description="建议填写绝对路径，例如 D:\\VideoManage\\storage。留空会恢复默认目录。修改录像目录只影响之后完成的新录像分片，历史录像不会自动搬迁。"
        style={{ marginBottom: 24 }}
      />
      <Form.Item
        name="recording_path"
        label="录像存放地址"
        extra={
          settings?.recording_path_default
            ? `默认配置：${settings.recording_path_default}`
            : '留空时保留 ZLMediaKit 原始录像目录'
        }
      >
        <Input
          prefix={<FolderOpenOutlined />}
          allowClear
          placeholder="例如：D:\\VideoManage\\recordings"
        />
      </Form.Item>
      <Form.Item
        name="snapshot_path"
        label="抓拍存放地址"
        extra={`默认配置：${settings?.snapshot_path_default ?? './data/snapshots'}`}
      >
        <Input
          prefix={<FolderOpenOutlined />}
          allowClear
          placeholder="例如：D:\\VideoManage\\snapshots"
        />
      </Form.Item>
      <Space>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => void save()}>
          保存设置
        </Button>
        <Button onClick={reset}>恢复默认</Button>
      </Space>
    </Form>
  );

  const networkContent = settings ? (
    <Descriptions bordered column={1} style={{ maxWidth: 760 }}>
      <Descriptions.Item label="后端地址">
        <Typography.Text code>{settings.backend_base}</Typography.Text>
      </Descriptions.Item>
      <Descriptions.Item label="ZLMediaKit API">
        <Typography.Text code>{settings.zlm_api_base}</Typography.Text>
      </Descriptions.Item>
      <Descriptions.Item label="HTTP 流媒体端口">{settings.zlm_http_port}</Descriptions.Item>
      <Descriptions.Item label="RTSP 输出端口">{settings.zlm_rtsp_port}</Descriptions.Item>
      <Descriptions.Item label="RTMP 输出端口">{settings.zlm_rtmp_port}</Descriptions.Item>
      <Descriptions.Item label="运行状态">
        <Space><CheckCircleOutlined style={{ color: theme.status.success }} />配置可读取</Space>
      </Descriptions.Item>
    </Descriptions>
  ) : (
    <Spin />
  );

  return (
    <Card
      title={<Space><SettingOutlined />系统设置</Space>}
      style={{ background: `${theme.bg.elevated}e8`, borderColor: theme.border.default }}
    >
      <Tabs
        tabPosition="left"
        items={[
          {
            key: 'basic',
            label: <Space><SettingOutlined />基础设置</Space>,
            children: basicContent,
          },
          {
            key: 'network',
            label: <Space><GlobalOutlined />网络设置</Space>,
            children: networkContent,
          },
          {
            key: 'media',
            label: <Space><CloudServerOutlined />流媒体服务</Space>,
            children: (
              <Alert
                type="info"
                showIcon
                message="ZLMediaKit 负责流媒体服务"
                description="RTSP 拉流、协议转换、录像切片和 WebHook 均由 ZLMediaKit 完成；网络端口和 API 密钥请在其配置文件中维护。"
                style={{ maxWidth: 760 }}
              />
            ),
          },
        ]}
      />
    </Card>
  );
}
