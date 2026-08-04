(ns natkit.protocol.wire-test
  "The codec invariant: wire keys survive a round trip VERBATIM.

  This is the single most important test in the port. `editor_metadata` carries
  the unflattened composite editor tree and is stored + returned by the backend
  without interpretation, so a composite graph reloads from the backend alone. A
  transform's `config` keys likewise come from the runtime node catalog and are
  unknown at compile time. Any global snake_case -> kebab-case conversion would
  corrupt both, silently."
  (:require [cljs.test :refer-macros [deftest testing is]]
            [natkit.protocol.wire :as wire]))

;; A payload shaped like a real stream_graph_list reply, including the two things
;; that must round-trip opaquely: editor_metadata and a catalog-driven config map.
(def graph-list-payload
  {:type "stream_graph_list"
   :request_id "stream-graphs:1753700000000"
   :graphs
   [{:graph_version 1
     :graph_id "vp-verify"
     :label "Filter + envelope"
     :description ""
     :created_at_us 1753700000000000
     :updated_at_us 1753700000000000
     :ui {:viewport {:x -120 :y 40 :zoom 0.9}
          :selected_node_id "tf-bandpass"}
     :nodes
     [{:id "src-emg"
       :kind "stream_source"
       :label "EMG"
       :position {:x 0 :y 0}
       :stream_id "10836297661294969472"
       :schema_name "ExgPillEmgDataSchemaV1"
       :output_port_ids ["data"]}
      {:id "tf-bandpass"
       :kind "transform"
       :label "Band-pass"
       :position {:x 280 :y 0}
       :transform_kind "bandpass_iir"
       :input_mapping_id "canonical_channel_frame"
       :config {:low_cutoff_hz 20
                :high_cutoff_hz 450
                :iir_method "butterworth"
                :butterworth_order 4}
       :output_identifier "emg-bandpass"
       :output_stream_id "4471822295861948416"
       :input_port_ids ["in1"]
       :output_port_ids ["out1"]}]
     :edges
     [{:id "e1"
       :source_node_id "src-emg"
       :source_port "data"
       :target_node_id "tf-bandpass"
       :target_port "in1"
       :hidden_topic_types ["Meta"]
       :edge_kind "data"}]
     :notes []
     ;; The opaque editor tree. The backend never looks inside this.
     :editor_metadata
     {:graph_version 1
      :graph_id "vp-verify"
      :label "Filter + envelope"
      :nodes [{:id "composite/filter-abc"
               :kind "composite"
               :label "My Filter"
               :position {:x 280 :y 0}
               :composite_id "composite-mfx1-1"
               :composite_version 1
               :input_port_ids ["in1"]
               :output_port_ids ["out1"]
               :template {:composite_version 1
                          :composite_id "composite-mfx1-1"
                          :label "My Filter"
                          :nodes []
                          :edges []
                          :inputs []
                          :outputs []}}]
      :edges []}}]
   ;; Id-keyed maps use STRING keys: "vp-verify" and "tf-bandpass" contain a
   ;; dash, so they are not plain field names and stay strings on decode (rule 2).
   :statuses
   {"vp-verify" {:graph_id "vp-verify"
                :run_state "running"
                :active_run_id "run-77"
                :node_statuses
                {"tf-bandpass" {:state "running"
                               :output_stream_id "4471822295861948416"
                               :output_topics [{:type "Data"
                                                :id "4471822295861948416"
                                                :schema "NatSignalFrameDataSchemaV1"}]
                               :worker_id "worker-1"
                               :thread_slot_id "slot-0"
                               :frames_processed 1284
                               :last_frame_at_us 1753700009000000}}}}})

(deftest round-trips-a-graph-list-payload-unchanged
  (is (wire/round-trips? graph-list-payload)))

