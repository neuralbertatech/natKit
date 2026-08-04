(ns natkit.protocol.schema
  "malli schemas for the /ws/stream_viewer protocol.

  These replace ~1,400 lines of TypeScript interfaces with data that also
  validates at RUNTIME — which is the upgrade, since TS types evaporate exactly
  where the risk is (the wire). Used two ways:

    - in tests, against golden payloads captured from a live backend
      (scripts/protocol_smoke.mjs --capture);
    - as a dev-only assertion at the socket boundary, compiled out of :advanced
      release builds via natkit.config/debug?.

  Schemas are deliberately OPEN (no :closed true). The backend adds fields
  routinely and a closed schema would turn every additive protocol change into a
  frontend outage. What we pin is that the fields we DEPEND on are present and
  correctly typed."
  (:require [malli.core :as m]
            [malli.error :as me]
            [natkit.config :as config]))

;; --- Primitives -------------------------------------------------------------

;; Stream ids are stringified uint64 on the wire — never coerce them to numbers,
;; they exceed JS's safe integer range.
(def StreamId [:string {:min 1}])
(def Micros :int)

(def Position [:map [:x number?] [:y number?]])

;; A decoded wire key is a keyword when it looked like a plain snake_case field
;; name and a string otherwise (an id, which may contain a slash). See
;; natkit.protocol.wire rule 2 — every :map-of over wire keys must allow both.
(def WireKey [:or :keyword :string])

(def SchemaFieldDescriptor
  [:schema {:registry
            {::field [:map
                      [:id :string]
                      [:label :string]
                      [:type :string]
                      [:optional {:optional true} :boolean]
                      [:description {:optional true} :string]
                      [:unit {:optional true} :string]
                      [:enum_values {:optional true} [:sequential :string]]
                      [:fields {:optional true} [:map-of WireKey [:ref ::field]]]
                      [:items {:optional true} [:ref ::field]]]}}
   [:ref ::field]])

(def DataSchemaDescriptor
  [:map
   [:schema_name :string]
   [:descriptor_version {:optional true} :int]
   [:root {:optional true} SchemaFieldDescriptor]])

;; --- Discovery --------------------------------------------------------------

(def StreamTopic
  [:map
   [:schema_name :string]
   [:type :string]                    ; "Data" | "Meta"
   [:serialization_type {:optional true} :string]
   [:descriptor {:optional true} DataSchemaDescriptor]])

(def StreamInfo
  [:map [:topics [:sequential StreamTopic]]])

(def StreamListMessage
  [:map
   [:type [:= "stream_list"]]
   [:streams [:map-of WireKey StreamInfo]]])

(def ConfigField
  [:map
   [:id :string]
   [:label :string]
   [:type :string]                    ; "number" | "enum" | "string"
   [:required {:optional true} :boolean]
   [:min {:optional true} number?]
   [:step {:optional true} number?]
   ;; NOT number-only, despite what the Svelte frontend's TypeScript declares
   ;; (`default_value?: number`). The live backend sends a STRING default for a
   ;; string-typed field — e.g. channel_select's `selection` defaults to "mav".
   ;; Validating this schema against a captured catalog is what surfaced it.
   [:default_value {:optional true} [:or number? :string :boolean]]
   [:default_option {:optional true} :string]
   [:options {:optional true} [:sequential :string]]])

(def PortTemplate
  [:map
   [:id :string]
   [:label :string]
   [:descriptor {:optional true} DataSchemaDescriptor]])

(def InputMapping
  [:map
   [:id :string]
   [:label {:optional true} :string]
   [:mode :string]                    ; canonical_channel_frame | explicit_channel_paths
   [:schema_name {:optional true} :string]
   [:required_descriptor_paths {:optional true} [:sequential :string]]
   [:channels {:optional true}
    [:sequential [:map [:label :string] [:sample_array_path :string]]]]])

;; The palette's contract. Note `kind` and `node_type` are open strings: adding a
;; node type on the backend must never require editing this file.
(def NodeCatalogEntry
  [:map
   [:node_type :string]
   [:kind :string]
   [:category :string]
   [:runner :string]
   [:label :string]
   [:description {:optional true} :string]
   [:config_fields [:sequential ConfigField]]
   [:input_ports [:sequential PortTemplate]]
   [:output_ports [:sequential PortTemplate]]
   [:variadic_inputs {:optional true} :boolean]
   [:input_mappings {:optional true} [:sequential InputMapping]]
   [:input_descriptor_paths {:optional true} [:sequential :string]]
   [:output_schema_name {:optional true} :string]])

