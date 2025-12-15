// Types for Stream Viewer WebSocket communication

export interface StreamTopic {
  schema_name: string;
  type: "Data" | "Meta";
  serialization_type: string;
}

export interface StreamInfo {
  topics: StreamTopic[];
}

export interface StreamListMessage {
  type: "stream_list";
  streams: Record<string, StreamInfo>;
}

export interface StatusMessage {
  type: "status";
  connected: boolean;
  subscribed_streams: number[];
}

export interface ErrorMessage {
  type: "error";
  message: string;
}

export interface ImuVector3 {
  x: number;
  y: number;
  z: number;
}

export interface ImuQuaternion {
  real: number;
  i: number;
  j: number;
  k: number;
}

export interface ImuData {
  accel: ImuVector3;
  gyro: ImuVector3;
  quat: ImuQuaternion;
}

export interface ImuAccuracies {
  accelerometer: number;
  gyroscope: number;
  rotation: number;
}

export interface ImuHasData {
  accelerometer: boolean;
  gyroscope: boolean;
  rotation: boolean;
}

export interface EncodingInfo {
  type: string;
  size: number;
}

export interface ImuDataMessage {
  type: "imu_data";
  stream_id: number;
  timestamp: number;
  encoding: EncodingInfo;
  data: ImuData;
  accuracies: ImuAccuracies;
  has_data: ImuHasData;
}

export interface ImuSample {
  timestamp: number;
  data: ImuData;
  accuracies: ImuAccuracies;
  has_data: ImuHasData;
}

export interface ImuBulkDataMessage {
  type: "imu_bulk_data";
  stream_id: number;
  encoding: EncodingInfo;
  samples: ImuSample[];
}

// Muse EEG data types
export interface MuseEegData {
  tp9: number[]; // 12 samples - left ear
  af7: number[]; // 12 samples - left forehead
  af8: number[]; // 12 samples - right forehead
  tp10: number[]; // 12 samples - right ear
}

export interface MusePpgData {
  ppg0: number[]; // 6 samples
  ppg1: number[]; // 6 samples
  ppg2: number[]; // 6 samples
}

export interface MuseHasData {
  eeg: boolean;
  accel: boolean;
  gyro: boolean;
  ppg: boolean;
}

export interface MuseSample {
  timestamp: number;
  eeg_sequence: number;
  motion_sequence: number;
  eeg: MuseEegData;
  accel: ImuVector3[]; // 3 motion samples
  gyro: ImuVector3[]; // 3 motion samples
  ppg: MusePpgData;
  has_data: MuseHasData;
}

export interface MuseDataMessage {
  type: "muse_data";
  stream_id: number;
  timestamp: number;
  eeg_sequence: number;
  motion_sequence: number;
  encoding: EncodingInfo;
  eeg: MuseEegData;
  accel: ImuVector3[];
  gyro: ImuVector3[];
  ppg: MusePpgData;
  has_data: MuseHasData;
}

export interface MuseBulkDataMessage {
  type: "muse_bulk_data";
  stream_id: number;
  encoding: EncodingInfo;
  samples: MuseSample[];
}

export type WebSocketMessage =
  | StreamListMessage
  | StatusMessage
  | ErrorMessage
  | ImuDataMessage
  | ImuBulkDataMessage
  | MuseDataMessage
  | MuseBulkDataMessage;

// Client-to-server messages
export interface SubscribeAction {
  action: "subscribe";
  stream_ids: number[];
}

export interface UnsubscribeAction {
  action: "unsubscribe";
  stream_ids: number[];
}

export interface GetStreamsAction {
  action: "get_streams";
}

export type ClientAction =
  | SubscribeAction
  | UnsubscribeAction
  | GetStreamsAction;
