export interface RecordedRunSummary {
  session_id: string;
  run_index: number;
  start_us: number;
  end_us: number | null;
  device_ids: string[];
  purpose: string;
  participant_id: string;
  protocol_id: string;
  tags: string[];
  notes: string;
  marker_count: number;
  last_activity_us: number;
}

export interface HelloMessage {
  type: "hello";
  service: string;
  broker: string;
  worker_id: string;
  slot_count: number;
  default_principal_id: string;
  authenticated_user?: {
    username: string;
    display_name: string;
    is_admin: boolean;
    shared_compute_access?: boolean;
  } | null;
}

export interface WorkerSummary {
  worker_id: string;
  slot_count: number;
  visible_slot_count: number;
  assigned_slot_count: number;
  queued_job_count: number;
  running_job_count: number;
  assigned_job_count: number;
  recovered_job_count?: number;
  restart_attempt_count?: number;
  busy_ratio_60s: number;
  last_heartbeat_us: number;
  worker_source?: string;
  worker_status?: string;
  slot_inventory_ready?: boolean;
  accepting_new_jobs?: boolean;
  drain_remaining_job_count?: number;
  drain_ready?: boolean;
}

export interface RecordedRunsMessage {
  type: "recorded_runs";
  request_id?: string | null;
  broker: string;
  runs: RecordedRunSummary[];
}

export interface WorkersMessage {
  type: "workers";
  request_id?: string | null;
  principal_id?: string | null;
  workers: WorkerSummary[];
}

export interface WorkerDrainStatusMessage extends WorkerSummary {
  type: "worker_drain_status";
  request_id?: string | null;
  timed_out: boolean;
}

export interface JobAcceptedMessage {
  type: "job_accepted";
  request_id?: string | null;
  job_id: string;
  status: string;
  message: string;
  thread_slot_id: string;
  priority: number;
}

export interface JobStatusMessage {
  type: "job_status";
  request_id?: string | null;
  job_id: string;
  job_type?: string;
  owner_principal_id?: string | null;
  worker_id?: string;
  thread_slot_id?: string;
  priority?: number;
  status:
    | "pending"
    | "queued"
    | "running"
    | "cancelling"
    | "completed"
    | "failed"
    | "cancelled";
  message: string;
  report?: Record<string, unknown> | null;
  error?: string | null;
  traceback_text?: string | null;
  stop_requested?: boolean;
  created_at_us?: number;
  started_at_us?: number | null;
  finished_at_us?: number | null;
  restart_count?: number;
}

export interface ThreadSlotSummary {
  slot_id: string;
  worker_id: string;
  slot_index: number;
  owner_principal_id?: string | null;
  access_mode?: "shared" | "dedicated";
  dedicated_username?: string | null;
  current_job_id?: string | null;
  queue_depth: number;
  assigned_job_count: number;
  running_job_count: number;
  busy_ratio_60s: number;
  completed_jobs: number;
  failed_jobs: number;
  cancelled_jobs: number;
  restart_attempt_count?: number;
}

export interface ThreadSlotsMessage {
  type: "thread_slots";
  request_id?: string | null;
  worker_id: string;
  principal_id?: string | null;
  slots: ThreadSlotSummary[];
}

export interface JobListMessage {
  type: "job_list";
  request_id?: string | null;
  principal_id?: string | null;
  thread_slot_id?: string | null;
  jobs: JobStatusMessage[];
}

export interface WorkerJobClaimMessage {
  type: "worker_job_claim";
  request_id?: string | null;
  worker_id: string;
  slot_id: string;
  job:
    | (JobStatusMessage & {
        request: Record<string, unknown>;
      })
    | null;
}

export interface ErrorMessage {
  type: "error";
  request_id?: string | null;
  message: string;
}

export type MlControlPlaneMessage =
  | HelloMessage
  | RecordedRunsMessage
  | WorkersMessage
  | WorkerDrainStatusMessage
  | JobAcceptedMessage
  | JobStatusMessage
  | ThreadSlotsMessage
  | JobListMessage
  | WorkerJobClaimMessage
  | ErrorMessage;

