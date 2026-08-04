(ns natkit.graph.composite
  "Composite (\"higher-order\") nodes and graph flattening.

  Port of frontend/src/VisualProgramming/composites.ts.

  A composite is a reusable, function-like group of primitive graph nodes, and it
  is a FRONTEND-ONLY authoring concept: the backend understands only its own node
  kinds and rejects anything else. Before a graph is saved / validated / run,
  every composite instance is inlined into namespaced primitive nodes by
  `flatten-graph`, so the backend never sees a composite.

  Two other editor-only things are dropped by flattening:
    - param nodes — their value is already written into the target transform's
      config, so the executed graph is unchanged by their absence;
    - provenance edges — they resolve node configuration at author/submit time,
      not at runtime.

  Everything here is pure. Note that `deepClone` from the TS has no equivalent:
  ClojureScript data is already immutable, so ~a dozen defensive clones simply
  disappear."
  (:require [natkit.graph.model :as model]))

;; --- Ids --------------------------------------------------------------------

(defonce ^:private id-counter (atom 0))

(defn- unique-suffix []
  (let [n (swap! id-counter inc)]
    (str (.toString (js/Date.now) 36) "-" (.toString n 36))))

(defn create-composite-id []
  (str "composite-" (unique-suffix)))

(defn composite-instance?
  [node]
  (= "composite" (:kind node)))

(defn param-node?
  [node]
  (= "param" (:kind node)))

(defn namespace-id
  "Deterministic, collision-free prefixing of an inner id with its instance id."
  [instance-id inner-id]
  (str instance-id "::" inner-id))

(defn namespace-output-identifier
  "Unique, backend-safe transform output identifier for an expanded inner node."
  [instance-id inner]
  (model/sanitize-identifier (str instance-id "-" inner)))

(defn instance-ports-from-template
  [template]
  {:input_port_ids (mapv :port_id (:inputs template))
   :output_port_ids (mapv :port_id (:outputs template))})

;; --- Expansion --------------------------------------------------------------

