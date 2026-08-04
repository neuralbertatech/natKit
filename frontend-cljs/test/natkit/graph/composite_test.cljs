(ns natkit.graph.composite-test
  "Ported from frontend/src/VisualProgramming/composites.test.ts. These assertions
  are the behavioral contract for graph flattening — the executed graph the
  backend receives must be identical to what the Svelte editor produces."
  (:require [cljs.test :refer-macros [deftest testing is]]
            [natkit.graph.composite :as composite]))

;; --- Fixtures (mirroring the TS helpers) ------------------------------------

(defn source-node
  ([id] (source-node id "stream-a"))
  ([id stream-id]
   {:id id
    :kind "stream_source"
    :label (str "Source " id)
    :position {:x 0 :y 0}
    :stream_id stream-id
    :output_port_ids ["data"]}))

(defn transform-node [id output-id]
  {:id id
   :kind "transform"
   :label (str "Transform " id)
   :position {:x 100 :y 0}
   :transform_kind "rectify"
   :config {}
   :output_identifier output-id
   :input_port_ids ["input"]
   :output_port_ids ["output"]})

(defn viewer-node [id]
  {:id id
   :kind "viewer"
   :label (str "Viewer " id)
   :position {:x 200 :y 0}
   :input_port_ids ["input"]})

(defn edge [id source source-port target target-port]
  {:id id
   :source_node_id source
   :source_port source-port
   :target_node_id target
   :target_port target-port})

(defn base-graph [nodes edges]
  {:graph_version 1
   :graph_id "graph-1"
   :label "Test graph"
   :nodes (vec nodes)
   :edges (vec edges)})

(defn- source-transform-viewer-graph []
  (base-graph
   [(source-node "src") (transform-node "tx" "rectified") (viewer-node "view")]
   [(edge "e1" "src" "data" "tx" "input")
    (edge "e2" "tx" "output" "view" "input")]))

(defn- no-template [_] nil)

;; --- extract-composite-from-selection ---------------------------------------

