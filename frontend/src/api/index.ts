import client from './client';
import type {
  Device,
  DeviceInput,
  Recording,
  RecordStatus,
  SnapshotSaveResult,
  StorageSettings,
  StreamInfo,
  StreamProtocolsInfo,
  TokenResponse,
  User,
} from './types';

export async function login(
  username: string,
  password: string
): Promise<TokenResponse> {
  const { data } = await client.post('/auth/login', { username, password });
  return data;
}

export async function me(): Promise<User> {
  const { data } = await client.get('/auth/me');
  return data;
}

export async function listDevices(): Promise<Device[]> {
  const { data } = await client.get('/devices');
  return data;
}

export async function createDevice(input: DeviceInput): Promise<Device> {
  const { data } = await client.post('/devices', input);
  return data;
}

export async function updateDevice(
  id: number,
  input: Partial<DeviceInput>
): Promise<Device> {
  const { data } = await client.put(`/devices/${id}`, input);
  return data;
}

export async function deleteDevice(id: number): Promise<void> {
  await client.delete(`/devices/${id}`);
}

export async function getStreamInfo(id: number): Promise<StreamInfo> {
  const { data } = await client.get(`/streams/${id}`);
  return data;
}

export async function getStreamProtocols(id: number): Promise<StreamProtocolsInfo> {
  const { data } = await client.get(`/streams/${id}/protocols`);
  return data;
}

export async function startStream(id: number): Promise<void> {
  await client.post(`/streams/${id}/start`);
}

export async function stopStream(id: number): Promise<void> {
  await client.post(`/streams/${id}/stop`);
}

export async function captureSnapshot(id: number): Promise<Blob> {
  const { data } = await client.get(`/streams/${id}/snapshot`, {
    responseType: 'blob',
  });
  return data;
}

export async function saveSnapshot(id: number): Promise<SnapshotSaveResult> {
  const { data } = await client.post(`/streams/${id}/snapshot/save`);
  return data;
}

export async function getSettings(): Promise<StorageSettings> {
  const { data } = await client.get('/settings');
  return data;
}

export async function updateStorageSettings(input: {
  recording_path: string;
  snapshot_path: string;
}): Promise<StorageSettings> {
  const { data } = await client.put('/settings/storage', input);
  return data;
}

export async function startRecording(id: number): Promise<RecordStatus> {
  const { data } = await client.post(`/streams/${id}/record/start`);
  return data;
}

export async function stopRecording(id: number): Promise<RecordStatus> {
  const { data } = await client.post(`/streams/${id}/record/stop`);
  return data;
}

export async function getRecordingStatus(id: number): Promise<RecordStatus> {
  const { data } = await client.get(`/streams/${id}/record/status`);
  return data;
}

export async function listRecordings(params?: {
  device_id?: number;
  start?: string;
  end?: string;
}): Promise<Recording[]> {
  const { data } = await client.get('/recordings', { params });
  return data;
}

export function recordingFileUrl(id: number): string {
  // <video> 标签无法携带 Authorization 头，改用 query 参数传令牌
  const token = localStorage.getItem('token') ?? '';
  return `/api/recordings/${id}/file?token=${encodeURIComponent(token)}`;
}

export async function ptzMove(
  id: number,
  direction: 'left' | 'right' | 'up' | 'down',
  speed = 0.5
): Promise<void> {
  await client.post(`/devices/${id}/ptz/move`, { direction, speed });
}

export async function ptzZoom(
  id: number,
  direction: 'in' | 'out',
  speed = 0.5
): Promise<void> {
  await client.post(`/devices/${id}/ptz/zoom`, { direction, speed });
}

export async function ptzStop(id: number): Promise<void> {
  await client.post(`/devices/${id}/ptz/stop`);
}