(defn expand-instance
  "Expand one instance into namespaced primitive nodes + edges.
  Returns {:nodes [...] :edges [...] :id-map {inner-id -> namespaced-id}}."
  [instance template]
  (let [id-map (into {} (map (fn [node]
                               [(:id node) (namespace-id (:id instance) (:id node))])
                             (:nodes template)))
        instance-pos (:position instance)
        nodes (mapv (fn [node]
                      (cond-> (assoc node
                                     :id (get id-map (:id node))
                                     :position {:x (+ (:x instance-pos) (get-in node [:position :x]))
                                                :y (+ (:y instance-pos) (get-in node [:position :y]))})
                        (contains? #{"transform" "combine"} (:kind node))
                        (-> (assoc :output_identifier
                                   (namespace-output-identifier
                                    (:id instance)
                                    (or (:output_identifier node) (:id node))))
                            ;; The expanded node's runtime stream id is derived
                            ;; from its new output_identifier by the backend.
                            (dissoc :output_stream_id))))
                    (:nodes template))
        ;; NOTE (faithful port): the TS builds a fresh 5-key edge object here, so
        ;; an inner edge's `hidden_topic_types` / `edge_kind` are intentionally
        ;; NOT carried through. v1 composites contain only primitive data edges.
        edges (mapv (fn [edge]
                      {:id (namespace-id (:id instance) (:id edge))
                       :source_node_id (or (get id-map (:source_node_id edge))
                                           (:source_node_id edge))
                       :source_port (:source_port edge)
                       :target_node_id (or (get id-map (:target_node_id edge))
                                           (:target_node_id edge))
                       :target_port (:target_port edge)})
                    (:edges template))]
    {:nodes nodes :edges edges :id-map id-map}))

(defn- rewire-edge
  "Rewrite the endpoint(s) of an outer edge that reference a composite instance
  so they point at the bound internal pin.

  `boundary` maps instance-id -> {:template t :id-map m}. Returns
  {:edge e-or-nil :diagnostics [...]}; a nil :edge means the edge is dropped
  because a referenced boundary port has no binding."
  [edge boundary]
  (let [source-entry (get boundary (:source_node_id edge))
        target-entry (get boundary (:target_node_id edge))
        source-decl (when source-entry
                      (some #(when (= (:port_id %) (:source_port edge)) %)
                            (get-in source-entry [:template :outputs])))
        target-decl (when target-entry
                      (some #(when (= (:port_id %) (:target_port edge)) %)
                            (get-in target-entry [:template :inputs])))]
    (cond
      (and source-entry (nil? source-decl))
      {:edge nil
       :diagnostics [{:severity "error"
                      :code "composite_unbound_output"
                      :message (str "Composite output port '" (:source_port edge)
                                    "' has no binding.")}]}

      (and target-entry (nil? target-decl))
      {:edge nil
       :diagnostics [{:severity "error"
                      :code "composite_unbound_input"
                      :message (str "Composite input port '" (:target_port edge)
                                    "' has no binding.")}]}

      :else
      {:edge (cond-> edge
               source-decl
               (assoc :source_node_id (or (get (:id-map source-entry)
                                               (:internal_node_id source-decl))
                                          (:internal_node_id source-decl))
                      :source_port (:internal_port source-decl))
               target-decl
               (assoc :target_node_id (or (get (:id-map target-entry)
                                               (:internal_node_id target-decl))
                                          (:internal_node_id target-decl))
                      :target_port (:internal_port target-decl)))
       :diagnostics []})))

(defn flatten-graph
  "Inline every composite instance into primitives, producing a backend-safe
  graph. `resolve-template` is (fn [composite-id] template-or-nil), consulted
  only when an instance carries no embedded template snapshot.

  Returns {:graph g :diagnostics [...]}."
  [graph resolve-template]
  (let [;; Pass 1 — partition nodes, expanding composites as we go.
        {:keys [primitive-nodes inner-edges boundary missing-instances
                param-node-ids diagnostics]}
        (reduce
         (fn [acc node]
           (cond
             ;; Editor-only control node — dropped from the executed graph.
             (param-node? node)
             (update acc :param-node-ids conj (:id node))

             (not (composite-instance? node))
             (update acc :primitive-nodes conj node)

             :else
             (if-let [template (or (:template node)
                                   (resolve-template (:composite_id node)))]
               (let [expanded (expand-instance node template)
                     drift? (and (:template node)
                                 (not= (:composite_version node)
                                       (:composite_version template)))]
                 (cond-> acc
                   drift?
                   (update :diagnostics conj
                           {:severity "warning"
                            :code "composite_version_drift"
                            :message (str "Composite '" (:label node)
                                          "' version differs from its template.")})
                   true
                   (-> (update :primitive-nodes into (:nodes expanded))
                       (update :inner-edges into (:edges expanded))
                       (assoc-in [:boundary (:id node)]
                                 {:template template :id-map (:id-map expanded)}))))
               (-> acc
                   (update :missing-instances conj (:id node))
                   (update :diagnostics conj
                           {:severity "error"
                            :code "composite_template_missing"
                            :message (str "Composite '" (:label node)
                                          "' has no available template definition.")})))))
         {:primitive-nodes []
          :inner-edges []
          :boundary {}
          :missing-instances #{}
          :param-node-ids #{}
          :diagnostics []}
         (:nodes graph))

        ;; Pass 2 — rewire the outer edges through any composite boundaries.
        {:keys [outer-edges edge-diagnostics]}
        (reduce
         (fn [acc edge]
           (if (or (contains? missing-instances (:source_node_id edge))
                   (contains? missing-instances (:target_node_id edge))
                   (contains? param-node-ids (:source_node_id edge))
                   (contains? param-node-ids (:target_node_id edge))
                   ;; Provenance edges resolve config at author time, not runtime.
                   (= "provenance" (:edge_kind edge)))
             acc
             (let [{:keys [edge diagnostics]} (rewire-edge edge boundary)]
               (cond-> (update acc :edge-diagnostics into diagnostics)
                 edge (update :outer-edges conj edge)))))
         {:outer-edges [] :edge-diagnostics []}
         (:edges graph))]
    {:graph (assoc graph
                   :nodes primitive-nodes
                   :edges (into outer-edges inner-edges))
     :diagnostics (into diagnostics edge-diagnostics)}))

;; --- Authoring --------------------------------------------------------------

(defn- centroid
  [nodes]
  (if (empty? nodes)
    {:x 0 :y 0}
    (let [sum (reduce (fn [acc node]
                        {:x (+ (:x acc) (get-in node [:position :x]))
                         :y (+ (:y acc) (get-in node [:position :y]))})
                      {:x 0 :y 0}
                      nodes)
          n (count nodes)]
      {:x (js/Math.round (/ (:x sum) n))
       :y (js/Math.round (/ (:y sum) n))})))

(defn- boundary-decls
  "Derive the composite's external ports from the edges that cross the selection
  boundary, deduped by (node, port) and numbered in edge order."
  [edges selected-ids]
  (reduce
   (fn [{:keys [inputs outputs input-keys output-keys] :as acc} edge]
     (let [source-inside? (contains? selected-ids (:source_node_id edge))
           target-inside? (contains? selected-ids (:target_node_id edge))
           in-key (str (:target_node_id edge) ":" (:target_port edge))
           out-key (str (:source_node_id edge) ":" (:source_port edge))]
       (cond-> acc
         (and target-inside? (not source-inside?) (not (contains? input-keys in-key)))
         (-> (update :inputs conj {:port_id (str "in" (inc (count inputs)))
                                   :label (str "Input " (inc (count inputs)))
                                   :internal_node_id (:target_node_id edge)
                                   :internal_port (:target_port edge)})
             (update :input-keys conj in-key))

         (and source-inside? (not target-inside?) (not (contains? output-keys out-key)))
         (-> (update :outputs conj {:port_id (str "out" (inc (count outputs)))
                                    :label (str "Output " (inc (count outputs)))
                                    :internal_node_id (:source_node_id edge)
                                    :internal_port (:source_port edge)})
             (update :output-keys conj out-key)))))
   {:inputs [] :outputs [] :input-keys #{} :output-keys #{}}
   edges))

(defn extract-composite-from-selection
  "Group the selected nodes into a new composite template + one instance node.
  Returns {:template t :instance i :next-graph g}, or nil when the selection is
  empty or already contains a composite (v1: composites may not nest)."
  [graph selected-ids label]
  (let [selected (filterv #(contains? selected-ids (:id %)) (:nodes graph))]
    (when (and (seq selected)
               (not (some composite-instance? selected)))
      (let [internal-edge? (fn [edge]
                             (and (contains? selected-ids (:source_node_id edge))
                                  (contains? selected-ids (:target_node_id edge))))
            internal-edges (filterv internal-edge? (:edges graph))
            {:keys [inputs outputs]} (boundary-decls (:edges graph) selected-ids)

            ;; Normalize template positions to the selection's bounding-box origin.
            min-x (apply min (map #(get-in % [:position :x]) selected))
            min-y (apply min (map #(get-in % [:position :y]) selected))
            template-nodes (mapv (fn [node]
                                   (update node :position
                                           (fn [{:keys [x y]}]
                                             {:x (- x min-x) :y (- y min-y)})))
                                 selected)

            now-us (* 1000 (js/Date.now))
            template {:composite_version 1
                      :composite_id (create-composite-id)
                      :label label
                      :description ""
                      :created_at_us now-us
                      :updated_at_us now-us
                      :nodes template-nodes
                      :edges internal-edges
                      :inputs inputs
                      :outputs outputs}

            ports (instance-ports-from-template template)
            instance (merge {:id (str "composite/"
                                      (or (not-empty (model/sanitize-identifier label)) "group")
                                      "-" (unique-suffix))
                             :kind "composite"
                             :label label
                             :position (centroid selected)
                             :composite_id (:composite_id template)
                             :composite_version 1
                             :template template}
                            ports)

            ;; Reindex external edges onto the instance boundary; drop internals.
            decl-for-internal-input (into {} (map (fn [d]
                                                    [(str (:internal_node_id d) ":" (:internal_port d)) d])
                                                  inputs))
            decl-for-internal-output (into {} (map (fn [d]
                                                     [(str (:internal_node_id d) ":" (:internal_port d)) d])
                                                   outputs))
            next-edges
            (reduce
             (fn [acc edge]
               (let [source-inside? (contains? selected-ids (:source_node_id edge))
                     target-inside? (contains? selected-ids (:target_node_id edge))]
                 (cond
                   (internal-edge? edge) acc

                   (and (not source-inside?) (not target-inside?))
                   (conj acc edge)

                   :else
                   (let [source-decl (when source-inside?
                                       (get decl-for-internal-output
                                            (str (:source_node_id edge) ":" (:source_port edge))))
                         target-decl (when target-inside?
                                       (get decl-for-internal-input
                                            (str (:target_node_id edge) ":" (:target_port edge))))]
                     ;; A crossing edge whose pin was not promoted to a boundary
                     ;; port cannot be represented — drop it (as the TS does).
                     (if (or (and source-inside? (nil? source-decl))
                             (and target-inside? (nil? target-decl)))
                       acc
                       (conj acc (cond-> edge
                                   source-decl (assoc :source_node_id (:id instance)
                                                      :source_port (:port_id source-decl))
                                   target-decl (assoc :target_node_id (:id instance)
                                                      :target_port (:port_id target-decl)))))))))
             []
             (:edges graph))

            next-nodes (conj (filterv #(not (contains? selected-ids (:id %))) (:nodes graph))
                             instance)]
        {:template template
         :instance instance
         :next-graph (assoc graph :nodes next-nodes :edges next-edges)}))))

(defn ungroup-instance
  "Inline one composite instance back into editor primitives, leaving any other
  composites alone. A no-op when the instance is missing or carries no embedded
  template."
  [graph instance-id]
  (let [instance (some (fn [node]
                         (when (and (= instance-id (:id node))
                                    (composite-instance? node))
                           node))
                       (:nodes graph))
        template (:template instance)]
    (if-not (and instance template)
      graph
      (let [expanded (expand-instance instance template)
            boundary {(:id instance) {:template template :id-map (:id-map expanded)}}
            outer-edges (reduce (fn [acc edge]
                                  (if-let [rewired (:edge (rewire-edge edge boundary))]
                                    (conj acc rewired)
                                    acc))
                                []
                                (:edges graph))
            next-nodes (into (filterv #(not= instance-id (:id %)) (:nodes graph))
                             (:nodes expanded))]
        (assoc graph
               :nodes next-nodes
               :edges (into outer-edges (:edges expanded)))))))

(defn instantiate-composite
  "Place a library template on the canvas as a fresh instance node."
  [template position]
  (merge {:id (str "composite/"
                   (or (not-empty (model/sanitize-identifier (:label template))) "composite")
                   "-" (unique-suffix))
          :kind "composite"
          :label (:label template)
          :position position
          :composite_id (:composite_id template)
          :composite_version (:composite_version template)
          :template template}
         (instance-ports-from-template template)))

;; --- Validation + export/import --------------------------------------------

(defn validate-composite-template
  [template]
  (let [node-ids (into #{} (map :id (:nodes template)))
        dangling (for [decl (concat (:inputs template) (:outputs template))
                       :when (not (contains? node-ids (:internal_node_id decl)))]
                   {:severity "error"
                    :code "composite_dangling_boundary"
                    :message (str "Boundary port '" (:port_id decl)
                                  "' references a missing internal node.")})]
    (cond-> (vec dangling)
      (empty? (:nodes template))
      (conj {:severity "error"
             :code "composite_empty"
             :message "Composite has no internal nodes."}))))

(def export-file-type "natkit.composite")

(defn serialize-composite-export
  [templates]
  {:file_type export-file-type
   :file_version 1
   :exported_at_us (* 1000 (js/Date.now))
   :templates (vec templates)})

(defn- well-formed-template?
  [candidate]
  (and (map? candidate)
       (string? (:composite_id candidate))
       (sequential? (:nodes candidate))
       (sequential? (:edges candidate))
       (sequential? (:inputs candidate))
       (sequential? (:outputs candidate))))

(defn parse-composite-export-file
  "Parse an exported composite file. Returns {:templates [...] :errors [...]};
  malformed templates are skipped individually rather than failing the file."
  [text]
  (let [parsed (try
                 (js->clj (js/JSON.parse text) :keywordize-keys true)
                 (catch :default _ ::invalid))]
    (cond
      (= ::invalid parsed)
      {:templates [] :errors ["File is not valid JSON."]}

      (not= export-file-type (:file_type parsed))
      {:templates [] :errors ["Not a natKit composite file (missing file_type)."]}

      (not= 1 (:file_version parsed))
      {:templates []
       :errors [(str "Unsupported composite file version: " (:file_version parsed) ".")]}

      (not (sequential? (:templates parsed)))
      {:templates [] :errors ["Composite file has no templates array."]}

      :else
      (reduce (fn [acc candidate]
                (if (well-formed-template? candidate)
                  (update acc :templates conj candidate)
                  (update acc :errors conj "Skipped a malformed composite template.")))
              {:templates [] :errors []}
              (:templates parsed)))))
