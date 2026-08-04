(ns natkit.subs
  "Subscriptions. Layer-2 extractors read app-db; layer-3 computations delegate to
  the pure namespaces so nothing about a derivation is locked inside a sub."
  (:require [re-frame.core :as rf]
            [natkit.db :as db]))

;; --- Connection -------------------------------------------------------------

(rf/reg-sub :connection-state :-> :connection-state)
(rf/reg-sub :reconnect :-> :reconnect)
(rf/reg-sub :toasts :-> :toasts)

(rf/reg-sub :connected?
  :<- [:connection-state]
  (fn [state _] (= :connected state)))

;; --- Discovery --------------------------------------------------------------

(rf/reg-sub :streams :-> :streams)
(rf/reg-sub :node-catalog :-> :node-catalog)
(rf/reg-sub :graphs :-> :graphs)
(rf/reg-sub :graph-statuses :-> :graph-statuses)
(rf/reg-sub :profiles :-> :profiles)
(rf/reg-sub :live :-> :live)

(rf/reg-sub :source-stream-options
  :<- [:streams]
  (fn [streams _] (db/source-stream-options streams)))

;; The palette and every transform inspector render from this. Derived from the
;; catalog, never fetched separately.
(rf/reg-sub :transform-capabilities
  :<- [:node-catalog]
  (fn [catalog _] (db/transform-capabilities catalog)))

(rf/reg-sub :catalog-by-category
  :<- [:node-catalog]
  (fn [catalog _] (db/catalog-by-category catalog)))

(rf/reg-sub :catalog-entry
  :<- [:node-catalog]
  (fn [catalog [_ node-type]] (db/catalog-entry catalog node-type)))

;; --- Graphs -----------------------------------------------------------------

(rf/reg-sub :selected-graph-id :-> :selected-graph-id)
(rf/reg-sub :draft-graph :-> :draft-graph)
(rf/reg-sub :draft-dirty? :-> :draft-dirty?)
(rf/reg-sub :selection :-> :selection)
(rf/reg-sub :interaction :-> :interaction)
(rf/reg-sub :panels :-> :panels)
(rf/reg-sub :diagnostics :-> :diagnostics)

(rf/reg-sub :graph-status
  :<- [:graph-statuses]
  (fn [statuses [_ graph-id]] (get statuses graph-id)))

(rf/reg-sub :selected-graph-status
  :<- [:graph-statuses]
  :<- [:selected-graph-id]
  (fn [[statuses graph-id] _] (get statuses graph-id)))

(rf/reg-sub :selected-graph-running?
  :<- [:selected-graph-status]
  (fn [status _] (= "running" (:run_state status))))

(rf/reg-sub :node-runtime-status
  :<- [:selected-graph-status]
  (fn [status [_ node-id]]
    (get-in status [:node_statuses node-id])))

(rf/reg-sub :selected-node
  (fn [db _] (db/selected-node db)))

;; --- ML ---------------------------------------------------------------------

(rf/reg-sub :ml :-> :ml)

(rf/reg-sub :train-job
  :<- [:ml]
  (fn [ml _] (:train-job ml)))

(rf/reg-sub :thread-slots
  :<- [:ml]
  (fn [ml _] (:thread-slots ml)))

(rf/reg-sub :recorded-runs
  :<- [:ml]
  (fn [ml _] (:recorded-runs ml)))
