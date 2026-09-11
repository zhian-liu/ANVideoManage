import client from './client';
import type {
  Device,
  DeviceInput,
  DirectoryListing,
  Recording,
  RecordStatus,
  SnapshotSaveResult,
  StorageSettings,
  StreamInfo,
  StreamProtocolsInfo,
  TokenResponse,
  User,
  GbConfig,
  GbConfigResponse,
  GbDevice,
  GbDeviceInput,
  GbChannel,
  GbLease,
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

export async function getGbConfig(): Promise<GbConfigResponse> {
  return (await client.get('/gb28181/config')).data;
}

export async function saveGbConfig(input: GbConfig): Promise<GbConfigResponse> {
  return (await client.put('/gb28181/config', input, { timeout: 90000 })).data;
}

export async function listGbDevices(): Promise<GbDevice[]> {
  return (await client.get('/gb28181/devices')).data;
}

export async function createGbDevice(input: GbDeviceInput): Promise<GbDevice> {
  return (await client.post('/gb28181/devices', input)).data;
}

export async function updateGbDevice(id: string, input: Partial<Omit<GbDeviceInput, 'id'>>): Promise<GbDevice> {
  return (await client.put(`/gb28181/devices/${id}`, input)).data;
}

export async function syncGbCatalog(id: string): Promise<void> {
  await client.post(`/gb28181/devices/${id}/catalog`);
}

export async function listGbChannels(id: string): Promise<GbChannel[]> {
  return (await client.get(`/gb28181/devices/${id}/channels`)).data;
}

export async function acquireGbLease(id: number, leaseId?: string): Promise<GbLease> {
  return (await client.post(`/streams/${id}/lease`, { lease_id: leaseId }, { timeout: 135000 })).data;
}

export async function releaseGbLease(id: number, leaseId: string): Promise<void> {
  await client.delete(`/streams/${id}/lease/${leaseId}`);
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

export async function browseDirectories(path = '', signal?: AbortSignal): Promise<DirectoryListing> {
  const { data } = await client.get('/settings/directories', {
    params: { path },
    signal,
    timeout: 15000,
  });
  return data;
}

export async function updateStorageSettings(input: {
  recording_path: string;
  snapshot_path: string;
  recording_retention_days: number;
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

export async function deleteRecording(id: number): Promise<void> {
  await client.delete(`/recordings/${id}`);
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
