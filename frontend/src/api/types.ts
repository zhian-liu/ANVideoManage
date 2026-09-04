export interface User {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export type AccessType = 'onvif' | 'cloud' | 'sdk';

export interface Device {
  id: number;
  name: string;
  vendor: string;
  access_type: AccessType;
  ip: string;
  port: number;
  username: string;
  password: string;
  rtsp_url: string;
  onvif_port: number;
  ptz_enabled: boolean;
  record_enabled: boolean;
  enabled: boolean;
  status: 'unknown' | 'online' | 'offline';
  created_at: string;
  updated_at: string;
}

export interface DeviceInput {
  name: string;
  vendor: string;
  access_type: AccessType;
  ip: string;
  port: number;
  username: string;
  password: string;
  rtsp_url: string;
  onvif_port: number;
  ptz_enabled: boolean;
  record_enabled: boolean;
  enabled: boolean;
}

export interface StreamInfo {
  device_id: number;
  online: boolean;
  recording: boolean;
  ts_url: string;
  flv_url: string;
  hls_url: string;
}

export interface StreamProtocol {
  key: string;
  name: string;
  url: string;
  description: string;
}

export interface StreamProtocolsInfo {
  device_id: number;
  stream: string;
  online: boolean;
  protocols: StreamProtocol[];
}

export interface RecordStatus {
  device_id: number;
  recording: boolean;
}

export interface StorageSettings {
  recording_path: string;
  snapshot_path: string;
  recording_path_default: string;
  snapshot_path_default: string;
  backend_base: string;
  zlm_api_base: string;
  zlm_http_port: number;
  zlm_rtsp_port: number;
  zlm_rtmp_port: number;
}

export interface SnapshotSaveResult {
  ok: boolean;
  file_name: string;
  file_path: string;
}

export interface Recording {
  id: number;
  device_id: number;
  start_time: string;
  end_time: string;
  file_path: string;
  file_name: string;
  file_size: number;
  created_at: string;
}
