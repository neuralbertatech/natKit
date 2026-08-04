(ns natkit.theme
  "Theme as data (plan §6). The theme is a Clojure map; garden compiles it to CSS
  and injects it at runtime. That gives light/dark/high-contrast switching for
  free, and leaves the door open to the interesting version later: a live
  classifier's output driving the accent.

  The visual target is rvbbit — translucent near-black surfaces over an optional
  backdrop, 1px neon borders, mixed type (geometric sans for labels, monospace for
  identifiers and values), and ONE accent per graph. Semantic colors are fixed so
  status never depends on the accent.

  This is the Phase-0/2 seed: enough to establish the identity and prove the
  garden pipeline. The full canvas/node/edge treatment lands with Phase 2."
  (:require [garden.core :as garden]))

(def dark
  {:name "dark"
   ;; Surfaces — translucent, so a backdrop can show through.
   :surface "rgba(10, 12, 20, 0.82)"
   :surface-raised "rgba(18, 22, 34, 0.88)"
   :surface-inset "rgba(4, 6, 12, 0.75)"
   :backdrop "#05070c"
   :line "rgba(120, 140, 180, 0.22)"
   :ink "#dbe6f0"
   :ink-muted "#8296a8"
   ;; Semantics — fixed, never accent-derived.
   :live "#00e5ff"        ; data edges, running nodes
   :provenance "#ffab70"  ; lineage edges (dashed)
   :selection "#c792ea"
   :error "#ff5370"
   :warn "#ffcb6b"
   :muted "#546e7a"
   ;; Type.
   :font-sans "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"
   :font-mono "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"})

(def accent-palette
  "Per-graph accents. rvbbit's boards each read as a single-accent scene; a graph
  picks one deterministically from its id so it stays stable across reloads."
  ["#00e5ff" "#ff4d9e" "#c792ea" "#ffcb6b" "#5ef38c" "#ff8a5c" "#6ea8ff"])

(defn accent-for
  "Deterministic accent for a graph id. Same graph, same color, every session."
  [graph-id]
  (if (seq graph-id)
    (let [h (reduce (fn [acc ch] (mod (+ (* acc 31) (.charCodeAt ch 0)) 1000003))
                    7
                    (seq (str graph-id)))]
      (nth accent-palette (mod h (count accent-palette))))
    (first accent-palette)))

(defn stylesheet
  "Compile a theme map to CSS text."
  [theme]
  (garden/css
   [[":root"
     {:--surface (:surface theme)
      :--surface-raised (:surface-raised theme)
      :--surface-inset (:surface-inset theme)
      :--backdrop (:backdrop theme)
      :--line (:line theme)
      :--ink (:ink theme)
      :--ink-muted (:ink-muted theme)
      :--live (:live theme)
      :--provenance (:provenance theme)
      :--selection (:selection theme)
      :--error (:error theme)
      :--warn (:warn theme)
      :--muted (:muted theme)
      :--font-sans (:font-sans theme)
      :--font-mono (:font-mono theme)}]
    ["*" {:box-sizing "border-box"}]
    ["html, body, #app" {:height "100%" :margin 0}]
    ["body" {:background (:backdrop theme)
             :color (:ink theme)
             :font-family (:font-sans theme)
             :font-size "14px"
             :line-height 1.5
             :-webkit-font-smoothing "antialiased"}]
    [".mono" {:font-family (:font-mono theme)}]
    ;; Panel: the base surface every sidebar/inspector/node card is built from.
    [".panel" {:background (:surface theme)
               :border (str "1px solid " (:line theme))
               :border-radius "10px"
               :backdrop-filter "blur(8px)"}]
    [".panel-inset" {:background (:surface-inset theme)
                     :border (str "1px solid " (:line theme))
                     :border-radius "6px"}]
    [".muted" {:color (:ink-muted theme)}]
    ;; Status dot — the one visual that must not depend on the accent.
    [".dot" {:display "inline-block" :width "8px" :height "8px"
             :border-radius "999px" :vertical-align "middle"}]
    [".dot.live" {:background (:live theme)
                  :box-shadow (str "0 0 8px " (:live theme))}]
    [".dot.error" {:background (:error theme)}]
    [".dot.warn" {:background (:warn theme)}]
    [".dot.muted" {:background (:muted theme)}]]))

(defn inject!
  "Install (or replace) the theme stylesheet in the document head."
  [theme]
  (let [id "natkit-theme"
        existing (.getElementById js/document id)
        node (or existing (.createElement js/document "style"))]
    (set! (.-id node) id)
    (set! (.-textContent node) (stylesheet theme))
    (when-not existing (.appendChild (.-head js/document) node))
    node))
