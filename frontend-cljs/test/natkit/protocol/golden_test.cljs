(ns natkit.protocol.golden-test
  "Validates the codec, the malli schemas and the app-db derivations against REAL
  payloads captured from a live backend.

  Capture them with:  node scripts/protocol_smoke.mjs --capture

  Synthetic fixtures prove the code does what I think it does; these prove the
  code does what the BACKEND actually does. Same technique already used in this
  repo for the C-ABI golden vectors and the marker-ABI real-payload tests."
  (:require [cljs.test :refer-macros [deftest testing is]]
            [natkit.db :as db]
            [natkit.graph.model :as model]
            [natkit.protocol.schema :as schema]
            [natkit.protocol.socket :as socket]
            [natkit.protocol.wire :as wire]
            [natkit.stream.descriptor :as descriptor]
            [natkit.stream.viewer-registry :as registry]))

(def ^:private fs (js/require "fs"))

(defn- load-golden
  "Read a captured payload, or nil when it has not been captured on this machine.
  Tests skip rather than fail when absent, so the suite still runs with no
  backend — but they DO run in CI once the resources are committed."
  [filename]
  (let [path (str "test/resources/" filename)]
    (when (.existsSync fs path)
      (wire/parse (.readFileSync fs path "utf8")))))

(def stream-list (load-golden "stream_list.json"))
(def node-catalog (load-golden "node_catalog.json"))
(def graph-list (load-golden "stream_graph_list.json"))
(def profile-list (load-golden "profile_list.json"))

(deftest golden-payloads-are-present
  (testing "capture them with: node scripts/protocol_smoke.mjs --capture"
    (is (some? stream-list) "test/resources/stream_list.json missing")
    (is (some? node-catalog) "test/resources/node_catalog.json missing")
    (is (some? graph-list) "test/resources/stream_graph_list.json missing")))

;; --- Codec ------------------------------------------------------------------

(deftest real-payloads-round-trip-through-the-codec
  (testing "every captured message survives encode -> parse unchanged"
    (doseq [[label payload] [["stream_list" stream-list]
                             ["node_catalog" node-catalog]
                             ["stream_graph_list" graph-list]
                             ["profile_list" profile-list]]
            :when payload]
      (is (wire/round-trips? payload) (str label " did not round-trip")))))

