(ns natkit.core
  "Entry point. init-fn for the :app build (see shadow-cljs.edn)."
  (:require [reagent.dom.client :as rdom]
            [re-frame.core :as rf]
            [natkit.config :as config]
            [natkit.theme :as theme]
            [natkit.events]
            [natkit.subs]
            [natkit.ui.harness :as harness]))

(defonce ^:private root (atom nil))

(defn mount! []
  (let [container (.getElementById js/document "app")]
    (when (nil? @root)
      (reset! root (rdom/create-root container)))
    (rdom/render @root [harness/root])))

(defn ^:dev/after-load reload! []
  (rf/clear-subscription-cache!)
  (theme/inject! theme/dark)
  (mount!))

(defn init []
  (js/console.log "natKit CLJS frontend starting · ws:" (config/ws-url))
  (theme/inject! theme/dark)
  (rf/dispatch-sync [:app/boot])
  (mount!))
