(ns natkit.events
  "The re-frame event surface. Handlers stay thin: they move data into app-db and
  emit effects. Anything with logic in it belongs in a pure namespace
  (natkit.graph.*, natkit.stream.*, natkit.experiment.*) so it can be tested
  without a running app."
  (:require [re-frame.core :as rf]
            [natkit.db :as db]
            [natkit.protocol.actions :as actions]
            [natkit.protocol.socket :as socket]
            [natkit.protocol.wire :as wire]))

;; --- Boot -------------------------------------------------------------------

(rf/reg-event-fx :app/boot
  (fn [_ _]
    {:db db/default-db
     ::socket/connect nil}))

;; --- Toasts -----------------------------------------------------------------
;; The bottom-right stack replaces the Svelte page's single floating error banner.

(defonce ^:private toast-counter (atom 0))

(rf/reg-event-db :toast/push
  (fn [db [_ level text]]
    (update db :toasts conj {:id (swap! toast-counter inc)
                             :level level
                             :text text})))

(rf/reg-event-db :toast/dismiss
  (fn [db [_ id]]
    (update db :toasts (fn [toasts] (vec (remove #(= id (:id %)) toasts))))))

;; --- Connection lifecycle ---------------------------------------------------

(rf/reg-event-db :protocol/connection-state
  (fn [db [_ state]]
    (assoc db :connection-state state)))

(rf/reg-event-fx :protocol/connected
  (fn [{:keys [db]} _]
    ;; Everything the page needs on connect. The catalog first — the palette and
    ;; every inspector render from it.
    {:db (assoc db :reconnect {:attempt 0 :delay_ms nil :abandoned? false})
     ::socket/send [(actions/get-streams)
                    (actions/list-node-catalog)
                    (actions/list-stream-graphs)
                    (actions/list-profiles)
                    ;; Compute slots, so a train submit can auto-pick one.
                    (actions/ml-proxy (actions/list-thread-slots))]}))

(rf/reg-event-db :protocol/reconnect-scheduled
  (fn [db [_ info]]
    (assoc db :reconnect (merge info {:abandoned? false}))))

(rf/reg-event-fx :protocol/reconnect-abandoned
  (fn [{:keys [db]} [_ attempts]]
    {:db (assoc db :reconnect {:attempt attempts :delay_ms nil :abandoned? true})
     :fx [[:dispatch [:toast/push :error
                      (str "Lost the backend connection after " attempts
                           " attempts. Reload to retry.")]]]}))

(rf/reg-event-db :protocol/socket-error
  (fn [db _]
    ;; A socket error is always followed by a close, which drives the reconnect.
    ;; Nothing to record beyond what the state pill already shows.
    db))

(rf/reg-event-fx :protocol/send-while-disconnected
  (fn [_ [_ action]]
    {:fx [[:dispatch [:toast/push :warn
                      (str "Not connected — '" (wire/action-name action)
                           "' was not sent.")]]]}))

(rf/reg-event-fx :protocol/malformed-frame
  (fn [_ [_ _raw]]
    {:fx [[:dispatch [:toast/push :error "Received a malformed frame from the backend."]]]}))

(rf/reg-event-fx :protocol/unknown-message
  (fn [_ [_ message]]
    ;; Surfaced rather than dropped: an unknown type means the backend protocol
    ;; grew and this frontend has not caught up.
    (js/console.warn "Unhandled message type:" (wire/message-type message))
    {}))

(rf/reg-event-db :protocol/status-received
  (fn [db [_ message]]
    (assoc db :subscribed-streams (:subscribed_streams message))))

(rf/reg-event-fx :protocol/error-received
  (fn [_ [_ message]]
    {:fx [[:dispatch [:toast/push :error (wire/error-message message)]]]}))

(rf/reg-event-db :protocol/provenance-received
  (fn [db _] db))

;; --- Discovery --------------------------------------------------------------

(rf/reg-event-db :streams/list-received
  (fn [db [_ message]]
    ;; Keyed by stream id — normalize so lookups by raw id always hit.
    (assoc db :streams (wire/id-keyed (:streams message)))))

(rf/reg-event-db :catalog/received
  (fn [db [_ message]]
    (assoc db :node-catalog (:nodes message))))

(rf/reg-event-db :catalog/transform-capabilities-received
  (fn [db _]
    ;; Legacy action, kept for backward compat on the backend. Capabilities are
    ;; DERIVED from the node catalog here (db/transform-capabilities), so there is
    ;; nothing to store.
    db))

;; --- Graphs -----------------------------------------------------------------

(defn- normalize-status
  "A status' node_statuses is keyed by NODE ID, which routinely contains a slash
  (source/…, composite/…). Normalize both levels."
  [status]
  (update status :node_statuses wire/id-keyed))

(defn- normalize-statuses [statuses]
  (reduce-kv (fn [acc graph-id status]
               (assoc acc (wire/key-name graph-id) (normalize-status status)))
             {}
             (or statuses {})))

(rf/reg-event-db :graphs/list-received
  (fn [db [_ message]]
    (assoc db
           :graphs (vec (:graphs message))
           :graph-statuses (normalize-statuses (:statuses message)))))

(rf/reg-event-db :graphs/saved
  (fn [db [_ message]]
    (let [saved (:graph message)
          others (filterv #(not= (:graph_id message) (:graph_id %)) (:graphs db))]
      (assoc db :graphs (vec (sort-by :label (conj others saved)))))))

(rf/reg-event-db :graphs/validation-received
  (fn [db [_ message]]
    ;; node/edge diagnostics are keyed by node/edge id.
    (assoc db :diagnostics {:graph (or (:graph_diagnostics message) [])
                            :nodes (or (wire/id-keyed (:node_diagnostics message)) {})
                            :edges (or (wire/id-keyed (:edge_diagnostics message)) {})})))

(rf/reg-event-db :graphs/status-received
  (fn [db [_ message]]
    (assoc-in db [:graph-statuses (:graph_id message)]
              (normalize-status (:status message)))))

(rf/reg-event-fx :graphs/started
  (fn [{:keys [db]} [_ message]]
    {:db (assoc-in db [:graph-statuses (:graph_id message)]
                   {:graph_id (:graph_id message)
                    :run_state "running"
                    :active_run_id (:graph_run_id message)
                    :node_statuses (wire/id-keyed (:node_statuses message))})
     ::socket/send (actions/list-stream-graphs)}))

(rf/reg-event-db :graphs/stopped
  (fn [db [_ message]]
    (assoc-in db [:graph-statuses (:graph_id message)]
              {:graph_id (:graph_id message)
               :run_state "stopped"
               :active_run_id (:graph_run_id message)
               :node_statuses (wire/id-keyed (:node_statuses message))})))

(rf/reg-event-fx :graphs/refresh
  (fn [_ _]
    {::socket/send (actions/list-stream-graphs)}))

(rf/reg-event-fx :graphs/request-status
  (fn [_ [_ graph-id]]
    {::socket/send (actions/get-stream-graph-status graph-id)}))

(rf/reg-event-fx :graphs/poll-statuses
  ;; Driven on an interval (re-pollsive, Phase 2). Polling every known graph
  ;; mirrors the Svelte page's 1s refresh.
  (fn [{:keys [db]} _]
    (when (= :connected (:connection-state db))
      {::socket/send (mapv #(actions/get-stream-graph-status (:graph_id %))
                           (filterv #(seq (:graph_id %)) (:graphs db)))})))

(rf/reg-event-db :graphs/select
  (fn [db [_ graph-id]]
    (let [graph (some #(when (= graph-id (:graph_id %)) %) (:graphs db))]
      (assoc db
             :selected-graph-id graph-id
             ;; A composite graph's editor tree round-trips through
             ;; editor_metadata, so prefer it over the flattened nodes.
             :draft-graph (or (:editor_metadata graph) graph)
             :draft-dirty? false
             :selection {:node-ids #{} :edge-id nil}))))

(rf/reg-event-fx :graphs/start
  (fn [{:keys [db]} [_ graph-id start-offset]]
    ;; Optimistically flip to "starting": the backend creates topics and spins up
    ;; workers synchronously before replying, which can take many seconds, and the
    ;; UI must react to the click rather than look frozen.
    {:db (update-in db [:graph-statuses graph-id]
                    (fn [existing]
                      (merge {:graph_id graph-id
                              :active_run_id nil
                              :node_statuses {}}
                             existing
                             {:run_state "starting"})))
     ::socket/send (actions/start-stream-graph graph-id start-offset)}))

(rf/reg-event-fx :graphs/stop
  (fn [_ [_ graph-id]]
    {::socket/send (actions/stop-stream-graph graph-id)}))

(rf/reg-event-fx :graphs/validate
  (fn [_ [_ graph]]
    {::socket/send (actions/validate-stream-graph graph)}))

(rf/reg-event-fx :graphs/save
  (fn [_ [_ graph]]
    {::socket/send (actions/save-stream-graph graph)}))

(rf/reg-event-fx :graphs/restart-node
  (fn [_ [_ graph-id node-id]]
    {::socket/send (actions/restart-stream-graph-node graph-id node-id)}))

;; --- Profiles ---------------------------------------------------------------

(rf/reg-event-db :profiles/list-received
  (fn [db [_ message]]
    (assoc db :profiles (vec (sort-by :display_name (:profiles message))))))

(rf/reg-event-db :profiles/saved
  (fn [db [_ message]]
    (let [others (filterv #(not= (:participant_id message) (:participant_id %))
                          (:profiles db))]
      (assoc db :profiles (vec (sort-by :display_name
                                        (conj others (:profile message))))))))

(rf/reg-event-db :profiles/deleted
  (fn [db [_ message]]
    (update db :profiles
            (fn [profiles]
              (vec (remove #(= (:participant_id message) (:participant_id %))
                           profiles))))))

;; --- Live streams -----------------------------------------------------------
;; Phase 5 wires the real per-stream buffers (in a separate atom, deliberately).
;; For now the summary is enough to prove the feed is alive.

(defn- note-frame [db stream-id device-id]
  (-> db
      (update-in [:live stream-id :frames] (fnil inc 0))
      (assoc-in [:live stream-id :last-at-ms] (js/Date.now))
      (cond-> device-id (assoc-in [:live stream-id :device-name] device-id))))

(rf/reg-event-db :stream/frame-received
  (fn [db [_ message]]
    (note-frame db (:stream_id message) (:device_id message))))

(rf/reg-event-db :stream/imu-received
  (fn [db [_ message]] (note-frame db (:stream_id message) nil)))

(rf/reg-event-db :stream/imu-bulk-received
  (fn [db [_ message]] (note-frame db (:stream_id message) nil)))

(rf/reg-event-db :stream/muse-received
  (fn [db [_ message]] (note-frame db (:stream_id message) nil)))

(rf/reg-event-db :stream/muse-bulk-received
  (fn [db [_ message]] (note-frame db (:stream_id message) nil)))

(rf/reg-event-db :stream/marker-received
  (fn [db [_ message]] (note-frame db (:stream_id message) nil)))

(rf/reg-event-db :stream/time-received
  (fn [db [_ message]]
    (assoc-in db [:stream-time (:stream_id message)] message)))

(rf/reg-event-fx :stream/subscribe
  (fn [_ [_ stream-id start-offset]]
    {::socket/send (actions/subscribe [stream-id] start-offset)}))

(rf/reg-event-fx :stream/unsubscribe
  (fn [_ [_ stream-id]]
    {::socket/send (actions/unsubscribe [stream-id])}))

;; --- Transforms (legacy standalone actions) ---------------------------------

(rf/reg-event-db :transforms/result-received (fn [db _] db))
(rf/reg-event-db :transforms/list-received (fn [db _] db))
(rf/reg-event-db :transforms/stopped (fn [db _] db))

;; --- Experiments / ML -------------------------------------------------------

(rf/reg-event-fx :experiment/publish-result-received
  (fn [_ [_ message]]
    {:fx [[:dispatch [:toast/push :info
                      (str "Published session " (:session_id message) ": "
                           (:published_marker_events message) " markers.")]]]}))

(rf/reg-event-db :ml/control-plane-received
  (fn [db [_ envelope]]
    ;; The control-plane message is nested inside the envelope so it cannot
    ;; collide with stream_viewer's own types.
    (let [message (:message envelope)]
      (case (wire/message-type message)
        "thread_slots" (update db :ml merge {:thread-slots (or (:slots message) [])
                                            :worker-id (:worker_id message)
                                            :principal-id (:principal_id message)})
        "recorded_runs" (assoc-in db [:ml :recorded-runs] (or (:runs message) []))
        "job_accepted" (assoc-in db [:ml :train-job :status]
                                 (str "queued (" (or (:job_id message) "job") ")"))
        "job_status" (let [report (:report message)
                           status (:status message)]
                       (cond-> (assoc-in db [:ml :train-job :status]
                                         (str status ": " (:message message)))
                         (= "completed" status)
                         (update-in [:ml :train-job] merge
                                    {:model-path (:model_path report)
                                     :bundle-path (:bundle_path report)
                                     :accuracy (:selected_mean_accuracy report)})))
        db))))

(rf/reg-event-fx :ml/request-recorded-runs
  (fn [_ _]
    {::socket/send (actions/ml-proxy (actions/list-recorded-runs))}))
