import { ArrowUpOutlined, FolderOpenOutlined, HomeOutlined } from '@ant-design/icons';
import { Alert, Button, Empty, Input, List, Modal, Space, Spin, Typography } from 'antd';
import type { InputProps } from 'antd';
import { isAxiosError } from 'axios';
import { useEffect, useRef, useState } from 'react';

import * as api from '../api';
import type { DirectoryListing } from '../api/types';

interface DirectoryPickerInputProps extends Omit<InputProps, 'value' | 'onChange' | 'prefix'> {
  value?: string;
  onChange?: (value: string) => void;
  pickerTitle: string;
}

export default function DirectoryPickerInput({
  value = '', onChange, pickerTitle, disabled, ...inputProps
}: DirectoryPickerInputProps) {
  const [open, setOpen] = useState(false);
  const [listing, setListing] = useState<DirectoryListing | null>(null);
  const [address, setAddress] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const request = useRef<AbortController | null>(null);

  useEffect(() => () => request.current?.abort(), []);

  const browse = async (path: string) => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError('');
    setAddress(path);
    try {
      const data = await api.browseDirectories(path, controller.signal);
      if (controller.signal.aborted) return;
      setListing(data);
      setAddress(data.current_path);
    } catch (err) {
      if (controller.signal.aborted) return;
      const detail = isAxiosError(err) ? err.response?.data?.detail : undefined;
      setError(typeof detail === 'string' ? detail : '读取文件夹失败，请检查路径或稍后重试');
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  };

  const close = () => {
    request.current?.abort();
    setOpen(false);
    setLoading(false);
  };

  const select = () => {
    if (!listing?.current_path || loading || error || address !== listing.current_path) return;
    onChange?.(listing.current_path);
    close();
  };

  return (
    <>
      <Input
        {...inputProps}
        value={value}
        onChange={(event) => onChange?.(event.target.value)}
        disabled={disabled}
        allowClear
        maxLength={512}
        prefix={
          <Button
            type="text"
            size="small"
            icon={<FolderOpenOutlined />}
            aria-label={pickerTitle}
            title={pickerTitle}
            disabled={disabled}
            style={{ width: 22, height: 22, padding: 0 }}
            onClick={() => {
              setListing(null);
              setOpen(true);
              void browse(value);
            }}
          />
        }
      />
      <Modal
        title={pickerTitle}
        open={open}
        onCancel={close}
        onOk={select}
        okText="选择此文件夹"
        cancelText="取消"
        okButtonProps={{ disabled: !listing?.current_path || loading || !!error || address !== listing.current_path }}
        width={680}
        destroyOnClose
      >
        <Typography.Paragraph type="secondary">
          请选择后端主机上的存储文件夹。选择后点击页面的“保存设置”生效。
        </Typography.Paragraph>
        <Space style={{ marginBottom: 12 }}>
          <Button icon={<HomeOutlined />} onClick={() => void browse('')}>此电脑</Button>
          <Button
            icon={<ArrowUpOutlined />}
            disabled={loading || listing?.parent_path == null}
            onClick={() => void browse(listing?.parent_path ?? '')}
          >
            上一级
          </Button>
        </Space>
        <Space.Compact block style={{ marginBottom: 12 }}>
          <Input
            aria-label="文件夹路径"
            placeholder="选择磁盘，或输入文件夹路径"
            value={address}
            maxLength={512}
            onChange={(event) => setAddress(event.target.value)}
            onPressEnter={(event) => {
              event.preventDefault();
              void browse(address);
            }}
          />
          <Button onClick={() => void browse(address)} loading={loading}>前往</Button>
        </Space.Compact>
        {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 12 }} />}
        <Spin spinning={loading}>
          <List
            key={listing?.current_path ?? ''}
            bordered
            size="small"
            dataSource={error ? [] : listing?.directories ?? []}
            locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={error ? '可返回“此电脑”重新选择' : '此文件夹没有子文件夹'} /> }}
            pagination={{ pageSize: 10, hideOnSinglePage: true, showSizeChanger: false }}
            style={{ minHeight: 200 }}
            renderItem={(directory) => (
              <List.Item key={directory.path} style={{ padding: '4px 8px' }}>
                <Button
                  type="text"
                  block
                  icon={<FolderOpenOutlined />}
                  title={directory.path}
                  disabled={loading}
                  onClick={() => void browse(directory.path)}
                  style={{ textAlign: 'left', justifyContent: 'flex-start', height: 'auto', minHeight: 32, whiteSpace: 'normal', overflowWrap: 'anywhere' }}
                >
                  {directory.name}
                </Button>
              </List.Item>
            )}
          />
        </Spin>
        <Typography.Paragraph style={{ marginTop: 12, marginBottom: 0, overflowWrap: 'anywhere' }}>
          当前文件夹：{listing?.current_path || '请选择磁盘或文件夹'}
        </Typography.Paragraph>
      </Modal>
    </>
  );
}
