(ns natkit.db
  "The shape of app-db, plus pure derivations over it.

  Two rules, both learned from the Svelte page:

  1. LIVE SAMPLE BUFFERS DO NOT LIVE HERE. The Svelte page hit a progressive
     stutter because deep-reactive proxies wrapped every sample read on the chart
     hot path; the fix was raw state plus a decoupled flush. app-db is subscribed
     to and snapshotted by undo, so a 100-frame x N-channel buffer in here would
     reintroduce that bug and multiply it. Buffers belong in a separate atom
     (natkit.stream.buffers, Phase 5); only a small per-stream summary lands here.

  2. Keys from the wire keep their snake_case spelling; keys this app invents are
     kebab-case. The boundary is therefore visible at a glance: `:graph_id` came
     from the backend, `:selected-graph-id` is ours."
  (:require [natkit.graph.model :as model]
            [natkit.protocol.wire :as wire]))

(def default-db
  {;; --- Connection ---------------------------------------------------------
   :connection-state :disconnected   ; :disconnected | :connecting | :connected
   :reconnect {:attempt 0 :delay_ms nil :abandoned? false}
   :toasts []                        ; [{:id :level :text}] — bottom-right stack

   ;; --- Discovery (from the backend) --------------------------------------
   :streams {}                       ; stream_id -> {:topics [...]}
   :node-catalog []                  ; the palette's single source of truth
   :graphs []                        ; [StreamGraphDefinition]
   :graph-statuses {}                ; graph_id -> StreamGraphStatusSummary
   :profiles []
   :stream-time {}                   ; stream_id -> stream_time reply

   ;; --- Validation ---------------------------------------------------------
   :diagnostics {:graph [] :nodes {} :edges {}}

   ;; --- Editor -------------------------------------------------------------
   :selected-graph-id nil
   :draft-graph nil                  ; the EditorGraphDefinition being edited
   :draft-dirty? false
   :selection {:node-ids #{} :edge-id nil}
   ;; Transient interaction state. In Svelte this was trapped inside a
   ;; 6,326-line component; here it is just data, which is what lets the editor
   ;; decompose into namespaces at all.
   :interaction {:drag nil :pan nil :pending-connection nil :context-menu nil}
   :palette-open? false
   :panels {:sidebar? true :inspector? true}

   ;; --- ML / experiments ---------------------------------------------------
   :ml {:thread-slots []
        :worker-id nil
        :principal-id nil
        :recorded-runs []
        :train-job {:status nil :model-path nil :bundle-path nil :accuracy nil}}

   ;; --- Live stream summaries (NOT the sample buffers — see rule 1) --------
   :live {}                          ; stream_id -> {:device-name :frames :last-at-ms}
   })

;; --- Derivations ------------------------------------------------------------

(defn transform-capabilities
  "The transform subset of the node catalog, reshaped as the capability records
  the descriptor/compat helpers expect. Derived, never fetched separately — the
  catalog is the single source of truth."
  [node-catalog]
  (into []
        (comp
         (filter #(= "transform" (:kind %)))
         (map (fn [entry]
                {:kind (:node_type entry)
                 :label (:label entry)
                 :description (:description entry)
                 :input_descriptor_paths (or (:input_descriptor_paths entry) [])
                 :input_mappings (or (:input_mappings entry) [])
                 :output_schema_name (or (:output_schema_name entry)
                                         "NatSignalFrameDataSchemaV1")
                 :config_fields (:config_fields entry)})))
        node-catalog))

(defn catalog-entry
  "The catalog entry for a node type, or nil."
  [node-catalog node-type]
  (some #(when (= node-type (:node_type %)) %) node-catalog))

(defn catalog-by-category
  "Catalog entries grouped by category, for the palette surfaces."
  [node-catalog]
  (group-by :category node-catalog))

(defn source-stream-options
  "Every discovered stream, as a source-node option. Deliberately NOT filtered to
  transform-compatible streams: a source node just represents a stream to view,
  record or route, and gating the list on transform capability used to hide
  non-channel-frame sensors (like the IMU) from the palette entirely.
  Compatibility is enforced later, at connection time."
  [streams]
  (->> streams
       (map (fn [[stream-id info]]
              (let [described (some #(when (:descriptor %) %) (:topics info))]
                {:streamId (wire/key-name stream-id)
                 :schemaName (or (get-in described [:descriptor :schema_name]) "Unknown")
                 :descriptor (:descriptor described)
                 :live false})))
       (sort-by :streamId)
       vec))

(defn graph-status [db graph-id]
  (get-in db [:graph-statuses graph-id]))

(defn graph-running?
  [db graph-id]
  (= "running" (:run_state (graph-status db graph-id))))

(defn selected-graph
  [db]
  (let [id (:selected-graph-id db)]
    (some #(when (= id (:graph_id %)) %) (:graphs db))))

(defn node-by-id
  [graph node-id]
  (some #(when (= node-id (:id %)) %) (:nodes graph)))

(defn selected-node
  [db]
  (let [node-ids (get-in db [:selection :node-ids])]
    (when (= 1 (count node-ids))
      (node-by-id (:draft-graph db) (first node-ids)))))

(defn node-diagnostics
  "Diagnostics for one node. The diagnostics tables are normalized to raw string
  ids on receipt (see natkit.protocol.wire/id-keyed), so this is a plain lookup."
  [db node-id]
  (get-in db [:diagnostics :nodes node-id]))

(defn draft-node-height [node]
  (model/node-height node))
