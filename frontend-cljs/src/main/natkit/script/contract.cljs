(ns natkit.script.contract
  "The contract a script node's code must satisfy — shared by BOTH runners.

  A script is a pure function over one canonical channel frame:

      stateless:  (fn [frame] frame')
      stateful:   (fn [state frame] {:state state' :frame frame'})

  `frame` is the canonical `NatSignalFrameDataSchemaV1` shape every natKit
  transform already speaks:

      {:device_id \"exg-01\"
       :seq_no 1234
       :device_ts_us 1784308749619698
       :sample_rate_hz 500
       :channels [{:label \"ch0\" :samples [0.1 0.2 …]} …]}

  WHY THIS SHAPE, AND WHY VALIDATED BOTH WAYS
  ------------------------------------------
  The whole system is descriptor-driven: compatibility checks, viewer selection,
  input-mapping auto-pick and the \"recommended next\" list all read a node's
  OUTPUT DESCRIPTOR. For a script node that descriptor has to be known *without
  running the script* — otherwise a script node could not be wired up until after
  it had executed, and a script edit could silently invalidate everything
  downstream of it.

  So the contract is fixed: a script consumes a channel frame and produces a
  channel frame, and its advertised output descriptor is the canonical one. The
  script may change channel count, labels and sample values freely — that is the
  point — but it may not change the *kind* of thing it emits.

  A script that returns something else is a NODE ERROR, not a corrupt frame:
  downstream consumers trust the descriptor, so emitting a malformed frame would
  push the failure somewhere much harder to diagnose. `normalize-result` is what
  enforces that, and it is the same rule the Python runner applies on its side."
  (:require [malli.core :as m]
            [malli.error :as me]
            [natkit.graph.model :as model]))

;; --- The frame schema -------------------------------------------------------

(def Channel
  [:map
   [:label :string]
   [:samples [:sequential number?]]])

(def Frame
  [:map
   [:device_id {:optional true} :string]
   [:seq_no {:optional true} :int]
   [:device_ts_us {:optional true} :int]
   [:sample_rate_hz {:optional true} number?]
   [:channels [:sequential Channel]]])

(defn valid-frame? [frame] (m/validate Frame frame))

(defn explain-frame
  "nil when `frame` satisfies the contract, otherwise a humanized explanation."
  [frame]
  (when-let [error (m/explain Frame frame)]
    (me/humanize error)))

(def output-descriptor
  "What a script node advertises on its output port — known statically, before the
  script has ever run."
  model/canonical-channel-frame-descriptor)

;; --- Frame helpers (also exposed INTO scripts) ------------------------------

(defn channel-labels [frame]
  (mapv :label (:channels frame)))

(defn channel-count [frame]
  (count (:channels frame)))

(defn samples-per-channel
  "Samples on the first channel. Frames are rectangular by contract, but a script
  may legitimately be mid-edit, so this is tolerant."
  [frame]
  (count (:samples (first (:channels frame)))))

(defn frame-shape
  "The live-frame hint the viewer registry uses to pick a renderer. A script that
  reduces each channel to one value automatically renders as a feature vector
  rather than a waveform — no configuration needed."
  [frame]
  {:n_channels (channel-count frame)
   :samples_per_channel (samples-per-channel frame)
   :channel_labels (channel-labels frame)})

(defn channel-by-label [frame label]
  (some #(when (= label (:label %)) %) (:channels frame)))

(defn map-samples
  "Apply `f` to every sample of every channel, preserving labels."
  [frame f]
  (update frame :channels
          (fn [channels]
            (mapv #(update % :samples (fn [samples] (mapv f samples))) channels))))

(defn map-channels
  "Rebuild the channel vector with `f`: (f channel) -> channel."
  [frame f]
  (update frame :channels #(mapv f %)))

(defn reduce-channels
  "Collapse each channel to a single value with `f`: (f samples) -> number.
  Produces a one-sample-per-channel frame, i.e. a feature vector."
  [frame f]
  (update frame :channels
          (fn [channels]
            (mapv (fn [channel]
                    (assoc channel :samples [(f (:samples channel))]))
                  channels))))

(defn select-channels
  "Keep only the channels whose labels appear in `labels`, in that order."
  [frame labels]
  (assoc frame :channels
         (into [] (keep #(channel-by-label frame %)) labels)))

;; --- Result normalization ---------------------------------------------------

(defn normalize-result
  "Coerce whatever a script returned into {:frame f :state s}, or report why it
  cannot be. Accepts either script shape:

    - a frame map                        -> {:frame it :state unchanged}
    - {:frame f} or {:frame f :state s}  -> as given

  Returns {:ok? true :frame f :state s} or {:ok? false :error msg}."
  [result previous-state]
  (cond
    (nil? result)
    {:ok? false :error "script returned nil — it must return a frame"}

    (not (map? result))
    {:ok? false
     :error (str "script returned " (goog/typeOf result)
                 " — it must return a frame map")}

    ;; The stateful shape, distinguished by an explicit :frame key.
    (contains? result :frame)
    (let [frame (:frame result)]
      (if-let [problems (explain-frame frame)]
        {:ok? false :error (str "returned :frame does not satisfy the frame contract: "
                                (pr-str problems))}
        {:ok? true
         :frame frame
         :state (if (contains? result :state) (:state result) previous-state)}))

    :else
    (if-let [problems (explain-frame result)]
      {:ok? false :error (str "returned value does not satisfy the frame contract: "
                              (pr-str problems))}
      {:ok? true :frame result :state previous-state})))

;; --- Starter scripts --------------------------------------------------------
;; A new script node opens with working, runnable code rather than a blank editor.

(def default-clojure-script
  "(fn [frame]
  ;; A script is a pure function from one channel frame to another.
  ;; Available: clojure core, clojure.string as str, and the `nk` helpers
  ;; (nk/map-samples, nk/reduce-channels, nk/channel-by-label, nk/mean, …).
  ;;
  ;; This one rectifies every sample. Try nk/reduce-channels with nk/rms to
  ;; turn the frame into a per-channel feature vector instead.
  (nk/map-samples frame nk/abs))
")

(def default-python-script
  "def process(frame):
    \"\"\"A script is a pure function from one channel frame to another.

    frame = {'device_id': str, 'seq_no': int, 'device_ts_us': int,
             'sample_rate_hz': float,
             'channels': [{'label': str, 'samples': [float, ...]}, ...]}

    Return a frame of the same shape. numpy is available as np.
    \"\"\"
    for channel in frame['channels']:
        channel['samples'] = [abs(s) for s in channel['samples']]
    return frame
")

(defn default-script-for [language]
  (case language
    "python" default-python-script
    default-clojure-script))
