// Sensor positions for the 7 IMU sensors
export enum SensorPosition {
  None = 0,
  LeftForearm,
  RightForearm,
  LeftUpperArm,
  RightUpperArm,
  LeftShoulder,
  RightShoulder,
  Trunk,
}

// Calibration status levels
export enum CalibrationStatus {
  Unknown = 0,
  Unreliable = 1,
  Low,
  Medium,
  High,
}

// ADL Task category
export type TaskCategory = "upper_extremity" | "bilateral" | "self_care";

// ADL Task definition
export interface AdlTask {
  id: string;
  name: string;
  instruction: string;
  duration_seconds: number;
  category: TaskCategory;
}

// Marker types for event logging
export type MarkerType =
  | "task_start"
  | "task_end"
  | "session_start"
  | "session_end";

// Marker structure matching backend
export interface Marker {
  marker_type: MarkerType;
  task_id: string;
  timestamp: number;
  session_id?: string;
}

// IMU sample data structure
export interface ImuSample {
  timestamp: number;
  stream_id: number;
  sensor_position: string;
  calibration_status_accelerometer: number;
  calibration_status_gyroscope: number;
  calibration_status_rotation: number;
  has_data_accelerometer: boolean;
  has_data_gyroscope: boolean;
  has_data_rotation: boolean;
  quat_i: number;
  quat_j: number;
  quat_k: number;
  quat_real: number;
  accel_x: number;
  accel_y: number;
  accel_z: number;
  gyro_x: number;
  gyro_y: number;
  gyro_z: number;
  gravity_x: number;
  gravity_y: number;
  gravity_z: number;
}

// Session data returned from backend
export interface SessionData {
  session_id: string;
  start_time: number;
  markers: Marker[];
  samples: ImuSample[];
  marker_count: number;
  sample_count: number;
}

// Recording session state
export interface RecordingState {
  is_recording: boolean;
  session_id: string | null;
  start_time: number | null;
}

// Stream topic information
export interface Topic {
  schema_name: string;
  type: string;
  serialization_type: string;
}

// Stream information
export interface Stream {
  id: number;
  name: string;
  topics: Topic[];
}

// Experiment phase/tab
export type ExperimentPhase =
  | "connection"
  | "stream-selection"
  | "calibration"
  | "experiment"
  | "export";

// Helper functions
export function sensor_position_to_string(position: SensorPosition): string {
  switch (position) {
    case SensorPosition.LeftForearm:
      return "Left Forearm";
    case SensorPosition.RightForearm:
      return "Right Forearm";
    case SensorPosition.LeftUpperArm:
      return "Left Upper Arm";
    case SensorPosition.RightUpperArm:
      return "Right Upper Arm";
    case SensorPosition.LeftShoulder:
      return "Left Shoulder";
    case SensorPosition.RightShoulder:
      return "Right Shoulder";
    case SensorPosition.Trunk:
      return "Trunk";
    case SensorPosition.None:
      return "N/A";
  }
}

export function parse_sensor_position_from_string(str: string): SensorPosition {
  switch (str) {
    case "Left Forearm":
      return SensorPosition.LeftForearm;
    case "Right Forearm":
      return SensorPosition.RightForearm;
    case "Left Upper Arm":
      return SensorPosition.LeftUpperArm;
    case "Right Upper Arm":
      return SensorPosition.RightUpperArm;
    case "Left Shoulder":
      return SensorPosition.LeftShoulder;
    case "Right Shoulder":
      return SensorPosition.RightShoulder;
    case "Trunk":
      return SensorPosition.Trunk;
    default:
      return SensorPosition.None;
  }
}

export function calibration_status_to_string(
  status: CalibrationStatus,
): string {
  switch (status) {
    case CalibrationStatus.Unknown:
      return "Unknown";
    case CalibrationStatus.Unreliable:
      return "Unreliable";
    case CalibrationStatus.Low:
      return "Low";
    case CalibrationStatus.Medium:
      return "Medium";
    case CalibrationStatus.High:
      return "High";
  }
}

// All sensor positions for the full ADL experiment (7 sensors)
export const ALL_SENSOR_POSITIONS: SensorPosition[] = [
  SensorPosition.LeftForearm,
  SensorPosition.RightForearm,
  SensorPosition.LeftUpperArm,
  SensorPosition.RightUpperArm,
  SensorPosition.LeftShoulder,
  SensorPosition.RightShoulder,
  SensorPosition.Trunk,
];

// Minimum sensor positions for testing (subset of full configuration)
export const TEST_SENSOR_POSITIONS: SensorPosition[] = [SensorPosition.Trunk];

// Set to true to enable test mode with reduced sensor requirements
export const TEST_MODE = false;

// Required sensor positions - uses test subset or full set based on TEST_MODE
export const REQUIRED_SENSOR_POSITIONS: SensorPosition[] = TEST_MODE
  ? TEST_SENSOR_POSITIONS
  : ALL_SENSOR_POSITIONS;
