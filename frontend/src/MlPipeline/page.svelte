<script lang="ts">
  import { onMount } from "svelte";
  import { getChannelFieldOptions } from "./fieldSelection";
  import type {
    HelloMessage,
    JobStatusMessage,
    RecordedRunSummary,
    ThreadSlotSummary,
    WorkerSummary,
  } from "./types";
  import { MlControlPlaneWebSocket, type ConnectionState } from "./websocket";
  import { StreamViewerWebSocket } from "../StreamViewer/websocket";
  import type {
    DataSchemaDescriptor,
    EmgDataMessage,
    ErrorMessage as StreamViewerErrorMessage,
    StreamInfo,
    StreamListMessage,
  } from "../StreamViewer/types";

  type FamilyId = "lda" | "linear_svm" | "random_forest";

  interface JobEvent {
    jobId: string;
    status: string;
    message: string;
    timestamp: string;
  }

  type WorkerRuntimeStatus =
    | "online"
    | "starting"
    | "draining"
    | "stalled"
    | "offline"
    | "missing"
    | "degraded";
  type SlotFilterMode = "all" | "mine" | "shared" | "submittable" | "active";

  const recoverableWorkerStatuses = new Set(["stalled", "offline", "missing"]);
  const drainingWorkerStatuses = new Set(["draining"]);

  const familyDescriptions: Record<FamilyId, { label: string; detail: string }> = {
    lda: {
      label: "LDA",
      detail: "Fast linear baseline with a small runtime footprint.",
    },
    linear_svm: {
      label: "Linear SVM",
      detail:
        "Linear margin-based classifier that is often stronger than LDA on noisier data.",
    },
    random_forest: {
      label: "Random Forest",
      detail: "Nonlinear tree ensemble that can fit more complex patterns at higher runtime cost.",
    },
  };

  function defaultControlPlaneUrl(): string {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const host = window.location.hostname || "127.0.0.1";
    return `${protocol}://${host}:8786`;
  }

  function defaultStreamViewerUrl(): string {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}/ws/stream_viewer`;
  }

  function runKey(run: RecordedRunSummary): string {
    return `${run.session_id}:${run.run_index}`;
  }

  function formatTimestamp(timestampUs: number | null | undefined): string {
    if (!timestampUs) {
      return "-";
    }
    return new Date(timestampUs / 1000).toLocaleString();
  }

  function formatWindow(startUs: number, endUs: number | null): string {
    return `${formatTimestamp(startUs)} - ${formatTimestamp(endUs)}`;
  }

  function formatPercent(value: number): string {
    return `${Math.round(value * 100)}%`;
  }

  function formatHeartbeat(timestampUs: number | null | undefined): string {
    if (!timestampUs) {
      return "-";
    }
    const seconds = Math.max(0, Math.round(Date.now() / 1000 - timestampUs / 1_000_000));
    if (seconds < 2) {
      return "just now";
    }
    if (seconds < 60) {
      return `${seconds}s ago`;
    }
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) {
      return `${minutes}m ago`;
    }
    const hours = Math.round(minutes / 60);
    return `${hours}h ago`;
  }

  function workerStatus(worker: WorkerSummary | null | undefined): WorkerRuntimeStatus {
    return (worker?.worker_status ?? "online") as WorkerRuntimeStatus;
  }

  function isWorkerDraining(worker: WorkerSummary | null | undefined): boolean {
    return drainingWorkerStatuses.has(workerStatus(worker));
  }

  function workerDrainLabel(worker: WorkerSummary | null | undefined): string {
    if (!worker || !isWorkerDraining(worker)) {
      return "accepting";
    }
    if (worker.drain_ready) {
      return "ready";
    }
    const remaining = Math.max(0, worker.drain_remaining_job_count ?? worker.assigned_job_count ?? 0);
    return `${remaining} remaining`;
  }

  function toggleSetValue<T>(source: Set<T>, value: T): Set<T> {
    const next = new Set(source);
    if (next.has(value)) {
      next.delete(value);
    } else {
      next.add(value);
    }
    return next;
  }

  let controlPlaneUrl = $state(defaultControlPlaneUrl());
  let broker = $state("");
  let principalId = $state("default");
  let defaultPrincipalId = "default";
  let authenticatedUser = $state<HelloMessage["authenticated_user"]>(null);
  let showAllSchedulerState = $state(false);
  let selectedThreadSlotId = $state("");
  let jobPriority = $state(0);
  let restGesture = $state("rest");
  let activeGesture = $state("fist");
  let windowMs = $state(200);
  let hopMs = $state(50);
  let voteWindows = $state(5);
  let confidenceThreshold = $state(0.6);
  let minHoldWindows = $state(2);
  let emitOnlyDuringCueHold = $state(false);
  let descriptorStreams = $state<Record<string, StreamInfo>>({});
  let selectedDescriptorStreamId = $state("");
  let descriptorPreview = $state<EmgDataMessage | null>(null);
  let selectedInputFields = $state(new Set<string>());
  let inputFieldsInitialized = $state(false);

  let connectionState = $state<ConnectionState>("disconnected");
  let workerId = $state("");
  let workers = $state<WorkerSummary[]>([]);
  let runs = $state<RecordedRunSummary[]>([]);
  let threadSlots = $state<ThreadSlotSummary[]>([]);
  let jobs = $state<JobStatusMessage[]>([]);
  let trainSelection = $state(new Set<string>());
  let evalSelection = $state(new Set<string>());
  let selectedFamilies = $state(new Set<FamilyId>(["lda", "linear_svm", "random_forest"]));
  let latestError = $state("");
  let latestInfo = $state("");
  let activeJobId = $state("");
  let activeJobStatus = $state<JobStatusMessage | null>(null);
  let latestReport = $state<Record<string, unknown> | null>(null);
  let jobEvents = $state<JobEvent[]>([]);
  let priorityDrafts = $state<Record<string, number>>({});
  let supportsListWorkers = $state(true);
  let supportsListThreadSlots = $state(true);
  let supportsListJobs = $state(true);
  let slotFilterMode = $state<SlotFilterMode>("all");
  let adminSelectedSlotAccessMode = $state<"shared" | "dedicated">("shared");
  let adminSelectedSlotDedicatedUsername = $state("");

  let wsManager: MlControlPlaneWebSocket | null = null;
  let descriptorWsManager: StreamViewerWebSocket | null = null;
  let descriptorSubscribedStreamId: string | null = null;

  const normalizedPrincipalId = $derived(principalId.trim());
  const isAuthenticatedAdmin = $derived(!!authenticatedUser?.is_admin);
  const hasSharedComputeAccess = $derived(
    !!authenticatedUser?.shared_compute_access || isAuthenticatedAdmin,
  );
  const emgDescriptorStreams = $derived.by(() =>
    Object.entries(descriptorStreams)
      .map(([streamId, info]) => ({
        streamId,
        descriptor: info.topics.find(
          (topic) =>
            topic.descriptor?.schema_name === "ExgPillEmgDataSchemaV1" ||
            topic.descriptor?.schema_name ===
              "ExgPillEmgTransformDataSchemaV1" ||
            topic.descriptor?.schema_name === "NatSignalFrameDataSchemaV1",
        )
          ?.descriptor,
      }))
      .filter(
        (
          stream,
        ): stream is { streamId: string; descriptor: DataSchemaDescriptor } =>
          stream.descriptor !== undefined,
      ),
  );
  const selectedDescriptor = $derived(
    emgDescriptorStreams.find((stream) => stream.streamId === selectedDescriptorStreamId)?.descriptor ??
      emgDescriptorStreams[0]?.descriptor,
  );
  const emgChannelFieldOptions = $derived(
    getChannelFieldOptions(selectedDescriptor, descriptorPreview),
  );

  function slotVisibleToViewer(slot: ThreadSlotSummary): boolean {
    if (showAllSchedulerState && isAuthenticatedAdmin) {
      return true;
    }
    if (slot.access_mode === "dedicated") {
      return slot.dedicated_username === normalizedPrincipalId || isAuthenticatedAdmin;
    }
    return hasSharedComputeAccess;
  }

  const visibleThreadSlots = $derived(
    showAllSchedulerState ? threadSlots : threadSlots.filter((slot) => slotVisibleToViewer(slot)),
  );
  const scopedJobs = $derived(
    jobs.filter(
      (job) =>
        showAllSchedulerState ||
        !job.owner_principal_id ||
        job.owner_principal_id === normalizedPrincipalId,
    ),
  );
  const visibleJobs = $derived.by(() =>
    jobs
      .filter(
        (job) =>
          (showAllSchedulerState ||
            !job.owner_principal_id ||
            job.owner_principal_id === normalizedPrincipalId) &&
          (!selectedThreadSlotId || job.thread_slot_id === selectedThreadSlotId),
      )
      .sort((a, b) => {
        const aTerminal =
          a.status === "completed" || a.status === "failed" || a.status === "cancelled";
        const bTerminal =
          b.status === "completed" || b.status === "failed" || b.status === "cancelled";
        if (aTerminal !== bTerminal) {
          return aTerminal ? 1 : -1;
        }
        return (b.priority ?? 0) - (a.priority ?? 0);
      }),
  );
  const selectedThreadSlot = $derived(
    visibleThreadSlots.find((slot) => slot.slot_id === selectedThreadSlotId) ?? null,
  );
  const workersById = $derived(new Map(workers.map((worker) => [worker.worker_id, worker])));
  const selectedThreadSlotWorker = $derived(
    selectedThreadSlot && selectedThreadSlot.worker_id
      ? workersById.get(selectedThreadSlot.worker_id)
      : undefined,
  );
  const claimedVisibleSlotCount = $derived(
    visibleThreadSlots.filter(
      (slot) =>
        slot.access_mode === "dedicated" && slot.dedicated_username === normalizedPrincipalId,
    ).length,
  );
  const unassignedVisibleSlotCount = $derived(
    visibleThreadSlots.filter((slot) => slot.access_mode !== "dedicated").length,
  );
  const claimableVisibleSlotCount = $derived(
    visibleThreadSlots.filter((slot) => slot.access_mode === "shared").length,
  );
  const submittableVisibleSlotCount = $derived(
    visibleThreadSlots.filter((slot) => slotIsSubmittableByPrincipal(slot)).length,
  );
  const visibleDrainingWorkerCount = $derived(
    workers.filter((worker) => isWorkerDraining(worker)).length,
  );
  const visibleDrainingSlotCount = $derived(
    visibleThreadSlots.filter((slot) => isSlotOnDrainingWorker(slot)).length,
  );
  const filteredThreadSlots = $derived(
    visibleThreadSlots.filter((slot) => slotMatchesFilter(slot)),
  );
  const activeScopedJobs = $derived(
    scopedJobs.filter(
      (job) => job.status !== "completed" && job.status !== "failed" && job.status !== "cancelled",
    ),
  );
  const scopedRestartAttemptCount = $derived(
    scopedJobs.reduce((count, job) => count + Math.max(0, job.restart_count ?? 0), 0),
  );
  const scopedQueuedJobCount = $derived(
    activeScopedJobs.filter((job) => job.status === "queued").length,
  );
  const scopedRunningJobCount = $derived(
    activeScopedJobs.filter((job) => job.status === "running" || job.status === "cancelling")
      .length,
  );
  const scopedRecoverableJobCount = $derived(
    activeScopedJobs.filter((job) => canRecoverJob(job)).length,
  );
  const visibleRecoverableWorkerCount = $derived(
    workers.filter((worker) => canRecoverWorker(worker)).length,
  );

  $effect(() => {
    if (selectedThreadSlot) {
      adminSelectedSlotAccessMode =
        selectedThreadSlot.access_mode === "dedicated" ? "dedicated" : "shared";
      adminSelectedSlotDedicatedUsername = selectedThreadSlot.dedicated_username ?? "";
    }
  });

  $effect(() => {
    if (filteredThreadSlots.length && !filteredThreadSlots.some((slot) => slot.slot_id === selectedThreadSlotId)) {
      selectedThreadSlotId = filteredThreadSlots[0].slot_id;
    }
  });

  $effect(() => {
    if (!filteredThreadSlots.length) {
      selectedThreadSlotId = "";
    }
  });

  $effect(() => {
    if (
      !selectedDescriptorStreamId &&
      emgDescriptorStreams.length > 0
    ) {
      selectedDescriptorStreamId = emgDescriptorStreams[0].streamId;
    }
  });

  $effect(() => {
    if (
      selectedDescriptorStreamId &&
      !emgDescriptorStreams.some((stream) => stream.streamId === selectedDescriptorStreamId)
    ) {
      selectedDescriptorStreamId = emgDescriptorStreams[0]?.streamId ?? "";
      descriptorPreview = null;
      descriptorSubscribedStreamId = null;
    }
  });

  $effect(() => {
    if (
      !inputFieldsInitialized &&
      emgChannelFieldOptions.length > 0
    ) {
      selectedInputFields = new Set(emgChannelFieldOptions.map((option) => option.path));
      inputFieldsInitialized = true;
    }
  });

  $effect(() => {
    selectedDescriptorStreamId;
    syncDescriptorSubscription();
  });

  function appendJobEvent(jobId: string, status: string, message: string): void {
    const previous = jobEvents[jobEvents.length - 1];
    if (
      previous &&
      previous.jobId === jobId &&
      previous.status === status &&
      previous.message === message
    ) {
      return;
    }
    jobEvents = [
      ...jobEvents,
      {
        jobId,
        status,
        message,
        timestamp: new Date().toLocaleTimeString(),
      },
    ];
  }

  function upsertJob(job: JobStatusMessage): void {
    const index = jobs.findIndex((existing) => existing.job_id === job.job_id);
    if (index === -1) {
      jobs = [...jobs, job];
      return;
    }
    jobs = jobs.map((existing, currentIndex) => (currentIndex === index ? { ...existing, ...job } : existing));
  }

  function slotWorker(slot: ThreadSlotSummary | null | undefined): WorkerSummary | undefined {
    if (!slot?.worker_id) {
      return undefined;
    }
    return workersById.get(slot.worker_id);
  }

  function isSlotOnDrainingWorker(slot: ThreadSlotSummary | null | undefined): boolean {
    return isWorkerDraining(slotWorker(slot));
  }

  function slotIsClaimableByPrincipal(slot: ThreadSlotSummary): boolean {
    if (!normalizedPrincipalId || isSlotOnDrainingWorker(slot)) {
      return false;
    }
    return slot.access_mode === "shared" && hasSharedComputeAccess;
  }

  function slotIsSubmittableByPrincipal(slot: ThreadSlotSummary): boolean {
    if (!normalizedPrincipalId || isSlotOnDrainingWorker(slot)) {
      return false;
    }
    if (slot.access_mode === "dedicated") {
      return slot.dedicated_username === normalizedPrincipalId || isAuthenticatedAdmin;
    }
    return hasSharedComputeAccess;
  }

  function slotMatchesFilter(slot: ThreadSlotSummary): boolean {
    if (slotFilterMode === "mine") {
      return slot.access_mode === "dedicated" && slot.dedicated_username === normalizedPrincipalId;
    }
    if (slotFilterMode === "shared") {
      return slot.access_mode === "shared";
    }
    if (slotFilterMode === "submittable") {
      return slotIsSubmittableByPrincipal(slot);
    }
    if (slotFilterMode === "active") {
      return (slot.assigned_job_count ?? 0) > 0;
    }
    return true;
  }

  function refreshRuns(): void {
    latestError = "";
    wsManager?.send({
      action: "list_recorded_runs",
      request_id: crypto.randomUUID(),
      ...(broker.trim() ? { broker: broker.trim() } : {}),
    });
  }

  function refreshScheduler(): void {
    if (supportsListWorkers) {
      wsManager?.send({
        action: "list_workers",
        request_id: crypto.randomUUID(),
        show_all: showAllSchedulerState && isAuthenticatedAdmin,
      });
    }
    if (supportsListThreadSlots) {
      wsManager?.send({
        action: "list_thread_slots",
        request_id: crypto.randomUUID(),
        show_all: showAllSchedulerState && isAuthenticatedAdmin,
      });
    }
    if (supportsListJobs) {
      wsManager?.send({
        action: "list_jobs",
        request_id: crypto.randomUUID(),
        show_all: showAllSchedulerState && isAuthenticatedAdmin,
      });
    }
  }

  function toggleTrain(run: RecordedRunSummary): void {
    const key = runKey(run);
    trainSelection = toggleSetValue(trainSelection, key);
    if (trainSelection.has(key) && evalSelection.has(key)) {
      const nextEval = new Set(evalSelection);
      nextEval.delete(key);
      evalSelection = nextEval;
    }
  }

  function toggleEval(run: RecordedRunSummary): void {
    const key = runKey(run);
    evalSelection = toggleSetValue(evalSelection, key);
    if (evalSelection.has(key) && trainSelection.has(key)) {
      const nextTrain = new Set(trainSelection);
      nextTrain.delete(key);
      trainSelection = nextTrain;
    }
  }

  function toggleFamily(family: FamilyId): void {
    selectedFamilies = toggleSetValue(selectedFamilies, family);
  }

  function toggleInputField(path: string): void {
    selectedInputFields = toggleSetValue(selectedInputFields, path);
  }

  function selectedRuns(source: Set<string>): Array<{ session_id: string; run_index: number }> {
    return runs
      .filter((run) => source.has(runKey(run)))
      .map((run) => ({
        session_id: run.session_id,
        run_index: run.run_index,
      }));
  }

  function startJob(): void {
    latestError = "";
    latestReport = null;
    const trainRuns = selectedRuns(trainSelection);
    const evalRuns = selectedRuns(evalSelection);
    const families = Array.from(selectedFamilies);
    const selectedFieldPaths = Array.from(selectedInputFields);
    if (!selectedThreadSlotId) {
      latestError = "Select a worker thread slot before starting a job.";
      return;
    }
    if (!selectedThreadSlot || !slotIsSubmittableByPrincipal(selectedThreadSlot)) {
      latestError = "Selected slot is not available to the current user.";
      return;
    }
    if (isWorkerDraining(selectedThreadSlotWorker)) {
      latestError = `Selected slot is attached to draining worker ${selectedThreadSlotWorker?.worker_id}.`;
      return;
    }
    if (!trainRuns.length || !evalRuns.length) {
      latestError = "Select at least one training run and one validation run.";
      return;
    }
    if (!families.length) {
      latestError = "Select at least one model family.";
      return;
    }
    latestInfo = `Submitting train / validate job to ${selectedThreadSlotId}`;
    wsManager?.send({
      action: "start_train_validate_job",
      request_id: crypto.randomUUID(),
      ...(broker.trim() ? { broker: broker.trim() } : {}),
      thread_slot_id: selectedThreadSlotId,
      priority: jobPriority,
      train_runs: trainRuns,
      eval_runs: evalRuns,
      families,
      ...(selectedFieldPaths.length ? { selected_fields: selectedFieldPaths } : {}),
      rest_gesture: restGesture,
      active_gesture: activeGesture,
      window_ms: windowMs,
      hop_ms: hopMs,
      vote_windows: voteWindows,
      confidence_threshold: confidenceThreshold,
      min_hold_windows: minHoldWindows,
      emit_only_during_cue_hold: emitOnlyDuringCueHold,
    });
  }

  function saveSelectedSlotPolicy(): void {
    if (!selectedThreadSlotId || !isAuthenticatedAdmin) {
      return;
    }
    if (isWorkerDraining(selectedThreadSlotWorker)) {
      latestError = `Selected slot is attached to draining worker ${selectedThreadSlotWorker?.worker_id}.`;
      return;
    }
    if (adminSelectedSlotAccessMode === "dedicated" && !adminSelectedSlotDedicatedUsername.trim()) {
      latestError = "Dedicated slots require a username.";
      return;
    }
    wsManager?.send({
      action: "set_slot_compute_policy",
      request_id: crypto.randomUUID(),
      slot_id: selectedThreadSlotId,
      access_mode: adminSelectedSlotAccessMode,
      dedicated_username:
        adminSelectedSlotAccessMode === "dedicated"
          ? adminSelectedSlotDedicatedUsername.trim()
          : undefined,
      show_all: showAllSchedulerState && isAuthenticatedAdmin,
    });
    latestInfo = `Updating compute policy for ${selectedThreadSlotId}`;
  }

  function saveJobPriority(jobId: string): void {
    const draft = priorityDrafts[jobId];
    if (draft === undefined) {
      return;
    }
    wsManager?.send({
      action: "update_job",
      request_id: crypto.randomUUID(),
      job_id: jobId,
      priority: draft,
      principal_id: normalizedPrincipalId,
    });
  }

  function stopJob(jobId: string): void {
    wsManager?.send({
      action: "stop_job",
      request_id: crypto.randomUUID(),
      job_id: jobId,
      principal_id: normalizedPrincipalId,
    });
  }

  function canRecoverJob(job: JobStatusMessage): boolean {
    const worker = job.worker_id ? workersById.get(job.worker_id) : undefined;
    return (
      (job.status === "running" || job.status === "cancelling") &&
      recoverableWorkerStatuses.has(worker?.worker_status ?? "")
    );
  }

  function recoverJob(jobId: string): void {
    wsManager?.send({
      action: "recover_job",
      request_id: crypto.randomUUID(),
      job_id: jobId,
      principal_id: normalizedPrincipalId,
    });
  }

  function canRecoverWorker(worker: WorkerSummary): boolean {
    return recoverableWorkerStatuses.has(worker.worker_status ?? "") && worker.running_job_count > 0;
  }

  function canDrainWorker(worker: WorkerSummary): boolean {
    const status = workerStatus(worker);
    return !drainingWorkerStatuses.has(status) && !recoverableWorkerStatuses.has(status);
  }

  function canResumeWorker(worker: WorkerSummary): boolean {
    return drainingWorkerStatuses.has(workerStatus(worker));
  }

  function recoverWorker(workerId: string): void {
    latestInfo = `Recovering active jobs on ${workerId}`;
    wsManager?.send({
      action: "recover_worker",
      request_id: crypto.randomUUID(),
      worker_id: workerId,
      principal_id: normalizedPrincipalId,
    });
  }

  function updateWorkerStatus(workerId: string, status: "online" | "draining"): void {
    latestInfo =
      status === "draining" ? `Draining worker ${workerId}` : `Resuming worker ${workerId}`;
    wsManager?.send({
      action: "update_worker_status",
      request_id: crypto.randomUUID(),
      worker_id: workerId,
      status,
      principal_id: normalizedPrincipalId,
    });
  }

  function syncDescriptorSubscription(): void {
    if (!descriptorWsManager || descriptorWsManager.getConnectionState() !== "connected") {
      return;
    }
    if (descriptorSubscribedStreamId && descriptorSubscribedStreamId !== selectedDescriptorStreamId) {
      descriptorWsManager.unsubscribe([descriptorSubscribedStreamId]);
      descriptorSubscribedStreamId = null;
    }
    if (selectedDescriptorStreamId && descriptorSubscribedStreamId !== selectedDescriptorStreamId) {
      descriptorWsManager.subscribe([selectedDescriptorStreamId]);
      descriptorSubscribedStreamId = selectedDescriptorStreamId;
      descriptorPreview = null;
    }
  }

  function connect(): void {
    wsManager?.disconnect();
    wsManager = new MlControlPlaneWebSocket(controlPlaneUrl, {
      onConnectionChange: (state) => {
        connectionState = state;
        if (state === "connected") {
          latestInfo = "Connected to NatKit ML control plane";
          refreshRuns();
          refreshScheduler();
        }
      },
      onHello: (message) => {
        if (message.service !== "natkit-ml-control-plane") {
          latestError =
            `Connected to incompatible service "${message.service}" at ${controlPlaneUrl}. ` +
            "The ML Pipeline worker-slot UI requires libnatkit/scripts/natkit_ml_control_plane.py.";
          latestInfo = "";
          return;
        }
        authenticatedUser = message.authenticated_user ?? null;
        workerId = message.worker_id;
        defaultPrincipalId = message.default_principal_id;
        principalId =
          message.authenticated_user?.username ?? message.default_principal_id;
        showAllSchedulerState =
          !!message.authenticated_user?.is_admin && showAllSchedulerState;
        if (!broker.trim()) {
          broker = message.broker;
        }
        if (message.authenticated_user === null) {
          latestError =
            "The control plane did not receive a shared auth session. Sign in through the main site before using the ML Pipeline.";
        }
        latestInfo = `Connected to ${message.service} on ${message.worker_id}`;
      },
      onRecordedRuns: (message) => {
        runs = message.runs;
        latestInfo = `Loaded ${message.runs.length} recorded runs`;
      },
      onWorkers: (message) => {
        supportsListWorkers = true;
        workers = message.workers;
        if (!workerId) {
          const embeddedWorker =
            message.workers.find((worker) => worker.worker_source === "embedded") ??
            message.workers[0];
          workerId = embeddedWorker?.worker_id ?? "";
        }
      },
      onThreadSlots: (message) => {
        supportsListThreadSlots = true;
        threadSlots = message.slots;
      },
      onJobList: (message) => {
        supportsListJobs = true;
        jobs = message.jobs;
      },
      onJobAccepted: (message) => {
        activeJobId = message.job_id;
        activeJobStatus = {
          type: "job_status",
          job_id: message.job_id,
          thread_slot_id: message.thread_slot_id,
          priority: message.priority,
          status: "queued",
          message: message.message,
        };
        latestInfo = `Job ${message.job_id} accepted on ${message.thread_slot_id}`;
        appendJobEvent(message.job_id, message.status, message.message);
        refreshScheduler();
      },
      onJobStatus: (message) => {
        activeJobId = message.job_id;
        activeJobStatus = message;
        upsertJob(message);
        appendJobEvent(message.job_id, message.status, message.message);
        latestInfo = message.message;
        if (message.status === "completed") {
          latestReport = (message.report ?? null) as Record<string, unknown> | null;
        }
        if (message.status === "failed") {
          latestError = message.error ?? message.message;
        }
      },
      onError: (message) => {
        if (message.message === "unknown action: list_workers") {
          supportsListWorkers = false;
          latestInfo = "Connected to a control plane build without explicit worker-list refresh support";
          return;
        }
        if (message.message === "unknown action: list_thread_slots") {
          supportsListThreadSlots = false;
          latestInfo = "Connected to a control plane build without explicit slot-list refresh support";
          return;
        }
        if (message.message === "unknown action: list_jobs") {
          supportsListJobs = false;
          latestInfo = "Connected to a control plane build without explicit job-list refresh support";
          return;
        }
        latestError = message.message;
      },
    });
    wsManager.connect();
  }

  onMount(() => {
    descriptorWsManager = new StreamViewerWebSocket(defaultStreamViewerUrl(), {
      onConnectionChange: (state) => {
        if (state === "connected") {
          descriptorWsManager?.requestStreamList();
          syncDescriptorSubscription();
        }
      },
      onStreamList: (message: StreamListMessage) => {
        descriptorStreams = message.streams;
        syncDescriptorSubscription();
      },
      onEmgData: (message: EmgDataMessage) => {
        if (String(message.stream_id) === selectedDescriptorStreamId) {
          descriptorPreview = message;
        }
      },
      onError: (message: StreamViewerErrorMessage) => {
        latestError = message.message;
      },
    });
    descriptorWsManager.connect();
    connect();
    return () => {
      wsManager?.disconnect();
      descriptorWsManager?.disconnect();
    };
  });
</script>

<div class="pipeline-page">
  <header class="page-header">
    <div>
      <p class="eyebrow">ML Workspace</p>
      <h1>Worker Slot Train / Validate</h1>
      <p class="subtitle">
        Discover recorded runs on Kafka, target a worker thread slot, queue jobs
        with priority, and inspect active and queued work on each slot.
      </p>
    </div>
    <div class="header-meta">
      <div class="connection-chip" data-state={connectionState}>{connectionState}</div>
      <div class="worker-chip">{workerId || "worker pending"}</div>
    </div>
  </header>

  <section class="control-band">
    <div class="field">
      <label for="control-plane-url">Control Plane URL</label>
      <input id="control-plane-url" bind:value={controlPlaneUrl} />
    </div>
    <div class="field">
      <label for="broker">Kafka Broker</label>
      <input id="broker" bind:value={broker} />
    </div>
    <div class="field">
      <label for="principal-display">Principal</label>
      <div id="principal-display" class="readonly-field">
        {authenticatedUser?.display_name || normalizedPrincipalId || "Unauthenticated"}
      </div>
    </div>
    {#if isAuthenticatedAdmin}
      <label class="checkbox-row scope-toggle">
        <input
          type="checkbox"
          bind:checked={showAllSchedulerState}
          onchange={() => refreshScheduler()}
        />
        Show all scheduler state
      </label>
    {/if}
    <div class="field">
      <label for="job-priority">Job Priority</label>
      <input id="job-priority" type="number" bind:value={jobPriority} step="1" />
    </div>
    <div class="button-row">
      <button onclick={connect}>Reconnect</button>
      <button onclick={refreshRuns} disabled={connectionState !== "connected"}>Refresh Runs</button>
      <button onclick={refreshScheduler} disabled={connectionState !== "connected"}>Refresh Scheduler</button>
      <button
        class="primary"
        onclick={startJob}
        disabled={connectionState !== "connected" || isWorkerDraining(selectedThreadSlotWorker)}
      >
        Queue Train / Validate
      </button>
    </div>
    {#if isAuthenticatedAdmin && selectedThreadSlot}
      <div class="admin-slot-policy">
        <strong>Selected Slot Policy</strong>
        <label>
          <span>Mode</span>
          <select bind:value={adminSelectedSlotAccessMode}>
            <option value="shared">Shared pool</option>
            <option value="dedicated">Dedicated</option>
          </select>
        </label>
        {#if adminSelectedSlotAccessMode === "dedicated"}
          <label>
            <span>Dedicated user</span>
            <input bind:value={adminSelectedSlotDedicatedUsername} placeholder="username" />
          </label>
        {/if}
        <button
          onclick={saveSelectedSlotPolicy}
          disabled={connectionState !== "connected" || (selectedThreadSlot.assigned_job_count ?? 0) > 0}
        >
          Save Slot Policy
        </button>
      </div>
    {/if}
  </section>

  {#if latestError}
    <section class="banner error">{latestError}</section>
  {/if}
  {#if latestInfo}
    <section class="banner info">{latestInfo}</section>
  {/if}

  <section class="scope-summary">
    <div class="section-header">
      <h2>Scheduler Scope</h2>
      <p>{showAllSchedulerState && isAuthenticatedAdmin ? "All principals" : normalizedPrincipalId || "Unscoped view"}</p>
    </div>
    <div class="summary-grid">
      <div class="summary-card">
        <span>Visible Slots</span>
        <strong>{visibleThreadSlots.length}</strong>
      </div>
      <div class="summary-card">
        <span>Dedicated To You</span>
        <strong>{claimedVisibleSlotCount}</strong>
      </div>
      <div class="summary-card">
        <span>Shared Slots</span>
        <strong>{unassignedVisibleSlotCount}</strong>
      </div>
      <div class="summary-card">
        <span>Shared Visible</span>
        <strong>{claimableVisibleSlotCount}</strong>
      </div>
      <div class="summary-card">
        <span>Submittable Slots</span>
        <strong>{submittableVisibleSlotCount}</strong>
      </div>
      <div class="summary-card">
        <span>Queued Jobs</span>
        <strong>{scopedQueuedJobCount}</strong>
      </div>
      <div class="summary-card">
        <span>Running Jobs</span>
        <strong>{scopedRunningJobCount}</strong>
      </div>
      <div class="summary-card">
        <span>Restart Attempts</span>
        <strong>{scopedRestartAttemptCount}</strong>
      </div>
      <div class="summary-card">
        <span>Recoverable Jobs</span>
        <strong>{scopedRecoverableJobCount}</strong>
      </div>
      <div class="summary-card">
        <span>Recoverable Workers</span>
        <strong>{visibleRecoverableWorkerCount}</strong>
      </div>
      <div class="summary-card">
        <span>Draining Workers</span>
        <strong>{visibleDrainingWorkerCount}</strong>
      </div>
      <div class="summary-card">
        <span>Slots On Draining Workers</span>
        <strong>{visibleDrainingSlotCount}</strong>
      </div>
    </div>
  </section>

  <section class="worker-section">
    <div class="section-header">
      <h2>Workers and Thread Slots</h2>
      <p>{workers.length} workers · {filteredThreadSlots.length} / {visibleThreadSlots.length} visible slots</p>
    </div>
    <div class="slot-filter-bar" role="group" aria-label="Thread slot filters">
      <button
        class:active-filter={slotFilterMode === "all"}
        class="filter-chip"
        onclick={() => (slotFilterMode = "all")}
      >
        All
      </button>
      <button
        class:active-filter={slotFilterMode === "mine"}
        class="filter-chip"
        onclick={() => (slotFilterMode = "mine")}
      >
        Mine
      </button>
      <button
        class:active-filter={slotFilterMode === "shared"}
        class="filter-chip"
        onclick={() => (slotFilterMode = "shared")}
      >
        Shared
      </button>
      <button
        class:active-filter={slotFilterMode === "submittable"}
        class="filter-chip"
        onclick={() => (slotFilterMode = "submittable")}
      >
        Submittable
      </button>
      <button
        class:active-filter={slotFilterMode === "active"}
        class="filter-chip"
        onclick={() => (slotFilterMode = "active")}
      >
        Active
      </button>
    </div>
    <div class="worker-grid">
      {#each workers as worker}
        <div class="worker-card">
          <div class="worker-card-head">
            <div>
              <h3>{worker.worker_id}</h3>
              <p>
                {worker.worker_source || "worker"} ·
                <span class="worker-status-pill" data-status={workerStatus(worker)}>
                  {workerStatus(worker)}
                </span>
                ·
                Heartbeat {formatHeartbeat(worker.last_heartbeat_us)}
              </p>
            </div>
            <span class="slot-busy">{formatPercent(worker.busy_ratio_60s)}</span>
          </div>
          <div class="worker-stats">
            <div><span>Slots</span><strong>{worker.visible_slot_count} / {worker.slot_count}</strong></div>
            <div><span>Assigned</span><strong>{worker.assigned_slot_count}</strong></div>
            <div><span>Queued</span><strong>{worker.queued_job_count}</strong></div>
            <div><span>Running</span><strong>{worker.running_job_count}</strong></div>
            <div><span>Active Jobs</span><strong>{worker.assigned_job_count}</strong></div>
            <div><span>Drain</span><strong>{workerDrainLabel(worker)}</strong></div>
            <div><span>Restarts</span><strong>{worker.restart_attempt_count ?? 0}</strong></div>
            <div><span>Recovered</span><strong>{worker.recovered_job_count ?? 0}</strong></div>
            <div><span>Inventory</span><strong>{worker.slot_inventory_ready ? "ready" : "pending"}</strong></div>
          </div>
          <div class="worker-actions">
            <button
              onclick={() => updateWorkerStatus(worker.worker_id, "draining")}
              disabled={connectionState !== "connected" || !canDrainWorker(worker)}
            >
              Drain Worker
            </button>
            <button
              onclick={() => updateWorkerStatus(worker.worker_id, "online")}
              disabled={connectionState !== "connected" || !canResumeWorker(worker)}
            >
              Resume Worker
            </button>
            <button onclick={() => recoverWorker(worker.worker_id)} disabled={!canRecoverWorker(worker)}>
              Recover Worker Jobs
            </button>
          </div>
        </div>
      {/each}
    </div>
    <div class="slot-grid">
      {#if filteredThreadSlots.length}
        {#each filteredThreadSlots as slot}
          <button
            class:selected={slot.slot_id === selectedThreadSlotId}
            class:slot-card-draining={isSlotOnDrainingWorker(slot)}
            class="slot-card"
            onclick={() => (selectedThreadSlotId = slot.slot_id)}
          >
            <div class="slot-head">
              <div>
                <h3>Slot {slot.slot_index + 1}</h3>
                <p>{slot.slot_id}</p>
              </div>
              <span class="slot-busy">{formatPercent(slot.busy_ratio_60s)}</span>
            </div>
            <div class="slot-stats">
              <div><span>Assigned</span><strong>{slot.assigned_job_count}</strong></div>
              <div><span>Queued</span><strong>{slot.queue_depth}</strong></div>
              <div><span>Running</span><strong>{slot.running_job_count}</strong></div>
              <div><span>Restarts</span><strong>{slot.restart_attempt_count ?? 0}</strong></div>
            </div>
            <div class="slot-foot">
              <span>
                Pool: {slot.access_mode === "dedicated" ? `dedicated:${slot.dedicated_username || "unset"}` : "shared"}
              </span>
              <span>Current: {slot.current_job_id || "idle"}</span>
              <span>Worker: {workerStatus(slotWorker(slot))}</span>
            </div>
          </button>
        {/each}
      {:else}
        <div class="empty-state">No slots match the current filter.</div>
      {/if}
    </div>
  </section>

  <section class="settings-band">
    <div class="settings-group">
      <h2>Input Fields</h2>
      <p class="helper-text">
        These descriptor-backed EMG channel selections determine which sample arrays the train / validate pipeline will featurize.
      </p>
      {#if emgDescriptorStreams.length > 0}
        <label>
          Descriptor source
          <select bind:value={selectedDescriptorStreamId}>
            {#each emgDescriptorStreams as stream}
              <option value={stream.streamId}>{stream.streamId}</option>
            {/each}
          </select>
        </label>
        {#if emgChannelFieldOptions.length > 0}
          <div class="field-option-list">
            {#each emgChannelFieldOptions as option}
              <label class="detailed-option">
                <span class="option-head">
                  <input
                    type="checkbox"
                    checked={selectedInputFields.has(option.path)}
                    onchange={() => toggleInputField(option.path)}
                  />
                  <span>{option.label}</span>
                </span>
                <span class="option-detail">{option.path} · {option.description}</span>
              </label>
            {/each}
          </div>
        {:else}
          <p class="helper-text">
            Waiting for a live EMG frame on the selected stream so concrete channel fields can be resolved.
          </p>
        {/if}
      {:else}
        <p class="helper-text">
          No live EMG descriptor source is available. Jobs will use all EMG channels until a descriptor-backed stream is visible.
        </p>
      {/if}
    </div>
    <div class="settings-group">
      <h2>Families</h2>
      <p class="helper-text">
        These are the model families the pipeline will train and compare before it chooses the best validation result.
      </p>
      {#each Object.entries(familyDescriptions) as [family, details]}
        <label class="detailed-option">
          <span class="option-head">
            <input
              type="checkbox"
              checked={selectedFamilies.has(family as FamilyId)}
              onchange={() => toggleFamily(family as FamilyId)}
            />
            <span>{details.label}</span>
          </span>
          <span class="option-detail">{details.detail}</span>
        </label>
      {/each}
    </div>
    <div class="settings-group">
      <h2>Windowing</h2>
      <label>Window ms <input type="number" bind:value={windowMs} min="50" step="10" /></label>
      <label>Hop ms <input type="number" bind:value={hopMs} min="10" step="10" /></label>
      <label>Vote windows <input type="number" bind:value={voteWindows} min="1" step="1" /></label>
    </div>
    <div class="settings-group">
      <h2>Calibration and Emission</h2>
      <label>Rest gesture <input bind:value={restGesture} /></label>
      <label>Active gesture <input bind:value={activeGesture} /></label>
      <label>Confidence <input type="number" bind:value={confidenceThreshold} min="0" max="1" step="0.05" /></label>
      <label>Min hold windows <input type="number" bind:value={minHoldWindows} min="1" step="1" /></label>
      <label class="checkbox-row">
        <input type="checkbox" bind:checked={emitOnlyDuringCueHold} />
        Emit only during cue hold
      </label>
    </div>
  </section>

  <section class="runs-section">
    <div class="section-header">
      <h2>Recorded Runs</h2>
      <p>{runs.length} runs discovered</p>
    </div>
    <table>
      <thead>
        <tr>
          <th>Train</th>
          <th>Eval</th>
          <th>Session</th>
          <th>Run</th>
          <th>Window</th>
          <th>Devices</th>
          <th>Participant</th>
          <th>Protocol</th>
          <th>Tags</th>
          <th>Markers</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>
        {#each runs as run}
          <tr>
            <td>
              <input
                type="checkbox"
                checked={trainSelection.has(runKey(run))}
                onchange={() => toggleTrain(run)}
              />
            </td>
            <td>
              <input
                type="checkbox"
                checked={evalSelection.has(runKey(run))}
                onchange={() => toggleEval(run)}
              />
            </td>
            <td>{run.session_id}</td>
            <td>{run.run_index}</td>
            <td>{formatWindow(run.start_us, run.end_us)}</td>
            <td>{run.device_ids.join(", ") || "unknown"}</td>
            <td>{run.participant_id || "-"}</td>
            <td>{run.protocol_id || "-"}</td>
            <td>{run.tags.join(", ") || "-"}</td>
            <td>{run.marker_count}</td>
            <td class="notes-cell">{run.notes || "-"}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>

  <section class="jobs-section">
    <div class="section-header">
      <h2>Slot Jobs</h2>
      <p>{selectedThreadSlot ? selectedThreadSlot.slot_id : "No slot selected"}</p>
    </div>
    <table>
      <thead>
        <tr>
          <th>Job</th>
          <th>Status</th>
          <th>Restarts</th>
          <th>Priority</th>
          <th>Created</th>
          <th>Started</th>
          <th>Finished</th>
          <th>Message</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {#each visibleJobs as job}
          <tr>
            <td>{job.job_id}</td>
            <td><span class="status-pill" data-status={job.status}>{job.status}</span></td>
            <td>{job.restart_count ?? 0}</td>
            <td class="priority-cell">
              <input
                type="number"
                value={priorityDrafts[job.job_id] ?? job.priority ?? 0}
                oninput={(event) => {
                  const target = event.currentTarget as HTMLInputElement;
                  priorityDrafts = { ...priorityDrafts, [job.job_id]: Number(target.value) };
                }}
                disabled={job.status !== "queued"}
              />
            </td>
            <td>{formatTimestamp(job.created_at_us)}</td>
            <td>{formatTimestamp(job.started_at_us ?? undefined)}</td>
            <td>{formatTimestamp(job.finished_at_us ?? undefined)}</td>
            <td class="notes-cell">{job.message}</td>
            <td class="action-cell">
              <button onclick={() => saveJobPriority(job.job_id)} disabled={job.status !== "queued"}>
                Save
              </button>
              <button onclick={() => stopJob(job.job_id)} disabled={job.status === "completed" || job.status === "failed" || job.status === "cancelled"}>
                Stop
              </button>
              <button onclick={() => recoverJob(job.job_id)} disabled={!canRecoverJob(job)}>
                Recover
              </button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>

  <section class="job-section">
    <div class="section-header">
      <h2>Latest Job Status</h2>
      <p>{activeJobId ? `Job ${activeJobId}` : "No recent job"}</p>
    </div>
    <div class="job-summary">
      <div class="status-pill" data-status={activeJobStatus?.status ?? "idle"}>
        {activeJobStatus?.status ?? "idle"}
      </div>
      <div class="job-activity">
        <h3>Current activity</h3>
        <p>{activeJobStatus?.message || "Queue a job to see live pipeline activity."}</p>
      </div>
    </div>
    {#if activeJobStatus}
      <div class="job-status">
        <div><strong>Slot:</strong> {activeJobStatus.thread_slot_id || "-"}</div>
        <div><strong>Priority:</strong> {activeJobStatus.priority ?? 0}</div>
        <div><strong>Restarts:</strong> {activeJobStatus.restart_count ?? 0}</div>
        <div><strong>Owner:</strong> {activeJobStatus.owner_principal_id || "-"}</div>
      </div>
    {/if}
    {#if jobEvents.length}
      <div class="job-history">
        <h3>Activity log</h3>
        <div class="history-list">
          {#each jobEvents as event}
            <div class="history-row">
              <span class="history-time">{event.timestamp}</span>
              <span class="history-job">{event.jobId}</span>
              <span class="history-status" data-status={event.status}>{event.status}</span>
              <span class="history-message">{event.message}</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}
    {#if latestReport}
      <div class="report-grid">
        <div class="report-stat">
          <span class="label">Selected Family</span>
          <strong>{String(latestReport.selected_family ?? "-")}</strong>
        </div>
        <div class="report-stat">
          <span class="label">Mean Accuracy</span>
          <strong>{String(latestReport.selected_mean_accuracy ?? "-")}</strong>
        </div>
        <div class="report-stat">
          <span class="label">Mean Coverage</span>
          <strong>{String(latestReport.selected_mean_coverage ?? "-")}</strong>
        </div>
        <div class="report-stat report-stat-wide">
          <span class="label">Selected Fields</span>
          <strong>{Array.isArray(latestReport.selected_fields) && latestReport.selected_fields.length
            ? latestReport.selected_fields.join(", ")
            : "all channels"}</strong>
        </div>
      </div>
      <pre>{JSON.stringify(latestReport, null, 2)}</pre>
    {/if}
  </section>
</div>

<style>
  .pipeline-page {
    padding: 24px;
    color: #16211c;
  }

  .page-header,
  .control-band,
  .scope-summary,
  .worker-section,
  .settings-band,
  .runs-section,
  .jobs-section,
  .job-section,
  .banner {
    background: #fff;
    border: 1px solid #d9e1dc;
    border-radius: 8px;
    margin-bottom: 16px;
  }

  .page-header {
    padding: 22px 24px;
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-start;
  }

  .eyebrow {
    margin: 0;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #0b7a53;
  }

  h1 {
    margin: 6px 0 0;
    font-size: 32px;
    line-height: 1.1;
  }

  .subtitle {
    margin: 10px 0 0;
    max-width: 760px;
    color: #57655f;
  }

  .header-meta {
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: flex-end;
  }

  .connection-chip,
  .worker-chip {
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 12px;
    text-transform: uppercase;
    background: #eef2ef;
    color: #57655f;
  }

  .connection-chip[data-state="connected"] {
    background: #e1f2ea;
    color: #0b7a53;
  }

  .connection-chip[data-state="connecting"] {
    background: #f7ecd9;
    color: #9b5c12;
  }

  .control-band,
  .settings-band {
    padding: 18px 20px;
    display: grid;
    gap: 14px;
  }

  .control-band {
    grid-template-columns: repeat(5, minmax(0, 1fr));
    align-items: end;
  }

  .settings-band {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .field,
  .settings-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .settings-group {
    padding: 14px;
    border: 1px solid #d9e1dc;
    border-radius: 8px;
  }

  .settings-group h2,
  .worker-section h2,
  .runs-section h2,
  .jobs-section h2,
  .job-section h2 {
    margin: 0;
    font-size: 18px;
  }

  .helper-text {
    margin: 0;
    color: #57655f;
    font-size: 13px;
  }

  .field-option-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 14px;
  }

  input,
  select {
    border: 1px solid #c6d2cb;
    border-radius: 6px;
    padding: 8px 10px;
    font: inherit;
  }

  .readonly-field {
    min-height: 42px;
    display: flex;
    align-items: center;
    border: 1px solid #c6d2cb;
    border-radius: 6px;
    padding: 8px 10px;
    background: #f6f8f7;
    color: #22332b;
  }

  .checkbox-row {
    flex-direction: row;
    align-items: center;
  }

  .scope-toggle {
    align-self: end;
    gap: 10px;
    min-height: 42px;
  }

  .button-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    grid-column: 1 / -1;
  }

  button {
    border: 1px solid #c6d2cb;
    border-radius: 6px;
    background: #fff;
    color: #16211c;
    padding: 8px 12px;
    font: inherit;
    cursor: pointer;
  }

  button.primary {
    background: #0b7a53;
    border-color: #0b7a53;
    color: #fff;
  }

  button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .banner {
    padding: 12px 16px;
  }

  .banner.error {
    border-color: #efc6bd;
    background: #f9e7e2;
    color: #7f2619;
  }

  .banner.info {
    border-color: #cce1d6;
    background: #edf7f1;
    color: #14543b;
  }

  .worker-section,
  .scope-summary,
  .runs-section,
  .jobs-section,
  .job-section {
    padding: 18px 20px;
  }

  .summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 10px;
  }

  .slot-filter-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 14px;
  }

  .filter-chip.active-filter {
    background: #0b7a53;
    border-color: #0b7a53;
    color: #fff;
  }

  .summary-card {
    border: 1px solid #d9e1dc;
    border-radius: 6px;
    padding: 12px;
    background: #fcfdfc;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: baseline;
    margin-bottom: 14px;
  }

  .section-header p {
    margin: 0;
    color: #57655f;
    font-size: 13px;
  }

  .slot-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 12px;
  }

  .empty-state {
    border: 1px dashed #c6d2cb;
    border-radius: 8px;
    padding: 24px;
    color: #57655f;
    background: #fcfdfc;
  }

  .worker-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 12px;
    margin-bottom: 12px;
  }

  .worker-card {
    border: 1px solid #d9e1dc;
    border-radius: 8px;
    padding: 14px;
    background: #fcfdfc;
  }

  .worker-card-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }

  .worker-card h3 {
    margin: 0;
    font-size: 16px;
  }

  .worker-card p {
    margin: 4px 0 0;
    color: #57655f;
    font-size: 12px;
  }

  .worker-status-pill {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 999px;
    background: #eef2ef;
    color: #57655f;
    font-size: 11px;
    text-transform: uppercase;
  }

  .worker-status-pill[data-status="online"] {
    background: #e1f2ea;
    color: #0b7a53;
  }

  .worker-status-pill[data-status="starting"],
  .worker-status-pill[data-status="draining"] {
    background: #f7ecd9;
    color: #9b5c12;
  }

  .worker-status-pill[data-status="stalled"],
  .worker-status-pill[data-status="offline"],
  .worker-status-pill[data-status="missing"] {
    background: #f9e7e2;
    color: #7f2619;
  }

  .worker-status-pill[data-status="degraded"] {
    background: #ece8fb;
    color: #5b41a8;
  }

  .worker-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
    gap: 8px;
    margin-top: 12px;
  }

  .worker-stats div {
    border: 1px solid #d9e1dc;
    border-radius: 6px;
    padding: 8px;
    background: #fff;
  }

  .worker-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 12px;
  }

  .slot-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
    text-align: left;
  }

  .slot-card.selected {
    border-color: #0b7a53;
    box-shadow: inset 0 0 0 1px #0b7a53;
    background: #f3fbf7;
  }

  .slot-card.slot-card-draining {
    border-color: #e1c38f;
    background: #fffcf5;
  }

  .slot-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }

  .slot-head h3 {
    margin: 0;
    font-size: 16px;
  }

  .slot-head p,
  .slot-foot {
    margin: 4px 0 0;
    color: #57655f;
    font-size: 12px;
  }

  .slot-busy {
    padding: 4px 8px;
    border-radius: 999px;
    background: #edf7f1;
    color: #0b7a53;
    font-size: 12px;
    font-weight: 600;
  }

  .slot-stats {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
  }

  .slot-stats div {
    border: 1px solid #d9e1dc;
    border-radius: 6px;
    padding: 8px;
    background: #fcfdfc;
  }

  .slot-stats span,
  .worker-stats span,
  .summary-card span,
  .report-stat .label {
    display: block;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #57655f;
  }

  .slot-stats strong,
  .worker-stats strong,
  .summary-card strong,
  .report-stat strong {
    display: block;
    margin-top: 4px;
    font-size: 18px;
  }

  .slot-foot {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }

  th,
  td {
    padding: 10px 8px;
    border-bottom: 1px solid #e6ece8;
    text-align: left;
    vertical-align: top;
  }

  th {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #57655f;
  }

  .notes-cell {
    max-width: 340px;
    color: #41514a;
  }

  .priority-cell input {
    width: 80px;
  }

  .action-cell {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .status-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 94px;
    padding: 6px 10px;
    border-radius: 999px;
    background: #eef2ef;
    color: #57655f;
    font-size: 12px;
    text-transform: uppercase;
  }

  .status-pill[data-status="queued"] {
    background: #eaf1ff;
    color: #2453a4;
  }

  .status-pill[data-status="running"],
  .status-pill[data-status="cancelling"] {
    background: #f7ecd9;
    color: #9b5c12;
  }

  .status-pill[data-status="completed"] {
    background: #e1f2ea;
    color: #0b7a53;
  }

  .status-pill[data-status="failed"],
  .status-pill[data-status="cancelled"] {
    background: #f9e7e2;
    color: #8b2d20;
  }

  .job-summary {
    display: flex;
    gap: 16px;
    align-items: center;
  }

  .job-activity h3,
  .job-history h3 {
    margin: 0 0 6px;
    font-size: 15px;
  }

  .job-activity p {
    margin: 0;
    color: #41514a;
  }

  .job-status {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin-top: 16px;
  }

  .job-history {
    margin-top: 16px;
  }

  .history-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .history-row {
    display: grid;
    grid-template-columns: 90px 1.5fr 110px 3fr;
    gap: 10px;
    align-items: start;
    padding: 8px 10px;
    border: 1px solid #e6ece8;
    border-radius: 6px;
    background: #fcfdfc;
    font-size: 13px;
  }

  .history-time,
  .history-job {
    color: #57655f;
  }

  .history-status {
    font-size: 12px;
    text-transform: uppercase;
  }

  .report-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin-top: 16px;
  }

  .report-stat {
    border: 1px solid #d9e1dc;
    border-radius: 6px;
    padding: 12px;
    background: #fcfdfc;
  }

  .report-stat-wide {
    grid-column: 1 / -1;
  }

  pre {
    margin: 14px 0 0;
    padding: 14px;
    border-radius: 8px;
    background: #132019;
    color: #d7eee2;
    font-size: 12px;
    overflow: auto;
  }

  @media (max-width: 1100px) {
    .control-band,
    .settings-band {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 760px) {
    .pipeline-page {
      padding: 16px;
    }

    .page-header,
    .section-header,
    .job-summary {
      flex-direction: column;
      align-items: stretch;
    }

    .control-band,
    .settings-band,
    .job-status,
    .report-grid {
      grid-template-columns: 1fr;
    }

    .history-row {
      grid-template-columns: 1fr;
    }
  }
</style>
