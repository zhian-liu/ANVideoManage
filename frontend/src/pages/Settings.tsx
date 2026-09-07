import {
  CheckCircleOutlined,
  CloudServerOutlined,
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
  InputNumber,
  Radio,
  Space,
  Spin,
  Tabs,
  Typography,
  message,
} from 'antd';
import { useEffect, useState } from 'react';

import * as api from '../api';
import type { StorageSettings } from '../api/types';
import DirectoryPickerInput from '../components/DirectoryPickerInput';
import { useTheme } from '../theme/ThemeProvider';

interface StorageForm {
  recording_path: string;
  snapshot_path: string;
  auto_cleanup: boolean;
  recording_retention_days: number;
}

export default function Settings() {
  const { theme } = useTheme();
  const [form] = Form.useForm<StorageForm>();
  const [settings, setSettings] = useState<StorageSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const autoCleanup = Form.useWatch('auto_cleanup', form);

  const fillForm = (data: StorageSettings) => {
    form.setFieldsValue({
      recording_path: data.recording_path,
      snapshot_path: data.snapshot_path,
      auto_cleanup: data.recording_retention_days > 0,
      recording_retention_days: data.recording_retention_days || 30,
    });
  };

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await api.getSettings();
      setSettings(data);
      fillForm(data);
    } catch {
      message.error('读取设置失败，请确认后端已启动');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSettings();
  }, []);

  const save = async (values: StorageForm) => {
    setSaving(true);
    try {
      const data = await api.updateStorageSettings({
        recording_path: values.recording_path,
        snapshot_path: values.snapshot_path,
        recording_retention_days: values.auto_cleanup ? values.recording_retention_days : 0,
      });
      setSettings(data);
      fillForm(data);
      message.success('存储设置已保存');
    } catch {
      message.error('保存失败，请检查输入或稍后重试');
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    form.setFieldsValue({
      recording_path: settings?.recording_path_default ?? '',
      snapshot_path: settings?.snapshot_path_default ?? '',
      auto_cleanup: false,
      recording_retention_days: 30,
    });
  };

  const basicContent = loading ? (
    <div style={{ minHeight: 280, display: 'grid', placeItems: 'center' }}>
      <Spin />
    </div>
  ) : (
    <Form
      form={form}
      layout="vertical"
      style={{ maxWidth: 760 }}
      disabled={saving || !settings}
      onFinish={(values) => void save(values)}
    >
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
        <DirectoryPickerInput
          pickerTitle="选择录像文件夹"
          placeholder="例如：D:\\VideoManage\\recordings"
        />
      </Form.Item>
      <Form.Item
        name="auto_cleanup"
        label="录像保存方式"
        extra="默认永久保存。自动清理按录像结束时间计算，也适用于已保存的历史录像。"
      >
        <Radio.Group
          options={[
            { label: '永久保存', value: false },
            { label: '按天自动清理', value: true },
          ]}
        />
      </Form.Item>
      {autoCleanup && (
        <Form.Item
          name="recording_retention_days"
          label="录像保留天数"
          rules={[
            { required: true, message: '请输入录像保留天数' },
            { type: 'integer', min: 1, max: 3650, message: '请输入 1–3650 之间的整数' },
          ]}
          extra="保存后立即检查，之后每小时自动清理超过保留天数的已完成录像和回放记录。清理后的录像无法恢复，抓拍图片不受影响。"
        >
          <InputNumber min={1} max={3650} precision={0} addonAfter="天" style={{ width: 220 }} />
        </Form.Item>
      )}
      <Form.Item
        name="snapshot_path"
        label="抓拍存放地址"
        extra={`默认配置：${settings?.snapshot_path_default ?? './data/snapshots'}`}
      >
        <DirectoryPickerInput
          pickerTitle="选择抓拍文件夹"
          placeholder="例如：D:\\VideoManage\\snapshots"
        />
      </Form.Item>
      <Space>
        <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
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