export interface ListRecordedRunsAction {
  action: "list_recorded_runs";
  request_id?: string;
  broker?: string;
}

export interface ListWorkersAction {
  action: "list_workers";
  request_id?: string;
  principal_id?: string;
  show_all?: boolean;
}

export interface StartTrainValidateJobAction {
  action: "start_train_validate_job";
  request_id?: string;
  broker?: string;
  owner_principal_id?: string;
  thread_slot_id: string;
  priority?: number;
  families?: string[];
  selected_fields?: string[];
  train_runs: Array<{ session_id: string; run_index: number }>;
  eval_runs: Array<{ session_id: string; run_index: number }>;
  rest_gesture?: string;
  active_gesture?: string;
  window_ms?: number;
  hop_ms?: number;
  vote_windows?: number;
  confidence_threshold?: number;
  min_hold_windows?: number;
  emit_only_during_cue_hold?: boolean;
}

export interface GetJobStatusAction {
  action: "get_job_status";
  request_id?: string;
  job_id: string;
  principal_id?: string;
}

export interface ListThreadSlotsAction {
  action: "list_thread_slots";
  request_id?: string;
  principal_id?: string;
  show_all?: boolean;
}

export interface ListJobsAction {
  action: "list_jobs";
  request_id?: string;
  principal_id?: string;
  thread_slot_id?: string;
  show_all?: boolean;
}

export interface AssignThreadSlotsAction {
  action: "assign_thread_slots";
  request_id?: string;
  principal_id: string;
  slot_ids: string[];
}

export interface ReleaseThreadSlotsAction {
  action: "release_thread_slots";
  request_id?: string;
  principal_id: string;
  slot_ids: string[];
}

export interface SetSlotComputePolicyAction {
  action: "set_slot_compute_policy";
  request_id?: string;
  slot_id: string;
  access_mode: "shared" | "dedicated";
  dedicated_username?: string;
  show_all?: boolean;
}

export interface UpdateWorkerStatusAction {
  action: "update_worker_status";
  request_id?: string;
  worker_id: string;
  status: "online" | "draining";
  principal_id?: string;
}

export interface WaitWorkerDrainReadyAction {
  action: "wait_worker_drain_ready";
  request_id?: string;
  worker_id: string;
  timeout_s?: number;
}

export interface UpdateJobAction {
  action: "update_job";
  request_id?: string;
  job_id: string;
  priority: number;
  principal_id?: string;
}

export interface StopJobAction {
  action: "stop_job";
  request_id?: string;
  job_id: string;
  principal_id?: string;
}

export interface RecoverJobAction {
  action: "recover_job";
  request_id?: string;
  job_id: string;
  principal_id?: string;
}

export interface RecoverWorkerAction {
  action: "recover_worker";
  request_id?: string;
  worker_id: string;
  principal_id?: string;
}

export interface ClaimWorkerSlotJobAction {
  action: "claim_worker_slot_job";
  request_id?: string;
  worker_id: string;
  slot_id: string;
}

export interface ReportWorkerJobStateAction {
  action: "report_worker_job_state";
  request_id?: string;
  worker_id: string;
  job_id: string;
  status: "running" | "completed" | "failed" | "cancelled";
  message?: string;
  report?: Record<string, unknown>;
  error?: string;
  traceback_text?: string;
}

export type MlControlPlaneAction =
  | ListRecordedRunsAction
  | ListWorkersAction
  | StartTrainValidateJobAction
  | GetJobStatusAction
  | ListThreadSlotsAction
  | ListJobsAction
  | AssignThreadSlotsAction
  | ReleaseThreadSlotsAction
  | UpdateWorkerStatusAction
  | WaitWorkerDrainReadyAction
  | UpdateJobAction
  | SetSlotComputePolicyAction
  | ClaimWorkerSlotJobAction
  | ReportWorkerJobStateAction
  | StopJobAction
  | RecoverJobAction
  | RecoverWorkerAction;
