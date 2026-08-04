(ns natkit.graph.model
  "Pure graph model: geometry, identifiers, defaults, run-state classification.

  Port of frontend/src/VisualProgramming/streamGraph.ts. Node `kind` and
  `edge_kind` values are STRINGS here, matching the wire (see
  natkit.protocol.wire for why)."
  (:require [clojure.string :as str]))

;; --- Provenance ports -------------------------------------------------------
;; Provenance ports carry data lineage / control wiring, not streaming data.
;; They are identified purely by an id prefix so an edge can be classified as
;; provenance from its endpoints, rendered distinctly, and validated separately.

(def provenance-port-prefix "prov_")
;; source -> experiment: "records against this stream".
(def provenance-port-source "prov_source")
;; experiment -> train: "train on this experiment's sessions".
(def provenance-port-experiment "prov_experiment")
;; train -> classify (outbound): "the models this trainer produced".
(def provenance-port-models "prov_models")
;; train -> classify (inbound): "classify with a model this trainer produced".
(def provenance-port-model "prov_model")

(defn provenance-port?
  [port-id]
  (and (string? port-id) (str/starts-with? port-id provenance-port-prefix)))

(defn provenance-edge?
  "An edge is provenance if it is tagged as such, or if either endpoint is a
  provenance-typed port."
  [edge]
  (or (= "provenance" (:edge_kind edge))
      (provenance-port? (:source_port edge))
      (provenance-port? (:target_port edge))))

;; --- Layout constants -------------------------------------------------------

(def default-viewport {:x 0 :y 0 :zoom 1})
(def node-width 220)
(def header-height 42)
(def port-row-height 28)
;; Extra height a viewer node reserves below its ports to host an inline chart.
;; Ports anchor to the TOP (see port-position), so growing a card downward never
;; moves a port and edges stay attached.
(def inline-graph-height 210)

;; --- Identifiers ------------------------------------------------------------

(defn sanitize-identifier
  "Backend-safe identifier: only [A-Za-z0-9_-], no runs of dashes, no leading
  dash, max 64 chars."
  [value]
  (let [s (-> (str value)
              (str/replace #"[^A-Za-z0-9_-]" "-")
              (str/replace #"--+" "-")
              (str/replace #"^-+" ""))]
    (subs s 0 (min 64 (count s)))))

(defn empty-graph
  "A fresh, empty draft graph."
  []
  (let [now-us (* 1000 (js/Date.now))]
    {:graph_version 1
     :graph_id (str "stream-graph-" (js/Date.now))
     :label "Untitled graph"
     :description ""
     :created_at_us now-us
     :updated_at_us now-us
     :ui {:viewport default-viewport
          :selected_node_id nil}
     :nodes []
     :edges []
     :notes []}))

;; --- Geometry ---------------------------------------------------------------

(defn node-height
  [node]
  (let [inputs (count (:input_port_ids node))
        outputs (count (:output_port_ids node))
        rows (max inputs outputs 1)
        base (+ header-height (* rows port-row-height) 22)]
    (if (and (= "viewer" (:kind node)) (:inline_graph node))
      (+ base inline-graph-height)
      base)))

(defn- index-of
  "Index of `x` in `coll`, or -1. (Mirrors Array#indexOf, which the TS used.)"
  [coll x]
  (or (first (keep-indexed (fn [i v] (when (= v x) i)) coll)) -1))

(defn port-position
  "Where a port anchors, in graph coordinates. `side` is :input or :output."
  [node port-id side]
  (let [ports (if (= :input side)
                (:input_port_ids node)
                (:output_port_ids node))
        index (max 0 (index-of ports port-id))]
    {:x (+ (get-in node [:position :x])
           (if (= :input side) 0 node-width))
     :y (+ (get-in node [:position :y])
           header-height
           (* port-row-height index)
           (/ port-row-height 2))}))

;; --- Config defaults --------------------------------------------------------

(defn default-transform-config
  "Seed a transform's config from its catalog entry's declared defaults. Config
  field ids come from the runtime catalog, so nothing here is hardcoded."
  [capability]
  (reduce (fn [config {:keys [id default_value default_option]}]
            (cond
              (some? default_value) (assoc config (keyword id) default_value)
              (some? default_option) (assoc config (keyword id) default_option)
              :else config))
          {}
          (:config_fields capability)))

;; --- Descriptors ------------------------------------------------------------

(defn- field
  ([id type] (field id type nil))
  ([id type extra]
   (merge {:id id :label id :type type :optional false} extra)))

(def canonical-channel-frame-descriptor
  "The descriptor a transform/combine node emits. A REAL descriptor, not an empty
  stub — downstream compatibility checks, input-mapping auto-pick and the
  \"recommended next\" list all probe these fields."
  {:schema_name "NatSignalFrameDataSchemaV1"
   :descriptor_version 1
   :root (field "root" "object"
                {:fields
                 {:device_id (field "device_id" "string")
                  :seq_no (field "seq_no" "uint64")
                  :device_ts_us (field "device_ts_us" "uint64")
                  :sample_rate_hz (field "sample_rate_hz" "uint32")
                  :channels (field "channels" "array"
                                   {:items (field "channel" "object"
                                                  {:fields
                                                   {:label (field "label" "string")
                                                    :samples (field "samples" "array"
                                                                    {:items (field "sample" "float32")})}})})}})})

(defn output-descriptor
  "The descriptor on a node's output, or nil if it has none / is unknown.
  `available-streams` is the seq of {:streamId :descriptor ...} source options."
  [node available-streams]
  (when node
    (case (:kind node)
      "stream_source" (some (fn [stream]
                              (when (= (:streamId stream) (:stream_id node))
                                (:descriptor stream)))
                            available-streams)
      ("transform" "combine") canonical-channel-frame-descriptor
      nil)))

;; --- Run state --------------------------------------------------------------

(defn run-state-class
  "Coarse visual class for a run/node state. Returns :ok, :error or :muted."
  [state]
  (cond
    (contains? #{"running" "valid"} state) :ok
    (contains? #{"error" "stalled"} state) :error
    :else :muted))
