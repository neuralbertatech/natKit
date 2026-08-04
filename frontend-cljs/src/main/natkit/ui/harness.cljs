(ns natkit.ui.harness
  "The Phase-0 connection harness — NOT the Phase-2 canvas.

  Its whole job is to make the protocol layer observable: is the socket up, did
  the catalog arrive, what streams and graphs does the backend actually report,
  and what runtime state are they in. It is the thing that proves the auth cookie
  reaches the socket and that the codec round-trips real payloads. Phase 2
  replaces it with the real shell + canvas."
  (:require [clojure.string :as str]
            [re-frame.core :as rf]))

(defn- connection-pill []
  (let [state @(rf/subscribe [:connection-state])
        {:keys [attempt abandoned?]} @(rf/subscribe [:reconnect])]
    [:span {:style {:display "inline-flex" :align-items "center" :gap "8px"}}
     [:span {:class (str "dot " (case state
                                 :connected "live"
                                 :connecting "warn"
                                 (if abandoned? "error" "muted")))}]
     [:span.mono (name state)]
     (when (and (pos? attempt) (not= :connected state))
       [:span.mono.muted (str "retry " attempt)])]))

(defn- section [title & children]
  (into [:div.panel {:style {:padding "14px 16px" :marginBottom "12px"}}
         [:div {:style {:display "flex" :justifyContent "space-between"
                        :alignItems "baseline" :marginBottom "10px"}}
          [:strong title]]]
        children))

(defn- streams-section []
  (let [options @(rf/subscribe [:source-stream-options])
        live @(rf/subscribe [:live])]
    (section (str "Streams (" (count options) ")")
             (if (empty? options)
               [:div.muted "No streams discovered yet."]
               (into [:div]
                     (for [{:keys [streamId schemaName descriptor]} options]
                       ^{:key streamId}
                       [:div.panel-inset {:style {:padding "8px 10px" :marginBottom "6px"}}
                        [:div.mono streamId]
                        [:div.mono.muted {:style {:fontSize "12px"}}
                         schemaName
                         (when-not descriptor " · no descriptor")
                         (when-let [frames (get-in live [streamId :frames])]
                           (str " · " frames " frames"))]
                        [:button
                         {:style {:marginTop "6px" :fontSize "12px"}
                          :on-click #(rf/dispatch [:stream/subscribe streamId])}
                         "subscribe"]
                        [:button
                         {:style {:marginTop "6px" :marginLeft "6px" :fontSize "12px"}
                          :on-click #(rf/dispatch [:stream/unsubscribe streamId])}
                         "unsubscribe"]]))))))

(defn- catalog-section []
  (let [by-category @(rf/subscribe [:catalog-by-category])
        catalog @(rf/subscribe [:node-catalog])
        capabilities @(rf/subscribe [:transform-capabilities])]
    (section (str "Node catalog (" (count catalog) " types, "
                  (count capabilities) " transforms)")
             (if (empty? catalog)
               [:div.muted "Catalog not loaded."]
               (into [:div]
                     (for [[category entries] (sort-by key by-category)]
                       ^{:key (str category)}
                       [:div {:style {:marginBottom "6px"}}
                        [:span.mono {:style {:color "var(--live)"}} (str category)]
                        [:span.mono.muted {:style {:fontSize "12px"}}
                         " " (str/join ", " (map :node_type entries))]]))))))

(defn- graphs-section []
  (let [graphs @(rf/subscribe [:graphs])
        statuses @(rf/subscribe [:graph-statuses])
        selected @(rf/subscribe [:selected-graph-id])]
    (section (str "Stream graphs (" (count graphs) ")")
             (if (empty? graphs)
               [:div.muted "No saved graphs."]
               (into [:div]
                     (for [{:keys [graph_id label nodes edges]} graphs]
                       (let [status (get statuses graph_id)
                             run-state (:run_state status)]
                         ^{:key graph_id}
                         [:div.panel-inset
                          {:style {:padding "8px 10px" :marginBottom "6px"
                                   :borderColor (when (= selected graph_id)
                                                  "var(--selection)")}}
                          [:div {:style {:display "flex" :gap "8px" :alignItems "center"}}
                           [:span {:class (str "dot " (case run-state
                                                        "running" "live"
                                                        ("error" "stalled") "error"
                                                        "starting" "warn"
                                                        "muted"))}]
                           [:strong label]
                           [:span.mono.muted {:style {:fontSize "12px"}}
                            (str (count nodes) " nodes · " (count edges) " edges"
                                 " · " (or run-state "draft"))]]
                          [:div.mono.muted {:style {:fontSize "12px"}} graph_id]
                          [:div {:style {:marginTop "6px" :display "flex" :gap "6px"}}
                           [:button {:style {:fontSize "12px"}
                                     :on-click #(rf/dispatch [:graphs/select graph_id])}
                            "select"]
                           [:button {:style {:fontSize "12px"}
                                     :on-click #(rf/dispatch [:graphs/request-status graph_id])}
                            "status"]
                           [:button {:style {:fontSize "12px"}
                                     :on-click #(rf/dispatch [:graphs/start graph_id])}
                            "start"]
                           [:button {:style {:fontSize "12px"}
                                     :on-click #(rf/dispatch [:graphs/stop graph_id])}
                            "stop"]]])))))))

(defn- toasts []
  (let [items @(rf/subscribe [:toasts])]
    (into [:div {:style {:position "fixed" :right "16px" :bottom "16px"
                         :display "flex" :flexDirection "column" :gap "8px"
                         :maxWidth "420px" :zIndex 50}}]
          (for [{:keys [id level text]} items]
            ^{:key id}
            [:div.panel
             {:style {:padding "10px 12px"
                      :borderColor (case level
                                     :error "var(--error)"
                                     :warn "var(--warn)"
                                     "var(--line)")}
              :on-click #(rf/dispatch [:toast/dismiss id])}
             [:div {:style {:fontSize "13px"}} text]]))))

(defn root []
  [:div {:style {:padding "20px" :maxWidth "980px" :margin "0 auto"}}
   [:div {:style {:display "flex" :justifyContent "space-between"
                  :alignItems "baseline" :marginBottom "16px"}}
    [:div
     [:div {:style {:fontSize "20px"}} "natKit · Visual Programming"]
     [:div.mono.muted {:style {:fontSize "12px"}}
      "ClojureScript frontend · Phase 0 protocol harness"]]
    [connection-pill]]
   [catalog-section]
   [streams-section]
   [graphs-section]
   [toasts]])