(deftest extract-derives-boundary-ports-and-replaces-selection
  (testing "grouping the middle transform yields one input, one output, one instance"
    (let [graph (source-transform-viewer-graph)
          {:keys [template instance next-graph]}
          (composite/extract-composite-from-selection graph #{"tx"} "My Filter")]
      (is (some? template))
      (is (= 1 (count (:inputs template))))
      (is (= 1 (count (:outputs template))))
      (is (= 1 (count (:nodes template))))

      ;; The graph now holds source, composite instance, viewer.
      (is (= 3 (count (:nodes next-graph))))
      (is (= 1 (count (filterv composite/composite-instance? (:nodes next-graph)))))

      ;; External edges are rewired onto the instance boundary ports.
      (let [into-instance (some #(when (= (:id instance) (:target_node_id %)) %)
                                (:edges next-graph))
            out-of-instance (some #(when (= (:id instance) (:source_node_id %)) %)
                                  (:edges next-graph))]
        (is (= "src" (:source_node_id into-instance)))
        (is (= (:port_id (first (:inputs template))) (:target_port into-instance)))
        (is (= "view" (:target_node_id out-of-instance)))
        (is (= (:port_id (first (:outputs template))) (:source_port out-of-instance)))))))

(deftest extract-refuses-empty-and-nested-selections
  (testing "an empty selection produces no composite"
    (is (nil? (composite/extract-composite-from-selection
               (source-transform-viewer-graph) #{} "Nope"))))
  (testing "v1 composites may not contain another composite"
    (let [graph (source-transform-viewer-graph)
          {:keys [next-graph instance]}
          (composite/extract-composite-from-selection graph #{"tx"} "Inner")]
      (is (nil? (composite/extract-composite-from-selection
                 next-graph #{(:id instance)} "Outer"))))))

;; --- flatten-graph ----------------------------------------------------------

(deftest flatten-inlines-a-composite-and-rewires-the-boundary
  (let [extracted (composite/extract-composite-from-selection
                   (source-transform-viewer-graph) #{"tx"} "My Filter")
        {:keys [graph diagnostics]} (composite/flatten-graph (:next-graph extracted)
                                                             no-template)]
    (is (empty? diagnostics))
    (testing "no composite nodes survive flattening"
      (is (every? #(contains? #{"stream_source" "transform" "viewer" "sink"} (:kind %))
                  (:nodes graph))))
    (is (= 3 (count (:nodes graph))))

    (testing "the chain is reconnected end-to-end through the expanded transform"
      (let [expanded-tx (some #(when (= "transform" (:kind %)) %) (:nodes graph))
            into-tx (some #(when (= (:id expanded-tx) (:target_node_id %)) %) (:edges graph))
            out-of-tx (some #(when (= (:id expanded-tx) (:source_node_id %)) %) (:edges graph))]
        (is (= "src" (:source_node_id into-tx)))
        (is (= "view" (:target_node_id out-of-tx)))))))

(deftest flatten-gives-distinct-output-identifiers-for-reused-composites
  (let [template {:composite_version 1
                  :composite_id "cmp-1"
                  :label "Rectifier"
                  :nodes [(transform-node "tx" "rectified")]
                  :edges []
                  :inputs [{:port_id "in1" :label "In"
                            :internal_node_id "tx" :internal_port "input"}]
                  :outputs [{:port_id "out1" :label "Out"
                             :internal_node_id "tx" :internal_port "output"}]}
        instance-a {:id "composite/a"
                    :kind "composite"
                    :label "Rectifier A"
                    :position {:x 0 :y 0}
                    :composite_id "cmp-1"
                    :composite_version 1
                    :input_port_ids ["in1"]
                    :output_port_ids ["out1"]
                    :template template}
        instance-b (assoc instance-a
                          :id "composite/b"
                          :label "Rectifier B"
                          :position {:x 400 :y 0})
        {:keys [graph]} (composite/flatten-graph
                         (base-graph [instance-a instance-b] [])
                         no-template)
        transforms (filterv #(= "transform" (:kind %)) (:nodes graph))]
    (is (= 2 (count transforms)))
    (testing "output identifiers are namespaced per instance, so they stay unique"
      (is (= 2 (count (set (map :output_identifier transforms))))))
    (testing "expanded node ids are globally unique too"
      (is (= 2 (count (set (map :id (:nodes graph)))))))))

(deftest flatten-reports-a-missing-template-and-drops-its-edges
  (let [orphan {:id "composite/orphan"
                :kind "composite"
                :label "Orphan"
                :position {:x 0 :y 0}
                :composite_id "missing"
                :composite_version 1
                :input_port_ids ["in1"]
                :output_port_ids ["out1"]}
        graph (base-graph [(source-node "src") orphan]
                          [(edge "e1" "src" "data" "composite/orphan" "in1")])
        {:keys [graph diagnostics]} (composite/flatten-graph graph no-template)]
    (is (some #(= "composite_template_missing" (:code %)) diagnostics))
    (is (= 0 (count (:edges graph))))))

(deftest flatten-resolves-a-template-from-the-library-when-not-embedded
  (testing "an instance with no embedded snapshot falls back to resolve-template"
    (let [template {:composite_version 1
                    :composite_id "cmp-lib"
                    :label "Library rectifier"
                    :nodes [(transform-node "tx" "rectified")]
                    :edges []
                    :inputs []
                    :outputs []}
          instance {:id "composite/lib"
                    :kind "composite"
                    :label "From library"
                    :position {:x 0 :y 0}
                    :composite_id "cmp-lib"
                    :composite_version 1}
          {:keys [graph diagnostics]}
          (composite/flatten-graph (base-graph [instance] [])
                                   (fn [id] (when (= "cmp-lib" id) template)))]
      (is (empty? diagnostics))
      (is (= 1 (count (:nodes graph))))
      (is (= "transform" (:kind (first (:nodes graph))))))))

(deftest flatten-drops-param-nodes-and-their-binding-edges
  (let [param {:id "param/1"
               :kind "param"
               :label "Cutoff"
               :position {:x 0 :y 0}
               :value 30
               :min 0
               :max 100
               :step 1
               :target_node_id "tf"
               :target_field "cutoff_hz"
               :output_port_ids ["value"]}
        graph (base-graph
               [(source-node "src") (transform-node "tf" "tf-out") param]
               [(edge "e1" "src" "data" "tf" "input")
                (edge "e2" "param/1" "value" "tf" "input")])
        {:keys [graph]} (composite/flatten-graph graph no-template)]
    (testing "the param node and its binding edge never reach the backend"
      (is (= ["src" "tf"] (sort (map :id (:nodes graph)))))
      (is (= 1 (count (:edges graph))))
      (is (= "e1" (:id (first (:edges graph))))))))

(deftest flatten-drops-provenance-edges-and-keeps-data-edges
  (let [graph (base-graph
               [(source-node "src") (transform-node "tf" "tf-out")]
               [(edge "data" "src" "data" "tf" "input")
                (assoc (edge "prov" "src" "data" "tf" "prov_model")
                       :edge_kind "provenance")])
        {:keys [graph]} (composite/flatten-graph graph no-template)]
    (is (= 1 (count (:edges graph))))
    (is (= "data" (:id (first (:edges graph)))))))

(deftest flatten-keeps-export-nodes-and-their-data-edges
  (testing "unlike param nodes, export is a real backend kind"
    ;; The control-plane job is submitted client-side, but the node itself must
    ;; reach the backend so it validates, starts and reports status.
    (let [export-node {:id "export/1"
                       :kind "export"
                       :label "Export"
                       :position {:x 0 :y 0}
                       :input_port_ids ["in1" "in2"]
                       :output_port_ids []
                       :config {:format "parquet"
                                :output_name ""
                                :output_dir ""
                                :label_field "label"
                                :include_markers true
                                :overwrite false
                                :run_index nil}}
          graph (base-graph
                 [(source-node "src") (transform-node "tf" "tf-out") export-node]
                 [(edge "e1" "src" "data" "tf" "input")
                  (edge "e2" "tf" "output" "export/1" "in1")])
          {:keys [graph]} (composite/flatten-graph graph no-template)
          flat-export (some #(when (= "export/1" (:id %)) %) (:nodes graph))]
      (is (= ["export/1" "src" "tf"] (sort (map :id (:nodes graph)))))
      (is (= ["e1" "e2"] (sort (map :id (:edges graph)))))
      (is (= "export" (:kind flat-export)))
      (testing "config round-trips verbatim (the backend stores it opaquely)"
        (is (= "label" (get-in flat-export [:config :label_field])))))))

(deftest flatten-leaves-a-plain-primitive-graph-untouched
  (testing "a graph with no composites, params or provenance edges is unchanged"
    (let [original (source-transform-viewer-graph)
          {:keys [graph diagnostics]} (composite/flatten-graph original no-template)]
      (is (empty? diagnostics))
      (is (= (:nodes original) (:nodes graph)))
      (is (= (:edges original) (:edges graph)))
      (testing "graph-level metadata is carried through untouched"
        (is (= (:graph_id original) (:graph_id graph)))
        (is (= (:label original) (:label graph)))))))

;; --- ungroup-instance -------------------------------------------------------

(deftest ungroup-restores-primitives-and-reconnects-the-boundary
  (let [extracted (composite/extract-composite-from-selection
                   (source-transform-viewer-graph) #{"tx"} "My Filter")
        restored (composite/ungroup-instance (:next-graph extracted)
                                             (:id (:instance extracted)))]
    (is (every? #(not= "composite" (:kind %)) (:nodes restored)))
    (is (= 3 (count (:nodes restored))))
    (let [tx (some #(when (= "transform" (:kind %)) %) (:nodes restored))]
      (is (some #(and (= "src" (:source_node_id %)) (= (:id tx) (:target_node_id %)))
                (:edges restored)))
      (is (some #(and (= (:id tx) (:source_node_id %)) (= "view" (:target_node_id %)))
                (:edges restored))))))

(deftest ungroup-is-a-no-op-for-an-unknown-instance
  (let [graph (source-transform-viewer-graph)]
    (is (= graph (composite/ungroup-instance graph "composite/nope")))))

;; --- instantiate ------------------------------------------------------------

(deftest instantiate-derives-ports-from-the-template
  (let [template {:composite_version 1
                  :composite_id "cmp-1"
                  :label "My Filter"
                  :nodes [(transform-node "tx" "rectified")]
                  :edges []
                  :inputs [{:port_id "in1" :label "In"
                            :internal_node_id "tx" :internal_port "input"}]
                  :outputs [{:port_id "out1" :label "Out"
                             :internal_node_id "tx" :internal_port "output"}]}
        instance (composite/instantiate-composite template {:x 40 :y 50})]
    (is (= "composite" (:kind instance)))
    (is (= ["in1"] (:input_port_ids instance)))
    (is (= ["out1"] (:output_port_ids instance)))
    (is (= {:x 40 :y 50} (:position instance)))
    (testing "the template snapshot is embedded so the graph is self-contained"
      (is (= template (:template instance))))))

;; --- validation -------------------------------------------------------------

(deftest validate-flags-dangling-boundaries-and-empty-composites
  (testing "a boundary port pointing at a missing internal node is an error"
    (let [diagnostics (composite/validate-composite-template
                       {:composite_version 1
                        :composite_id "cmp-1"
                        :label "Broken"
                        :nodes [(transform-node "tx" "out")]
                        :edges []
                        :inputs [{:port_id "in1" :label "In"
                                  :internal_node_id "gone" :internal_port "input"}]
                        :outputs []})]
      (is (some #(= "composite_dangling_boundary" (:code %)) diagnostics))))
  (testing "an empty composite is an error"
    (is (some #(= "composite_empty" (:code %))
              (composite/validate-composite-template
               {:composite_version 1 :composite_id "c" :label "Empty"
                :nodes [] :edges [] :inputs [] :outputs []}))))
  (testing "a well-formed template is clean"
    (is (empty? (composite/validate-composite-template
                 {:composite_version 1 :composite_id "c" :label "Fine"
                  :nodes [(transform-node "tx" "out")]
                  :edges []
                  :inputs [{:port_id "in1" :label "In"
                            :internal_node_id "tx" :internal_port "input"}]
                  :outputs []})))))

;; --- export / import --------------------------------------------------------

(deftest export-import-round-trips-templates
  (let [template {:composite_version 1
                  :composite_id "cmp-1"
                  :label "Rectifier"
                  :nodes [(transform-node "tx" "rectified")]
                  :edges []
                  :inputs []
                  :outputs []}
        text (js/JSON.stringify
              (clj->js (composite/serialize-composite-export [template])))
        {:keys [templates errors]} (composite/parse-composite-export-file text)]
    (is (empty? errors))
    (is (= 1 (count templates)))
    (is (= "cmp-1" (:composite_id (first templates))))
    (testing "the template survives the JSON round trip intact"
      (is (= template (first templates))))))

(deftest export-import-rejects-a-wrong-file-type
  (let [{:keys [templates errors]}
        (composite/parse-composite-export-file
         (js/JSON.stringify (clj->js {:file_type "something-else"})))]
    (is (= 0 (count templates)))
    (is (pos? (count errors)))))

(deftest export-import-rejects-an-unsupported-version
  (let [{:keys [templates errors]}
        (composite/parse-composite-export-file
         (js/JSON.stringify (clj->js {:file_type "natkit.composite"
                                      :file_version 99
                                      :templates []})))]
    (is (= 0 (count templates)))
    (is (pos? (count errors)))))

(deftest export-import-reports-invalid-json
  (is (pos? (count (:errors (composite/parse-composite-export-file "{not json"))))))

(deftest export-import-skips-a-malformed-template-but-keeps-the-rest
  (let [good {:composite_version 1 :composite_id "ok" :label "Good"
              :nodes [] :edges [] :inputs [] :outputs []}
        text (js/JSON.stringify
              (clj->js {:file_type "natkit.composite"
                        :file_version 1
                        :templates [good {:label "no id"}]}))
        {:keys [templates errors]} (composite/parse-composite-export-file text)]
    (is (= 1 (count templates)))
    (is (= "ok" (:composite_id (first templates))))
    (is (= 1 (count errors)))))