(def NodeCatalogMessage
  [:map
   [:type [:= "node_catalog"]]
   [:request_id {:optional true} :string]
   [:nodes [:sequential NodeCatalogEntry]]])

;; --- Graphs -----------------------------------------------------------------

(def GraphNode
  [:map
   [:id :string]
   [:kind :string]
   [:label :string]
   [:position Position]
   [:input_port_ids {:optional true} [:sequential :string]]
   [:output_port_ids {:optional true} [:sequential :string]]
   ;; Transform/combine.
   [:transform_kind {:optional true} :string]
   [:input_mapping_id {:optional true} :string]
   ;; Catalog-driven, so the keys are unknown at compile time — hence :any.
   [:config {:optional true} [:map-of WireKey :any]]
   [:output_identifier {:optional true} :string]
   [:output_stream_id {:optional true} :string]
   ;; Source.
   [:stream_id {:optional true} :string]
   [:schema_name {:optional true} :string]])

(def GraphEdge
  [:map
   [:id :string]
   [:source_node_id :string]
   [:source_port :string]
   [:target_node_id :string]
   [:target_port :string]
   [:hidden_topic_types {:optional true} [:sequential :string]]
   [:edge_kind {:optional true} :string]])

(def GraphDefinition
  [:map
   [:graph_version [:= 1]]
   [:graph_id :string]
   [:label :string]
   [:description {:optional true} [:maybe :string]]
   [:created_at_us {:optional true} Micros]
   [:updated_at_us {:optional true} Micros]
   [:ui {:optional true} [:map
                          [:viewport {:optional true}
                           [:map [:x number?] [:y number?] [:zoom number?]]]
                          [:selected_node_id {:optional true} [:maybe :string]]]]
   [:nodes [:sequential GraphNode]]
   [:edges [:sequential GraphEdge]]
   [:notes {:optional true} [:sequential :string]]
   ;; OPAQUE. The backend stores and returns this verbatim; nothing in this app
   ;; may interpret or reshape it. See natkit.protocol.wire.
   [:editor_metadata {:optional true} :any]])

(def NodeStatus
  [:map
   [:state :string]
   [:output_stream_id {:optional true} :string]
   [:output_topics {:optional true}
    [:sequential [:map [:type :string] [:id :string] [:schema :string]]]]
   [:worker_id {:optional true} :string]
   [:thread_slot_id {:optional true} :string]
   [:frames_processed {:optional true} :int]
   [:last_frame_at_us {:optional true} Micros]
   [:message {:optional true} :string]])

(def GraphStatusSummary
  [:map
   [:graph_id :string]
   [:run_state :string]
   [:active_run_id {:optional true} [:maybe :string]]
   [:node_statuses [:map-of WireKey NodeStatus]]])

(def StreamGraphListMessage
  [:map
   [:type [:= "stream_graph_list"]]
   [:request_id {:optional true} :string]
   [:graphs [:sequential GraphDefinition]]
   [:statuses [:map-of WireKey GraphStatusSummary]]])

(def ProfileListMessage
  [:map
   [:type [:= "profile_list"]]
   [:request_id {:optional true} :string]
   [:profiles [:sequential [:map
                            [:participant_id :string]
                            [:display_name :string]
                            [:graph_id {:optional true} :string]]]]])

(def ErrorMessage
  [:map
   [:type [:= "error"]]
   [:message {:optional true} :string]])

;; --- Registry ---------------------------------------------------------------

(def message-schemas
  "Schemas for the inbound messages this app depends on structurally. Messages
  absent from this map are still handled — they just aren't schema-checked."
  {"stream_list" StreamListMessage
   "node_catalog" NodeCatalogMessage
   "stream_graph_list" StreamGraphListMessage
   "profile_list" ProfileListMessage
   "error" ErrorMessage})

(defn explain
  "nil when `value` conforms to `schema`, otherwise a humanized explanation."
  [schema value]
  (when-let [error (m/explain schema value)]
    (me/humanize error)))

(defn valid?
  [schema value]
  (m/validate schema value))

(defn check-message!
  "Dev-only assertion at the socket boundary. Logs a structural mismatch and
  returns the message unchanged — a schema drift must never break the app, only
  make itself visible. Dead code in :advanced release builds."
  [message]
  (when config/debug?
    (when-let [schema (get message-schemas (:type message))]
      (when-let [problems (explain schema message)]
        (js/console.warn "Protocol schema mismatch for"
                         (:type message)
                         (clj->js problems)))))
  message)
