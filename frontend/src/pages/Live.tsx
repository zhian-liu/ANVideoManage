import {
  AppstoreOutlined,
  BorderOutlined,
  CameraOutlined,
  CloseOutlined,
  PauseOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  StopOutlined,
  VideoCameraAddOutlined,
} from '@ant-design/icons';
import { Button, Card, Empty, message, Modal, Tree } from 'antd';
import type { DataNode } from 'antd/es/tree';
import { useCallback, useEffect, useRef, useState } from 'react';

import * as api from '../api';
import type { Device, StreamInfo } from '../api/types';
import PTZPanel from '../components/PTZPanel';
import VideoPlayer from '../components/VideoPlayer';
import { useTheme } from '../theme/ThemeProvider';

type LayoutType = 1 | 4 | 9 | 16;

export default function Live() {
  const { theme } = useTheme();
  const [devices, setDevices] = useState<Device[]>([]);
  const [streams, setStreams] = useState<Record<number, StreamInfo>>({});
  const [selected, setSelected] = useState<Device | null>(null);
  const [loading, setLoading] = useState(false);
  const [layout, setLayout] = useState<LayoutType>(4);
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<Array<number | null>>([]);
  const [selectedWindow, setSelectedWindow] = useState(0);
  const [selectedTreeDeviceId, setSelectedTreeDeviceId] = useState<number | null>(null);
  const [pausedWindows, setPausedWindows] = useState<Record<number, boolean>>({});
  const [snapshottingDevices, setSnapshottingDevices] = useState<Record<number, boolean>>({});
  const [recordingActions, setRecordingActions] = useState<Record<number, boolean>>({});
  const videoElements = useRef<Record<number, Record<string, HTMLVideoElement>>>({});

  const registerVideoElement = useCallback(
    (deviceId: number, key: string, element: HTMLVideoElement | null) => {
      const byKey = videoElements.current[deviceId] ?? {};
      if (element) {
        byKey[key] = element;
        videoElements.current[deviceId] = byKey;
        return;
      }

      delete byKey[key];
      if (Object.keys(byKey).length === 0) {
        delete videoElements.current[deviceId];
      } else {
        videoElements.current[deviceId] = byKey;
      }
    },
    []
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const ds = await api.listDevices();
      setDevices(ds);
      const infos = await Promise.all(
        ds.filter((d) => d.enabled).map((d) => api.getStreamInfo(d.id).catch(() => null))
      );
      const map: Record<number, StreamInfo> = {};
      infos.forEach((info) => {
        if (info) map[info.device_id] = info;
      });
      setStreams(map);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const enabledDevices = devices.filter((d) => d.enabled);

  // 构建设备树数据
  const treeData: DataNode[] = enabledDevices.map((d) => ({
    key: d.id.toString(),
    title: d.name,
    icon: streams[d.id]?.online ? (
      <span style={{ color: '#52c41a' }}>●</span>
    ) : (
      <span style={{ color: '#d9d9d9' }}>●</span>
    ),
  }));

  // 将设备放入当前选中的视频窗口。
  const assignDeviceToWindow = (id: number) => {
    const previousDeviceId = selectedDeviceIds[selectedWindow] ?? null;
    const next = [...selectedDeviceIds];
    next[selectedWindow] = id;

    setSelectedTreeDeviceId(id);
    setSelectedDeviceIds(next);
    setPausedWindows((prev) => {
      if (!prev[selectedWindow]) return prev;
      const next = { ...prev };
      delete next[selectedWindow];
      return next;
    });
    if (previousDeviceId != null && previousDeviceId !== id) {
      stopStreamIfUnused(previousDeviceId, next);
    }
  };

  const onDeviceSelect = (selectedKeys: React.Key[]) => {
    const id = Number(selectedKeys[0]);
    if (Number.isInteger(id)) assignDeviceToWindow(id);
  };

  const onDeviceClick = (_event: unknown, node: DataNode) => {
    const id = Number(node.key);
    if (Number.isInteger(id)) assignDeviceToWindow(id);
  };

  const stopStreamIfUnused = (
    deviceId: number,
    assignments: Array<number | null>,
    ignoreSelectedDetails = false
  ) => {
    // 正在录像或录制操作尚未完成时，不能删除共享的流代理。
    const device = devices.find((item) => item.id === deviceId);
    const recording = streams[deviceId]?.recording ?? device?.record_enabled ?? false;
    if (recording || recordingActions[deviceId]) return;

    const usedByWindow = assignments.some((assignedId) => assignedId === deviceId);
    const usedByDetails = !ignoreSelectedDetails && selected?.id === deviceId;
    if (usedByWindow || usedByDetails) return;

    void api.stopStream(deviceId)
      .then(() => {
        setStreams((prev) => {
          const info = prev[deviceId];
          if (!info || !info.online) return prev;
          return { ...prev, [deviceId]: { ...info, online: false } };
        });
      })
      .catch(() => {
        // 播放器已经在浏览器端关闭，停止代理失败不影响界面状态。
      });
  };

  const captureCurrentVideo = async (deviceId: number): Promise<Blob | null> => {
    const video = Object.values(videoElements.current[deviceId] ?? {})[0];
    if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return null;
    if (!video.videoWidth || !video.videoHeight) return null;

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext('2d');
    if (!context) return null;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    // toBlob can throw when the media response lacks CORS headers.
    return await new Promise((resolve) => {
      canvas.toBlob(resolve, 'image/jpeg', 0.92);
    });
  };

  const captureSnapshot = async (deviceId: number, deviceName: string) => {
    setSnapshottingDevices((prev) => ({ ...prev, [deviceId]: true }));
    try {
      let blob: Blob | null = null;
      try {
        blob = await captureCurrentVideo(deviceId);
      } catch {
        // A tainted canvas means the media server did not allow canvas access.
        blob = null;
      }
      if (!blob) blob = await api.captureSnapshot(deviceId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const safeName = deviceName.replace(/[\\/:*?"<>|]/g, '_');
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      link.href = url;
      link.download = `${safeName}-${timestamp}.jpg`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      message.success('抓拍图片已下载');
    } catch {
      message.error('抓拍失败，请确认视频正在播放且设备配置正确');
    } finally {
      setSnapshottingDevices((prev) => {
        const next = { ...prev };
        delete next[deviceId];
        return next;
      });
    }
  };

  const toggleRecording = async (deviceId: number) => {
    const current = Boolean(streams[deviceId]?.recording);
    setRecordingActions((prev) => ({ ...prev, [deviceId]: true }));
    try {
      const status = current
        ? await api.stopRecording(deviceId)
        : await api.startRecording(deviceId);
      setStreams((prev) => {
        const info = prev[deviceId];
        if (!info) return prev;
        return {
          ...prev,
          [deviceId]: {
            ...info,
            online: status.recording ? true : info.online,
            recording: status.recording,
          },
        };
      });
      message.success(status.recording ? '录像已开始' : '录像已停止');
    } catch {
      message.error(current ? '停止录像失败' : '启动录像失败');
    } finally {
      setRecordingActions((prev) => {
        const next = { ...prev };
        delete next[deviceId];
        return next;
      });
    }
  };

  const closeWindow = (windowIndex: number) => {
    const deviceId = selectedDeviceIds[windowIndex] ?? null;
    if (deviceId == null) return;

    const next = [...selectedDeviceIds];
    next[windowIndex] = null;
    setSelectedDeviceIds(next);
    setPausedWindows((prev) => {
      if (!prev[windowIndex]) return prev;
      const next = { ...prev };
      delete next[windowIndex];
      return next;
    });
    stopStreamIfUnused(deviceId, next);
  };

  const toggleWindowPause = (windowIndex: number) => {
    setPausedWindows((prev) => ({
      ...prev,
      [windowIndex]: !prev[windowIndex],
    }));
  };

  // 处理双击设备 - 打开详情弹窗
  const onDeviceDoubleClick = (deviceId: number) => {
    const device = devices.find((d) => d.id === deviceId);
    if (device) {
      setSelected(device);
    }
  };

  // 获取布局列数
  const getLayoutCols = (type: LayoutType): number => {
    switch (type) {
      case 1:
        return 1;
      case 4:
        return 2;
      case 9:
        return 3;
      case 16:
        return 4;
    }
  };

  // 渲染视频窗口
  const renderVideoGrid = () => {
    const cols = getLayoutCols(layout);
    const cells: JSX.Element[] = [];

    for (let i = 0; i < layout; i++) {
      const deviceId = selectedDeviceIds[i] ?? null;
      const device = deviceId ? devices.find((d) => d.id === deviceId) : null;
      const info = device ? streams[device.id] : null;
      const isSelected = selectedWindow === i;
      const isPaused = Boolean(pausedWindows[i]);
      const isRecording = Boolean(info?.recording);

      cells.push(
        <div
          key={i}
          className="video-cell"
          style={{
            position: 'relative',
            aspectRatio: '16 / 9',
            background: theme.bg.base,
            border: `2px solid ${isSelected ? theme.primary.main : theme.border.default}`,
            borderRadius: 8,
            overflow: 'hidden',
            cursor: 'pointer',
            transition: 'all 0.3s',
            boxShadow: isSelected ? `0 0 0 2px ${theme.primary.dim}` : 'none',
          }}
          aria-label={`窗口 ${i + 1}${device ? `：${device.name}` : ''}`}
          role="button"
          tabIndex={0}
          onClick={() => setSelectedWindow(i)}
          onDoubleClick={() => device && onDeviceDoubleClick(device.id)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              setSelectedWindow(i);
            }
          }}
          onMouseEnter={(e) => {
            if (device) {
              e.currentTarget.style.transform = 'scale(1.02)';
              e.currentTarget.style.borderColor = theme.primary.main;
              e.currentTarget.style.boxShadow = `0 4px 16px ${theme.primary.dim}`;
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'scale(1)';
            e.currentTarget.style.borderColor = isSelected
              ? theme.primary.main
              : theme.border.default;
            e.currentTarget.style.boxShadow = isSelected
              ? `0 0 0 2px ${theme.primary.dim}`
              : 'none';
          }}
        >
          {deviceId !== null && (
            <>
              <Button
                type="text"
                icon={isPaused ? <PlayCircleOutlined /> : <PauseOutlined />}
                aria-label={isPaused ? `继续窗口 ${i + 1}` : `暂停窗口 ${i + 1}`}
                aria-pressed={isPaused}
                title={isPaused ? '继续播放' : '暂停播放'}
                onClick={(event) => {
                  event.stopPropagation();
                  toggleWindowPause(i);
                }}
                onDoubleClick={(event) => event.stopPropagation()}
                style={{
                  position: 'absolute',
                  bottom: 8,
                  left: 8,
                  zIndex: 3,
                  width: 30,
                  height: 30,
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                  background: 'rgba(0, 0, 0, 0.45)',
                  borderRadius: 6,
                }}
              />
              <Button
                type="text"
                icon={<CameraOutlined />}
                aria-label={`抓拍窗口 ${i + 1}`}
                title="抓拍图片"
                loading={Boolean(snapshottingDevices[deviceId])}
                disabled={!device}
                onClick={(event) => {
                  event.stopPropagation();
                  if (device) void captureSnapshot(deviceId, device.name);
                }}
                onDoubleClick={(event) => event.stopPropagation()}
                style={{
                  position: 'absolute',
                  bottom: 8,
                  left: 44,
                  zIndex: 3,
                  width: 30,
                  height: 30,
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                  background: 'rgba(0, 0, 0, 0.45)',
                  borderRadius: 6,
                }}
              />
              <Button
                type="text"
                icon={isRecording ? <StopOutlined /> : <VideoCameraAddOutlined />}
                aria-label={isRecording ? `停止窗口 ${i + 1} 录像` : `开始窗口 ${i + 1} 录像`}
                aria-pressed={isRecording}
                title={isRecording ? '停止录像' : '开始录像'}
                loading={Boolean(recordingActions[deviceId])}
                disabled={!device}
                onClick={(event) => {
                  event.stopPropagation();
                  void toggleRecording(deviceId);
                }}
                onDoubleClick={(event) => event.stopPropagation()}
                style={{
                  position: 'absolute',
                  bottom: 8,
                  right: 8,
                  zIndex: 3,
                  width: 30,
                  height: 30,
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: isRecording ? '#ff7875' : '#fff',
                  background: 'rgba(0, 0, 0, 0.45)',
                  borderRadius: 6,
                }}
              />
              <div
                style={{
                  position: 'absolute',
                  top: 8,
                  right: 8,
                  zIndex: 3,
                }}
                onDoubleClick={(event) => event.stopPropagation()}
              >
                <Button
                  type="text"
                  icon={<CloseOutlined />}
                  aria-label={`关闭窗口 ${i + 1}`}
                  title="关闭视频"
                  onClick={(event) => {
                    event.stopPropagation();
                    closeWindow(i);
                  }}
                  style={{
                    width: 30,
                    height: 30,
                    padding: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                    background: 'rgba(0, 0, 0, 0.45)',
                    borderRadius: 6,
                  }}
                />
              </div>
            </>
          )}
          {device && info?.online ? (
            <>
              <VideoPlayer
                url={info.ts_url || info.flv_url}
                fallbackUrl={info.ts_url ? info.flv_url : undefined}
                live
                muted
                paused={isPaused}
                videoKey={`window-${i}`}
                onVideoElement={(key, element) => registerVideoElement(device.id, key, element)}
              />
              <div
                style={{
                  position: 'absolute',
                  top: 8,
                  left: 8,
                  zIndex: 2,
                  padding: '4px 12px',
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: 600,
                  color: '#fff',
                  background: 'rgba(0,0,0,0.45)',
                  backdropFilter: 'blur(4px)',
                }}
              >
                {device.name}
              </div>
            </>
          ) : device ? (
            <div
              style={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                color: theme.text.tertiary,
                gap: 8,
              }}
            >
              <div style={{ fontSize: 32 }}>📹</div>
              <div>{device.name}</div>
              <div style={{ fontSize: 12 }}>设备离线</div>
            </div>
          ) : (
            <div
              style={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                color: theme.text.tertiary,
                gap: 8,
              }}
            >
              <div style={{ fontSize: 32 }}>📺</div>
              <div style={{ fontSize: 12 }}>窗口 {i + 1}</div>
            </div>
          )}
        </div>
      );
    }

    return (
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${cols}, 1fr)`,
          gap: 12,
          padding: 16,
        }}
      >
        {cells}
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 64px)', gap: 16, padding: 16 }}>
      {/* 左侧设备树 */}
      <Card
        title="实时预览"
        extra={
          <Button icon={<ReloadOutlined />} loading={loading} onClick={refresh} size="small">
            刷新
          </Button>
        }
        style={{
          width: 280,
          height: '100%',
          background: theme.bg.elevated,
          border: `1px solid ${theme.border.default}`,
        }}
        bodyStyle={{
          padding: '12px 0',
          height: 'calc(100% - 57px)',
          overflow: 'auto',
        }}
      >
        {enabledDevices.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无启用设备"
            style={{ marginTop: 60 }}
          />
        ) : (
          <Tree
            showIcon
            treeData={treeData}
            onSelect={onDeviceSelect}
            onClick={onDeviceClick}
            selectedKeys={selectedTreeDeviceId ? [selectedTreeDeviceId.toString()] : []}
            style={{
              background: 'transparent',
              color: theme.text.primary,
            }}
          />
        )}
      </Card>

      {/* 右侧视频区域 */}
      <Card
        style={{
          flex: 1,
          height: '100%',
          background: theme.bg.elevated,
          border: `1px solid ${theme.border.default}`,
          position: 'relative',
        }}
        bodyStyle={{
          padding: 0,
          height: '100%',
          overflow: 'auto',
        }}
      >
        {renderVideoGrid()}

        {/* 布局切换按钮 - 右下角 */}
        <div
            className="slide-in-up"
            style={{
              position: 'absolute',
              bottom: 20,
              right: 20,
              display: 'flex',
              gap: 8,
              background: theme.bg.elevated,
              padding: 8,
              borderRadius: 12,
              border: `1px solid ${theme.border.default}`,
              boxShadow: '0 4px 16px rgba(0, 0, 0, 0.1)',
            }}
          >
            <Button
              type={layout === 1 ? 'primary' : 'default'}
              icon={<BorderOutlined />}
              onClick={() => {
                setLayout(1);
                setSelectedWindow((prev) => Math.min(prev, 0));
              }}
              style={{
                background: layout === 1 ? theme.primary.main : theme.bg.elevated,
                borderColor: layout === 1 ? theme.primary.main : theme.border.default,
              }}
            >
              单窗口
            </Button>
            <Button
              type={layout === 4 ? 'primary' : 'default'}
              icon={<AppstoreOutlined />}
              onClick={() => {
                setLayout(4);
                setSelectedWindow((prev) => Math.min(prev, 3));
              }}
              style={{
                background: layout === 4 ? theme.primary.main : theme.bg.elevated,
                borderColor: layout === 4 ? theme.primary.main : theme.border.default,
              }}
            >
              4窗口
            </Button>
            <Button
              type={layout === 9 ? 'primary' : 'default'}
              icon={<AppstoreOutlined />}
              onClick={() => {
                setLayout(9);
                setSelectedWindow((prev) => Math.min(prev, 8));
              }}
              style={{
                background: layout === 9 ? theme.primary.main : theme.bg.elevated,
                borderColor: layout === 9 ? theme.primary.main : theme.border.default,
              }}
            >
              9窗口
            </Button>
            <Button
              type={layout === 16 ? 'primary' : 'default'}
              icon={<AppstoreOutlined />}
              onClick={() => {
                setLayout(16);
                setSelectedWindow((prev) => Math.min(prev, 15));
              }}
              style={{
                background: layout === 16 ? theme.primary.main : theme.bg.elevated,
                borderColor: layout === 16 ? theme.primary.main : theme.border.default,
              }}
            >
              16窗口
            </Button>
          </div>
        )
      </Card>

      {/* 设备详情弹窗 */}
      <Modal
        open={!!selected}
        onCancel={() => {
          const deviceId = selected?.id;
          setSelected(null);
          if (deviceId != null) stopStreamIfUnused(deviceId, selectedDeviceIds, true);
        }}
        footer={null}
        title={selected?.name}
        width={820}
        destroyOnClose
      >
        {selected && (
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <div
                style={{
                  aspectRatio: '16 / 9',
                  background: '#000',
                  borderRadius: 4,
                  overflow: 'hidden',
                }}
              >
                {streams[selected.id]?.online ? (
                    <VideoPlayer
                      url={streams[selected.id].ts_url || streams[selected.id].flv_url}
                      fallbackUrl={
                        streams[selected.id].ts_url ? streams[selected.id].flv_url : undefined
                      }
                      live
                      muted={false}
                      videoKey="details"
                      onVideoElement={(key, element) =>
                        registerVideoElement(selected.id, key, element)
                      }
                    />
                ) : (
                  <div
                    style={{
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#999',
                    }}
                  >
                    离线
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                <Button
                  icon={<CameraOutlined />}
                  loading={Boolean(snapshottingDevices[selected.id])}
                  onClick={() => void captureSnapshot(selected.id, selected.name)}
                >
                  抓拍
                </Button>
                <Button
                  icon={streams[selected.id]?.recording ? <StopOutlined /> : <VideoCameraAddOutlined />}
                  loading={Boolean(recordingActions[selected.id])}
                  onClick={() => void toggleRecording(selected.id)}
                >
                  {streams[selected.id]?.recording ? '停止录像' : '开始录像'}
                </Button>
              </div>
            </div>
            {selected.ptz_enabled && <PTZPanel deviceId={selected.id} />}
          </div>
        )}
      </Modal>
    </div>
  );
}
