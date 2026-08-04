(ns natkit.config
  "Build-time configuration. `debug?` is set per build in shadow-cljs.edn via
  :closure-defines, so dev-only work (malli assertions at the socket boundary)
  is dead-code-eliminated from :advanced release builds.")

(goog-define debug? true)

(defn- browser? []
  (exists? js/window))

(defn ws-url
  "The backend WebSocket URL. Configuration, never a hardcode:

    1. an injected `window.NATKIT_WS_URL` (dev, where the shadow dev server and
       the backend are on different ports);
    2. `NATKIT_WS_URL` from the environment (the node integration check);
    3. otherwise derived from the page origin, which is what works behind nginx
       in production."
  []
  (or (when (browser?) (some-> (aget js/window "NATKIT_WS_URL") not-empty))
      (when-not (browser?)
        (some-> (aget (.-env js/process) "NATKIT_WS_URL") not-empty))
      (if (browser?)
        (let [proto (if (= "https:" (.-protocol js/location)) "wss:" "ws:")]
          (str proto "//" (.-host js/location) "/ws/stream_viewer"))
        "ws://localhost:7409/ws/stream_viewer")))
