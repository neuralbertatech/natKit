(ns natkit.protocol.wire
  "JSON <-> ClojureScript codec for the /ws/stream_viewer protocol.

  Two rules, both discovered the hard way against real captured payloads.

  RULE 1 — wire keys keep their snake_case spelling, VERBATIM. There is no
  kebab-case conversion anywhere in this app. `editor_metadata` round-trips
  through the backend opaquely (it carries the unflattened composite editor tree,
  which is how a composite graph reloads from the backend alone), and a
  transform's `config` keys come from the runtime node catalog, so they are
  unknown at compile time — we could not reliably un-rename them even if we
  wanted to.

  RULE 2 — only FIELD NAMES become keywords. A key becomes a keyword only when it
  matches ^[A-Za-z_][A-Za-z0-9_]*$; every other key stays a string.

  Rule 2 is not stylistic. `(js->clj x :keywordize-keys true)` turns a key
  containing a slash into a NAMESPACED keyword, and writing it back with
  `clj->js` emits only the name — so \"source/13793649670644-1785250699870\"
  silently becomes \"13793649670644-1785250699870\". natKit node ids routinely
  contain a slash (source/…, viewer/…, composite/…, param/1, export/1) and
  `node_statuses`, `node_diagnostics` and `edge_diagnostics` are all keyed BY NODE
  ID. Three of five node_statuses keys in a real captured payload hit this.

  The rule also lands on the right semantics: backend field names are always
  snake_case, so they keywordize (`:graph_id`, `:run_state`), while identifier
  keys — which are data, not field names — stay strings. Every id-keyed lookup
  table is therefore accessed with the raw id, and `(name k)` is always safe on
  one of our keywords.

  Corollary of both rules: only KEYS are converted. VALUES stay strings —
  \"transform\", not :transform. Keywordizing values would need a per-field
  allow-list (a schema_name or a device_id must never become a keyword), and the
  whole point of the catalog-driven design is that new node types need no
  frontend change."
  (:require [clojure.string :as str]))

(def ^:private field-name-pattern #"[A-Za-z_][A-Za-z0-9_]*")

(defn field-name?
  "True when a wire key is a plain snake_case field name, and therefore safe to
  represent as a keyword."
  [k]
  (some? (re-matches field-name-pattern k)))

(defn- decode-key [k]
  (if (field-name? k) (keyword k) k))

(defn- encode-key [k]
  (cond
    ;; `str` then drop the leading ':' rather than `name`, so a namespaced keyword
    ;; would survive too. By rule 2 we never create one, but this makes the
    ;; encoder correct for hand-written data as well.
    (keyword? k) (subs (str k) 1)
    (string? k) k
    :else (str k)))

(defn js->data
  "An already-parsed JS value -> ClojureScript data, applying rule 2."
  [js-value]
  (cond
    (nil? js-value) nil
    (array? js-value) (mapv js->data js-value)
    (identical? "object" (goog/typeOf js-value))
    (persistent!
     (reduce (fn [acc k] (assoc! acc (decode-key k) (js->data (unchecked-get js-value k))))
             (transient {})
             (js-keys js-value)))
    :else js-value))

(defn data->js
  "ClojureScript data -> a plain JS value, applying rule 1 (keys emitted verbatim)."
  [value]
  (cond
    (nil? value) nil
    (map? value)
    (let [obj (js-obj)]
      (doseq [[k v] value] (unchecked-set obj (encode-key k) (data->js v)))
      obj)
    (or (sequential? value) (set? value)) (into-array (map data->js value))
    (keyword? value) (encode-key value)
    :else value))

(defn parse
  "JSON text -> ClojureScript data. Returns ::invalid-json rather than throwing so
  a malformed frame can be reported instead of killing the socket handler."
  [json-text]
  (try
    (js->data (js/JSON.parse json-text))
    (catch :default _ ::invalid-json)))

(defn invalid-json? [parsed] (= ::invalid-json parsed))

(defn encode
  "ClojureScript data -> JSON text."
  [value]
  (js/JSON.stringify (data->js value)))

(defn round-trips?
  "True when `value` survives encode -> parse unchanged. The codec tests pin both
  rules on real captured payloads with this."
  [value]
  (= value (parse (encode value))))

;; --- Message / action helpers ----------------------------------------------

(defn message-type
  "The `type` of an inbound message, as a string (e.g. \"stream_graph_list\")."
  [message]
  (:type message))

(defn action-name
  "The `action` of an outbound action, as a string (e.g. \"save_stream_graph\")."
  [action]
  (:action action))

(defn request-id
  "A fresh request id for an outbound action. The backend echoes it on the reply;
  the prefix makes a WS trace readable."
  [prefix]
  (str prefix ":" (js/Date.now)))

(defn error-message
  "Human-readable text from an `error` message."
  [message]
  (or (:message message) (:error message) "Unknown backend error"))

(defn marker-attribute
  "Read one attribute off a marker event. Marker attributes are backend-defined
  names (the per-cue class label lives under \"gesture\"), so the key is passed as
  a string and decoded the same way the codec would have."
  [marker attribute-name]
  (get-in marker [:attributes (decode-key attribute-name)]))

(defn key-name
  "The raw wire spelling of a decoded key, whether it came back as a keyword or a
  string. Safe on namespaced keywords, unlike `name`."
  [k]
  (if (keyword? k) (subs (str k) 1) (str k)))

(defn id-keyed
  "Normalize a wire lookup table so every key is the raw id string.

  Rule 2 already leaves most id keys as strings, but an id that happens to look
  like a plain field name would have keywordized — a graph literally called
  \"verify\" becomes :verify while one called \"vp-verify\" stays a string. Any
  map this app INDEXES INTO by id (statuses, node_statuses, diagnostics, streams)
  is normalized on receipt so a lookup by id always hits."
  [m]
  (when m
    (persistent! (reduce-kv (fn [acc k v] (assoc! acc (key-name k) v))
                            (transient {})
                            m))))

(defn blank->nil [s]
  (when (and (string? s) (not (str/blank? s))) s))
