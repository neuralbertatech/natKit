(ns natkit.protocol.actions
  "Outbound action builders — pure maps, one per backend action.

  Kept separate from the effect layer so every action's exact wire shape is unit
  testable without a socket. Field names are the wire's, verbatim."
  (:require [natkit.protocol.wire :as wire]))

(defn get-streams []
  {:action "get_streams"})

(defn list-node-catalog []
  {:action "list_node_catalog"
   :request_id (wire/request-id "node-catalog")})

(defn list-stream-graphs []
  {:action "list_stream_graphs"
   :request_id (wire/request-id "stream-graphs")})

(defn get-stream-graph-status [graph-id]
  {:action "get_stream_graph_status"
   :request_id (wire/request-id "stream-graph-status")
   :graph_id graph-id})

(defn save-stream-graph [graph]
  {:action "save_stream_graph"
   :request_id (wire/request-id "stream-graph-save")
   :graph graph})

(defn validate-stream-graph [graph]
  {:action "validate_stream_graph"
   :request_id (wire/request-id "stream-graph-validate")
   :graph graph})

(defn start-stream-graph
  "Start a graph. `start-offset` is optional replay support: -1 live (default),
  -2 beginning, or a concrete offset from a query_stream_time reply."
  ([graph-id] (start-stream-graph graph-id nil))
  ([graph-id start-offset]
   (cond-> {:action "start_stream_graph"
            :request_id (wire/request-id "stream-graph-start")
            :graph_id graph-id}
     (some? start-offset) (assoc :start_offset start-offset))))

(defn stop-stream-graph [graph-id]
  {:action "stop_stream_graph"
   :request_id (wire/request-id "stream-graph-stop")
   :graph_id graph-id})

(defn restart-stream-graph-node
  "Restart one node + its downstream subgraph in a running graph, after its
  config was saved. This is the incremental-reactivity path."
  [graph-id node-id]
  {:action "restart_stream_graph_node"
   :request_id (wire/request-id "stream-graph-restart")
   :graph_id graph-id
   :node_id node-id})

(defn subscribe
  ([stream-ids] (subscribe stream-ids nil))
  ([stream-ids start-offset]
   (cond-> {:action "subscribe"
            :stream_ids (vec stream-ids)}
     (some? start-offset) (assoc :start_offset start-offset))))

(defn unsubscribe [stream-ids]
  {:action "unsubscribe"
   :stream_ids (vec stream-ids)})

(defn query-stream-time
  ([stream-id] (query-stream-time stream-id nil nil))
  ([stream-id timestamp-us] (query-stream-time stream-id timestamp-us nil))
  ([stream-id timestamp-us request-id]
   (cond-> {:action "query_stream_time"
            :stream_id stream-id}
     (some? timestamp-us) (assoc :timestamp_us timestamp-us)
     (some? request-id) (assoc :request_id request-id))))

(defn list-profiles []
  {:action "list_profiles"
   :request_id (wire/request-id "profiles")})

(defn save-profile [profile]
  {:action "save_profile"
   :request_id (wire/request-id "profile-save")
   :profile profile})

(defn delete-profile [participant-id]
  {:action "delete_profile"
   :request_id (wire/request-id "profile-delete")
   :participant_id participant-id})

(defn publish-session-bundle
  "Publish a recorded session's metadata + markers. Recording is client-driven;
  this forwards the bundle over the same socket that carries the graph protocol."
  [{:keys [request-id session-id meta-records marker-events]}]
  {:action "publish_session_bundle"
   :request_id request-id
   :session_id session-id
   :meta_records (vec meta-records)
   :marker_events (vec marker-events)})

(defn ml-proxy
  "Wrap a control-plane action for the backend to relay upstream. Replies come
  back as `ml_control_plane` envelopes."
  [control-plane-action]
  {:action "ml_proxy"
   :message control-plane-action})

;; --- Control-plane actions (ride inside ml-proxy) ---------------------------

(defn list-thread-slots []
  {:action "list_thread_slots"
   :request_id (wire/request-id "thread-slots")})

(defn list-recorded-runs []
  {:action "list_recorded_runs"
   :request_id (wire/request-id "recorded-runs")})