(deftest keeps-snake-case-keys-verbatim
  (testing "encoding emits the exact wire spellings the backend expects"
    (let [json (wire/encode graph-list-payload)]
      ;; If a kebab-case conversion ever creeps in, these fail loudly.
      (is (re-find #"\"graph_id\"" json))
      (is (re-find #"\"output_stream_id\"" json))
      (is (re-find #"\"source_node_id\"" json))
      (is (re-find #"\"editor_metadata\"" json))
      (is (re-find #"\"low_cutoff_hz\"" json))
      (is (nil? (re-find #"graph-id" json)))
      (is (nil? (re-find #"output-stream-id" json)))
      (is (nil? (re-find #"editor-metadata" json))))))

(deftest editor-metadata-survives-a-full-round-trip
  (testing "the nested composite template is byte-identical after encode -> parse"
    (let [original (get-in graph-list-payload [:graphs 0 :editor_metadata])
          restored (get-in (wire/parse (wire/encode graph-list-payload))
                           [:graphs 0 :editor_metadata])]
      (is (= original restored))
      (is (= "composite-mfx1-1"
             (get-in restored [:nodes 0 :template :composite_id]))))))

(deftest catalog-driven-config-keys-survive
  (testing "config field ids come from the runtime catalog, so they must pass through"
    (let [restored (wire/parse (wire/encode graph-list-payload))
          config (get-in restored [:graphs 0 :nodes 1 :config])]
      (is (= {:low_cutoff_hz 20
              :high_cutoff_hz 450
              :iir_method "butterworth"
              :butterworth_order 4}
             config)))))

(deftest values-stay-strings-not-keywords
  (testing "only keys are keywordized — a kind/schema_name must remain a string"
    (let [restored (wire/parse (wire/encode graph-list-payload))
          node (get-in restored [:graphs 0 :nodes 0])]
      (is (= "stream_source" (:kind node)))
      (is (string? (:kind node)))
      (is (= "ExgPillEmgDataSchemaV1" (:schema_name node)))
      (is (string? (:schema_name node)))
      (testing "including a stream id, which is a stringified uint64"
        (is (string? (:stream_id node)))
        (is (= "10836297661294969472" (:stream_id node)))))))

;; --- Rule 2: which keys become keywords -------------------------------------

(deftest only-plain-field-names-become-keywords
  (is (true? (wire/field-name? "graph_id")))
  (is (true? (wire/field-name? "seq_no")))
  (is (true? (wire/field-name? "_private")))
  (testing "ids are not field names"
    (is (false? (wire/field-name? "source/13793649670644-1785250699870")))
    (is (false? (wire/field-name? "vp-verify")))
    (is (false? (wire/field-name? "1112596048936639351")))
    (is (false? (wire/field-name? "")))))

(deftest slash-containing-keys-survive-a-round-trip
  ;; REGRESSION: `js->clj :keywordize-keys true` turns "source/x" into the
  ;; NAMESPACED keyword :source/x, and `clj->js` writes back only the name — so
  ;; the key silently became "x". natKit node ids routinely contain a slash and
  ;; node_statuses is keyed by node id, so this corrupted real payloads.
  (let [payload {:type "stream_graph_status"
                 :graph_id "stream-graph-1785250697509"
                 :status
                 {:graph_id "stream-graph-1785250697509"
                  :run_state "running"
                  :node_statuses
                  {"source/13793649670644-1785250699870" {:state "running"}
                   "viewer/1785250704391" {:state "running"}
                   "composite/filter-abc::tx" {:state "stalled"}}}}]
    (is (wire/round-trips? payload))
    (testing "the full id, prefix included, is still the key"
      (let [restored (wire/parse (wire/encode payload))]
        (is (= #{"source/13793649670644-1785250699870"
                 "viewer/1785250704391"
                 "composite/filter-abc::tx"}
               (set (keys (get-in restored [:status :node_statuses])))))
        (is (= "stalled" (get-in restored [:status :node_statuses
                                           "composite/filter-abc::tx" :state])))))))

(deftest id-keyed-normalizes-a-lookup-table
  (testing "an id that happens to look like a field name still indexes by id"
    ;; A graph literally named "verify" keywordizes; "vp-verify" does not. Both
    ;; must be reachable with the raw string id.
    (let [statuses (wire/id-keyed (:statuses (wire/parse (wire/encode
                                                          {:statuses
                                                           {"verify" {:run_state "stopped"}
                                                            "vp-verify" {:run_state "running"}}}))))]
      (is (= #{"verify" "vp-verify"} (set (keys statuses))))
      (is (= "running" (:run_state (get statuses "vp-verify"))))
      (is (= "stopped" (:run_state (get statuses "verify")))))))

(deftest key-name-is-safe-on-namespaced-keywords
  (is (= "graph_id" (wire/key-name :graph_id)))
  (is (= "source/abc" (wire/key-name :source/abc)))
  (is (= "source/abc" (wire/key-name "source/abc"))))

(deftest empty-collections-and-nulls-round-trip
  (let [payload {:nodes [] :edges [] :notes []
                 :ui {:selected_node_id nil :viewport {:x 0 :y 0 :zoom 1}}
                 :description ""
                 :config {}}]
    (is (wire/round-trips? payload))
    (testing "a JSON null stays nil rather than vanishing"
      (is (contains? (:ui (wire/parse (wire/encode payload))) :selected_node_id))
      (is (nil? (get-in (wire/parse (wire/encode payload)) [:ui :selected_node_id]))))))

(deftest microsecond-timestamps-keep-full-precision
  ;; Wire timestamps are microseconds since epoch (~1.78e15) — inside JS's safe
  ;; integer range, but close enough to it to be worth pinning.
  (let [payload {:updated_at_us 1784308749619698 :created_at_us 1784226524116000}]
    (is (wire/round-trips? payload))
    (is (= 1784308749619698 (:updated_at_us (wire/parse (wire/encode payload)))))))

(deftest parse-reports-invalid-json-instead-of-throwing
  (let [parsed (wire/parse "{not json")]
    (is (wire/invalid-json? parsed))
    (is (not (wire/invalid-json? (wire/parse "{\"type\":\"status\"}"))))))

(deftest message-and-action-accessors
  (is (= "stream_graph_list" (wire/message-type graph-list-payload)))
  (is (= "save_stream_graph"
         (wire/action-name {:action "save_stream_graph" :request_id "x"})))
  (testing "request ids are prefixed so a WS trace is readable"
    (is (re-find #"^stream-graph-save:\d+$" (wire/request-id "stream-graph-save")))))

(deftest error-message-prefers-message-then-error
  (is (= "boom" (wire/error-message {:type "error" :message "boom"})))
  (is (= "bang" (wire/error-message {:type "error" :error "bang"})))
  (is (= "Unknown backend error" (wire/error-message {:type "error"}))))

(deftest marker-attributes-are-looked-up-by-string-name
  (testing "the per-cue class label lives under a backend-defined attribute name"
    (let [marker {:type "marker"
                  :session_id "s1"
                  :marker_type "cue"
                  :attributes {:gesture "flex" :repetition 3}}]
      (is (= "flex" (wire/marker-attribute marker "gesture")))
      (is (= 3 (wire/marker-attribute marker "repetition")))
      (is (nil? (wire/marker-attribute marker "missing"))))))
