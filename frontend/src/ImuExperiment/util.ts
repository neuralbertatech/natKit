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

export enum CalibrationStatus {
    Unknown = 0,
    Unreliable = 1,
    Low,
    Medium,
    High,
}

export function sensor_position_to_string(position: SensorPosition) {
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

export function parse_sensor_position_from_string(str: string) {
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