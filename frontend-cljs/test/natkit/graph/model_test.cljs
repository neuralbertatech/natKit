(ns natkit.graph.model-test
  "Covers the geometry/identifier helpers ported from streamGraph.ts. The Svelte
  original had no direct unit tests — these are new, and they pin the port."
  (:require [cljs.test :refer-macros [deftest testing is]]
            [natkit.graph.model :as model]
            [natkit.stream.descriptor :as descriptor]))

(deftest sanitize-identifier-produces-backend-safe-ids
  (is (= "my-filter" (model/sanitize-identifier "my filter")))
  (testing "runs of dashes collapse and leading dashes are stripped"
    (is (= "a-b" (model/sanitize-identifier "a   b")))
    (is (= "a-b" (model/sanitize-identifier "a///b")))
    (is (= "leading" (model/sanitize-identifier "---leading"))))
  (testing "underscores and existing dashes are preserved"
    (is (= "emg_bandpass-1" (model/sanitize-identifier "emg_bandpass-1"))))
  (testing "the result is capped at 64 characters"
    (is (= 64 (count (model/sanitize-identifier (apply str (repeat 200 "a")))))))
  (testing "a fully illegal label collapses to empty (callers supply a fallback)"
    (is (= "" (model/sanitize-identifier "!!!")))))

(deftest empty-graph-is-a-valid-draft
  (let [graph (model/empty-graph)]
    (is (= 1 (:graph_version graph)))
    (is (= [] (:nodes graph)))
    (is (= [] (:edges graph)))
    (is (= model/default-viewport (get-in graph [:ui :viewport])))
    (testing "timestamps are microseconds, as the wire expects"
      (is (pos? (:created_at_us graph)))
      (is (= (:created_at_us graph) (:updated_at_us graph))))))

(deftest node-height-grows-with-port-rows
  (let [one-port {:kind "transform" :input_port_ids ["in1"] :output_port_ids ["out1"]}
        three-in {:kind "combine" :input_port_ids ["in1" "in2" "in3"] :output_port_ids ["out1"]}]
    (is (< (model/node-height one-port) (model/node-height three-in)))
    (testing "a node with no ports still reserves one row"
      (is (= (model/node-height one-port)
             (model/node-height {:kind "sink"}))))
    (testing "an inline viewer chart reserves extra height below the ports"
      (is (= (+ model/inline-graph-height
                (model/node-height {:kind "viewer" :input_port_ids ["in1"]}))
             (model/node-height {:kind "viewer" :input_port_ids ["in1"] :inline_graph true}))))))

(deftest port-position-anchors-to-the-top-of-the-card
  (let [node {:kind "combine"
              :position {:x 100 :y 200}
              :input_port_ids ["in1" "in2"]
              :output_port_ids ["out1"]}
        in1 (model/port-position node "in1" :input)
        in2 (model/port-position node "in2" :input)
        out1 (model/port-position node "out1" :output)]
    (testing "inputs sit on the left edge, outputs a node-width to the right"
      (is (= 100 (:x in1)))
      (is (= (+ 100 model/node-width) (:x out1))))
    (testing "successive input rows step down by one row height"
      (is (= model/port-row-height (- (:y in2) (:y in1)))))
    (testing "an unknown port id clamps to the first row rather than floating off"
      (is (= (:y in1) (:y (model/port-position node "nope" :input)))))
    (testing "adding an inline chart does not move a port (ports anchor to the top)"
      (is (= in1 (model/port-position (assoc node :inline_graph true) "in1" :input))))))

(deftest provenance-ports-are-identified-by-prefix
  (is (true? (model/provenance-port? model/provenance-port-source)))
  (is (true? (model/provenance-port? model/provenance-port-experiment)))
  (is (true? (model/provenance-port? model/provenance-port-models)))
  (is (true? (model/provenance-port? model/provenance-port-model)))
  (testing "an ordinary data port is not provenance"
    (is (false? (model/provenance-port? "in1")))
    (is (false? (model/provenance-port? "data")))
    (is (false? (model/provenance-port? nil)))))

(deftest provenance-edges-are-detected-from-tag-or-endpoints
  (testing "an explicit edge_kind tag"
    (is (true? (model/provenance-edge? {:edge_kind "provenance"
                                        :source_port "out1" :target_port "in1"}))))
  (testing "or a provenance-typed port on either end"
    (is (true? (model/provenance-edge? {:source_port "data"
                                        :target_port model/provenance-port-source})))
    (is (true? (model/provenance-edge? {:source_port model/provenance-port-models
                                        :target_port "in1"}))))
  (testing "a plain data edge is not provenance"
    (is (false? (model/provenance-edge? {:source_port "out1" :target_port "in1"})))))

(deftest default-transform-config-seeds-from-the-catalog-entry
  (let [capability {:config_fields [{:id "low_cutoff_hz" :type "number" :default_value 20}
                                    {:id "iir_method" :type "enum" :default_option "butterworth"}
                                    {:id "no_default" :type "number"}]}]
    (is (= {:low_cutoff_hz 20 :iir_method "butterworth"}
           (model/default-transform-config capability)))
    (testing "a field with no declared default is left unset, not nil-filled"
      (is (not (contains? (model/default-transform-config capability) :no_default))))
    (testing "an entry with no config fields yields an empty map"
      (is (= {} (model/default-transform-config {:config_fields []}))))))

(deftest output-descriptor-resolves-per-node-kind
  (let [streams [{:streamId "s1" :descriptor {:schema_name "SensorV1"} :live false}]]
    (testing "a source node reports its bound stream's descriptor"
      (is (= {:schema_name "SensorV1"}
             (model/output-descriptor {:kind "stream_source" :stream_id "s1"} streams))))
    (testing "an unbound source has none"
      (is (nil? (model/output-descriptor {:kind "stream_source" :stream_id "missing"} streams))))
    (testing "a viewer/sink has no output at all"
      (is (nil? (model/output-descriptor {:kind "viewer"} streams))))))

(deftest transform-output-descriptor-is-a-real-channel-frame
  ;; This mattered in the Svelte original: the transform/combine output used to be
  ;; an empty stub, which broke compatibility checks, input-mapping auto-pick and
  ;; the "recommended next" list. It must probe as a genuine channel frame.
  (testing "a transform's output satisfies the canonical channel-frame contract"
    (is (true? (descriptor/supports-numeric-channel-frames?
                (model/output-descriptor {:kind "transform"} [])))))
  (testing "and so does a combine's"
    (is (true? (descriptor/supports-numeric-channel-frames?
                (model/output-descriptor {:kind "combine"} [])))))
  (testing "so a transform can feed another transform"
    (is (= "canonical_channel_frame"
           (descriptor/compatible-input-mapping-id
            (model/output-descriptor {:kind "transform"} [])
            {:input_mappings [{:id "canonical_channel_frame"
                               :mode "canonical_channel_frame"
                               :required_descriptor_paths []}]})))))

(deftest run-state-class-buckets-states
  (is (= :ok (model/run-state-class "running")))
  (is (= :ok (model/run-state-class "valid")))
  (is (= :error (model/run-state-class "error")))
  (is (= :error (model/run-state-class "stalled")))
  (is (= :muted (model/run-state-class "draft")))
  (is (= :muted (model/run-state-class "stopped")))
  (is (= :muted (model/run-state-class "starting")))
  (is (= :muted (model/run-state-class nil))))