(deftest real-editor-metadata-round-trips
  (when graph-list
    (let [with-metadata (filterv #(some? (:editor_metadata %)) (:graphs graph-list))]
      (testing "the live backend really does return editor_metadata"
        ;; Every graph on the dev stack carries one, so this invariant is
        ;; load-bearing rather than theoretical.
        (is (pos? (count with-metadata))))
      (testing "each opaque editor tree is identical after a codec round trip"
        (doseq [graph with-metadata]
          (is (= (:editor_metadata graph)
                 (:editor_metadata (wire/parse (wire/encode graph))))
              (str "editor_metadata corrupted for " (:graph_id graph))))))))

;; --- Schemas ----------------------------------------------------------------

(deftest real-payloads-satisfy-their-schemas
  (doseq [[type payload] [["stream_list" stream-list]
                          ["node_catalog" node-catalog]
                          ["stream_graph_list" graph-list]
                          ["profile_list" profile-list]]
          :when payload]
    (testing type
      (is (nil? (schema/explain (get schema/message-schemas type) payload))))))

;; --- Node catalog -----------------------------------------------------------

(deftest the-live-catalog-advertises-the-structural-kinds
  (when node-catalog
    (let [kinds (into #{} (map :kind) (:nodes node-catalog))]
      (testing "the kinds the editor must be able to place"
        (doseq [kind ["stream_source" "transform" "viewer" "sink" "combine"
                      "experiment" "train"]]
          (is (contains? kinds kind) (str "catalog is missing kind " kind))))
      (testing "and it advertises real transforms"
        (is (<= 10 (count (filterv #(= "transform" (:kind %)) (:nodes node-catalog)))))))))

(deftest transform-capabilities-derive-from-the-live-catalog
  (when node-catalog
    (let [capabilities (db/transform-capabilities (:nodes node-catalog))]
      (is (seq capabilities))
      (testing "every derived capability has what the compat checks need"
        (doseq [capability capabilities]
          (is (string? (:kind capability)))
          (is (sequential? (:input_mappings capability)))
          (is (string? (:output_schema_name capability)))
          (is (sequential? (:config_fields capability)))))
      (testing "a transform output can feed another transform"
        ;; The canonical channel frame a transform emits must satisfy at least one
        ;; real catalog transform's input mapping, or chaining is impossible.
        (is (some (fn [capability]
                    (descriptor/compatible-input-mapping-id
                     model/canonical-channel-frame-descriptor
                     capability))
                  capabilities))))))

(deftest default-config-seeds-from-every-live-catalog-entry
  (when node-catalog
    (testing "seeding a node's config from the live catalog never loses a default"
      (doseq [entry (:nodes node-catalog)]
        (let [config (model/default-transform-config entry)]
          (doseq [{:keys [id default_value default_option]} (:config_fields entry)]
            (cond
              (some? default_value)
              (is (= default_value (get config (keyword id)))
                  (str (:node_type entry) "/" id " lost its default_value"))
              (some? default_option)
              (is (= default_option (get config (keyword id)))
                  (str (:node_type entry) "/" id " lost its default_option"))
              :else
              (is (not (contains? config (keyword id)))
                  (str (:node_type entry) "/" id " was nil-filled")))))))
    (testing "a STRING default_value is preserved"
      ;; The Svelte frontend's TypeScript declares `default_value?: number`, but
      ;; the live backend sends a string default for a string-typed field —
      ;; channel_select's `selection` defaults to "mav". Validating the malli
      ;; schema against a captured catalog is what surfaced this.
      (let [string-defaults (for [entry (:nodes node-catalog)
                                  field (:config_fields entry)
                                  :when (string? (:default_value field))]
                              [(:node_type entry) (:id field) (:default_value field)])]
        (doseq [[node-type field-id expected] string-defaults]
          (let [entry (some #(when (= node-type (:node_type %)) %) (:nodes node-catalog))]
            (is (= expected (get (model/default-transform-config entry) (keyword field-id))))))))))

(deftest live-catalog-groups-into-palette-categories
  (when node-catalog
    (let [grouped (db/catalog-by-category (:nodes node-catalog))]
      (is (seq grouped))
      (testing "every entry lands in exactly one category"
        (is (= (count (:nodes node-catalog))
               (reduce + (map (comp count val) grouped))))))))

;; --- Streams ----------------------------------------------------------------

(deftest live-streams-become-source-options
  (when stream-list
    (let [options (db/source-stream-options (:streams stream-list))]
      (is (seq options))
      (testing "stream ids stay strings — they are stringified uint64"
        (doseq [option options]
          (is (string? (:streamId option)))))
      (testing "options are sorted, so the palette is stable across reloads"
        (is (= options (vec (sort-by :streamId options)))))
      (testing "no stream is dropped for lacking a descriptor"
        ;; Gating this list on transform capability used to hide non-channel-frame
        ;; sensors (like the IMU) from the palette entirely.
        (is (= (count (:streams stream-list)) (count options)))))))

(deftest every-described-live-stream-resolves-to-a-renderer
  (when stream-list
    (let [options (db/source-stream-options (:streams stream-list))
          described (filterv :descriptor options)]
      (is (pos? (count described)) "expected at least one stream with a descriptor")
      (doseq [{:keys [descriptor schemaName]} described]
        (let [renderer (registry/choose-renderer descriptor nil schemaName)]
          (testing (str schemaName " resolves to a known renderer")
            (is (contains? #{:marker :muse :imu :classification :feature_vector
                             :channel_frame :inspector}
                           renderer))))))))

;; --- Graphs -----------------------------------------------------------------

(deftest live-graphs-have-resolvable-topology
  (when graph-list
    (doseq [graph (:graphs graph-list)]
      (let [node-ids (into #{} (map :id) (:nodes graph))]
        (testing (str (:graph_id graph) " edges reference existing nodes")
          (doseq [edge (:edges graph)]
            (is (contains? node-ids (:source_node_id edge))
                (str "dangling source in " (:graph_id graph) ": " (:id edge)))
            (is (contains? node-ids (:target_node_id edge))
                (str "dangling target in " (:graph_id graph) ": " (:id edge)))))))))

(deftest live-graph-statuses-key-by-graph-id
  (when graph-list
    (let [graph-ids (into #{} (map :graph_id) (:graphs graph-list))]
      (doseq [[status-key status] (:statuses graph-list)]
        (testing "a status' own graph_id agrees with its map key"
          (is (= (name status-key) (:graph_id status))))
        (testing "and names a graph that exists"
          (is (contains? graph-ids (:graph_id status))))))))

;; --- Inbound routing --------------------------------------------------------

(deftest every-captured-message-type-routes-to-an-event
  (doseq [payload [stream-list node-catalog graph-list profile-list]
          :when payload]
    (let [event (socket/message->event payload)]
      (is (not= :protocol/unknown-message (first event))
          (str "no route for " (wire/message-type payload)))
      (testing "the message rides along as the event payload"
        (is (= payload (second event)))))))

(deftest an-unknown-message-type-is-surfaced-not-dropped
  (is (= :protocol/unknown-message
         (first (socket/message->event {:type "some_future_message"})))))
