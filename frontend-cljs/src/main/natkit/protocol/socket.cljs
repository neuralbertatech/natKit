(ns natkit.protocol.socket
  "WebSocket transport for /ws/stream_viewer, as re-frame effects.

  WHY THIS IS HAND-ROLLED (correcting plan §5.2): the plan proposed `websocket-fx`
  to replace the Svelte `StreamViewerWebSocket` class. On inspection it does not
  fit. websocket-fx imposes its own envelope on every frame —
  `{:id <uuid> :proto :request|:subscription|:push :data <payload>}` — and routes
  inbound frames by matching `:id` against an outstanding request or an open
  subscription.

  natKit's protocol is flat and mostly push-driven: outbound is
  `{\"action\": ...}`, inbound is `{\"type\": ...}`, and the majority of inbound
  frames are UNSOLICITED broadcasts (stream_graph_status, live frames,
  ml_control_plane relays) that correlate to no request id. Under websocket-fx
  those frames would route nowhere, so adopting it would mean changing the
  backend protocol — explicitly out of scope for this port.

  What follows is the ~100 lines that actually apply: connect, exponential
  backoff, send, and inbound dispatch into re-frame. The rest of the rvbbit stack
  (re-pollsive, undo, re-pressed, garden, re-com) is unaffected.

  The live socket object lives in an atom OUTSIDE app-db, since a mutable JS
  object is not a value and must never be snapshotted by undo."
  (:require [re-frame.core :as rf]
            [natkit.config :as config]
            [natkit.protocol.wire :as wire]))

(defonce ^:private connection (atom {:ws nil :attempts 0 :timer nil}))

(def max-reconnect-attempts 5)
(def base-reconnect-delay-ms 1000)

(defn reconnect-delay-ms
  "Exponential backoff, matching the Svelte client: 1s, 2s, 4s, 8s, 16s."
  [attempts]
  (* base-reconnect-delay-ms (js/Math.pow 2 attempts)))

(defn give-up?
  [attempts]
  (>= attempts max-reconnect-attempts))

;; --- Inbound routing --------------------------------------------------------
;; A pure message-type -> re-frame event mapping, so routing is testable without
;; a socket. Several wire types are aliases for one event:
;;   "frame" is the generic descriptor-driven channel frame; "emg_data" is the
;;   legacy per-sensor alias for the same payload shape.
;;   "transform_*" / "emg_transform_*" likewise.

(def message-type->event
  {"stream_list"             [:streams/list-received]
   "status"                  [:protocol/status-received]
   "node_catalog"            [:catalog/received]
   "transform_capabilities"  [:catalog/transform-capabilities-received]
   "stream_graph_list"       [:graphs/list-received]
   "stream_graph_saved"      [:graphs/saved]
   "stream_graph_validation" [:graphs/validation-received]
   "stream_graph_status"     [:graphs/status-received]
   "stream_graph_started"    [:graphs/started]
   "stream_graph_stopped"    [:graphs/stopped]
   "profile_list"            [:profiles/list-received]
   "profile_saved"           [:profiles/saved]
   "profile_deleted"         [:profiles/deleted]
   "frame"                   [:stream/frame-received]
   "emg_data"                [:stream/frame-received]
   "imu_data"                [:stream/imu-received]
   "imu_bulk_data"           [:stream/imu-bulk-received]
   "muse_data"               [:stream/muse-received]
   "muse_bulk_data"          [:stream/muse-bulk-received]
   "marker"                  [:stream/marker-received]
   "stream_time"             [:stream/time-received]
   "transform_provenance"    [:protocol/provenance-received]
   "transform_result"        [:transforms/result-received]
   "emg_transform_result"    [:transforms/result-received]
   "transform_list"          [:transforms/list-received]
   "emg_transform_list"      [:transforms/list-received]
   "transform_stopped"       [:transforms/stopped]
   "emg_transform_stopped"   [:transforms/stopped]
   "publish_result"          [:experiment/publish-result-received]
   "ml_control_plane"        [:ml/control-plane-received]
   "error"                   [:protocol/error-received]})

(defn message->event
  "The re-frame event for an inbound message. Unknown types route to a single
  event rather than being dropped silently, so a protocol addition is visible."
  [message]
  (if-let [event (get message-type->event (wire/message-type message))]
    (conj event message)
    [:protocol/unknown-message message]))

;; --- Effects ----------------------------------------------------------------

(declare open!)

(defn- schedule-reconnect! []
  (let [{:keys [attempts timer]} @connection]
    (when timer (js/clearTimeout timer))
    (if (give-up? attempts)
      (rf/dispatch [:protocol/reconnect-abandoned attempts])
      (let [delay (reconnect-delay-ms attempts)
            t (js/setTimeout #(open! (config/ws-url)) delay)]
        (swap! connection assoc :attempts (inc attempts) :timer t)
        (rf/dispatch [:protocol/reconnect-scheduled {:attempt (inc attempts)
                                                     :delay_ms delay}])))))

(defn- open! [url]
  (let [{:keys [ws]} @connection]
    (when-not (and ws (#{js/WebSocket.CONNECTING js/WebSocket.OPEN} (.-readyState ws)))
      (rf/dispatch [:protocol/connection-state :connecting])
      (try
        (let [socket (js/WebSocket. url)]
          (swap! connection assoc :ws socket)
          (set! (.-onopen socket)
                (fn [_]
                  (swap! connection assoc :attempts 0)
                  (rf/dispatch [:protocol/connection-state :connected])
                  (rf/dispatch [:protocol/connected])))
          (set! (.-onclose socket)
                (fn [_]
                  (swap! connection assoc :ws nil)
                  (rf/dispatch [:protocol/connection-state :disconnected])
                  (schedule-reconnect!)))
          (set! (.-onerror socket)
                (fn [_] (rf/dispatch [:protocol/socket-error])))
          (set! (.-onmessage socket)
                (fn [event]
                  (let [parsed (wire/parse (.-data event))]
                    (if (wire/invalid-json? parsed)
                      (rf/dispatch [:protocol/malformed-frame (.-data event)])
                      (rf/dispatch (message->event parsed)))))))
        (catch :default e
          (rf/dispatch [:protocol/connection-state :disconnected])
          (rf/dispatch [:protocol/socket-error (str e)])
          (schedule-reconnect!))))))

(defn- close! []
  (let [{:keys [ws timer]} @connection]
    (when timer (js/clearTimeout timer))
    (when ws (.close ws))
    (reset! connection {:ws nil :attempts 0 :timer nil})))

(defn connected?
  []
  (let [{:keys [ws]} @connection]
    (and ws (= js/WebSocket.OPEN (.-readyState ws)))))

(defn- send!
  "Serialize and send one action. Returns true when it went out."
  [action]
  (if (connected?)
    (do (.send (:ws @connection) (wire/encode action)) true)
    (do (rf/dispatch [:protocol/send-while-disconnected action]) false)))

(rf/reg-fx ::connect (fn [_] (open! (config/ws-url))))
(rf/reg-fx ::disconnect (fn [_] (close!)))

(rf/reg-fx ::send
  (fn [action-or-actions]
    (doseq [action (if (sequential? action-or-actions) action-or-actions [action-or-actions])]
      (when action (send! action)))))
