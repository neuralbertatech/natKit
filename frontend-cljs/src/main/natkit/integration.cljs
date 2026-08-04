(ns natkit.integration
  "Live integration check: boots the REAL socket + events + app-db against a
  running backend, in node, with no browser.

  This is what makes the Phase-0 exit gate meaningful. The unit suite proves the
  pure namespaces; scripts/protocol_smoke.mjs proves the backend contract. This
  proves the actual code path in between — natkit.protocol.socket connects,
  natkit.protocol.socket/message->event routes, natkit.events fills app-db, and
  the derivations in natkit.db resolve on real data.

  Run:  npx shadow-cljs compile integration && node out/integration.js
        NATKIT_WS_URL=ws://host:7409/ws/stream_viewer node out/integration.js"
  (:require [re-frame.core :as rf]
            [natkit.config :as config]
            [natkit.db :as db]
            [natkit.protocol.schema :as schema]
            [natkit.stream.viewer-registry :as registry]
            [natkit.events]
            [natkit.subs]))

(def ^:private timeout-ms 10000)

(defn- report []
  (let [db* @re-frame.db/app-db
        catalog (:node-catalog db*)
        capabilities (db/transform-capabilities catalog)
        options (db/source-stream-options (:streams db*))
        graphs (:graphs db*)
        statuses (:graph-statuses db*)]
    (println "")
    (println "app-db after connect:")
    (println "  connection-state    " (:connection-state db*))
    (println "  node catalog        " (count catalog) "types ·"
             (count capabilities) "transforms ·"
             (count (db/catalog-by-category catalog)) "categories")
    (println "  streams             " (count options) "("
             (count (filterv :descriptor options)) "with a descriptor)")
    (println "  graphs              " (count graphs) "·"
             (count (filterv #(some? (:editor_metadata %)) graphs))
             "carrying editor_metadata")
    (println "  graph statuses      " (count statuses))
    (println "")
    (println "renderer chosen per described stream (descriptor-driven):")
    (doseq [{:keys [streamId schemaName descriptor]} options
            :when descriptor]
      (println (str "  " streamId "  " schemaName
                    "  ->  " (name (registry/choose-renderer descriptor nil schemaName)))))
    (println "")
    (println "run state per graph:")
    (doseq [{:keys [graph_id label nodes]} graphs]
      (let [status (get statuses graph_id)]
        (println (str "  " (or (:run_state status) "draft")
                      "  " label
                      "  (" (count nodes) " nodes"
                      ", " (count (:node_statuses status)) " node statuses)"))))

    ;; --- Assertions ---------------------------------------------------------
    (let [problems
          (cond-> []
            (not= :connected (:connection-state db*))
            (conj "never reached :connected")

            (empty? catalog)
            (conj "node catalog is empty")

            (empty? capabilities)
            (conj "no transform capabilities derived from the catalog")

            (empty? options)
            (conj "no streams discovered")

            ;; Every id-keyed lookup table must be reachable with the raw id.
            ;; This is the codec rule-2 bug, checked against live data.
            (some (fn [[graph-id status]]
                    (or (not (string? graph-id))
                        (not= graph-id (:graph_id status))
                        (some (fn [[node-id _]] (not (string? node-id)))
                              (:node_statuses status))))
                  statuses)
            (conj "a status or node-status key is not the raw string id")

            ;; Every node named by a status must exist in its graph.
            (some (fn [{:keys [graph_id nodes]}]
                    (let [node-ids (into #{} (map :id) nodes)]
                      (some (fn [[node-id _]] (not (contains? node-ids node-id)))
                            (:node_statuses (get statuses graph_id)))))
                  graphs)
            (conj "a node status names a node absent from its graph")

            (some (fn [payload] (schema/explain schema/GraphDefinition payload)) graphs)
            (conj "a live graph failed the GraphDefinition schema"))]
      (println "")
      (if (seq problems)
        (do (println "RESULT: FAIL")
            (doseq [p problems] (println "  -" p))
            (js/process.exit 1))
        (do (println "RESULT: PASS — socket, routing, events and derivations all work live")
            (js/process.exit 0))))))

(defn main [& _]
  (println (str "connecting to " (config/ws-url) " …"))
  (rf/dispatch-sync [:app/boot])
  ;; Give the connect burst time to land, then assert on whatever arrived.
  (js/setTimeout report timeout-ms)
  ;; Fail loudly rather than hanging forever if the socket never opens.
  (js/setTimeout (fn []
                   (println "RESULT: FAIL — timed out with no reply")
                   (js/process.exit 1))
                 (+ timeout-ms 15000)))
