(ns natkit.stream.viewer-registry
  "Which renderer shows a stream. Port of frontend/src/StreamViewer/viewerRegistry.ts.

  The renderer is chosen from the stream's DESCRIPTOR CAPABILITY plus the live
  frame shape — never from a sensor name. This is what replaced the old
  imu/muse/emg ladder, and it means adding a sensor never means adding a viewer
  branch. Both the canvas's viewer nodes and any standalone viewer select through
  `choose-renderer`."
  (:require [clojure.string :as str]
            [natkit.stream.descriptor :as descriptor]))

;; Markers are a first-class schema rather than a channel-frame capability, so
;; this one renderer IS schema-name driven — deliberately.
(def marker-schema-name "MarkerEventV1")

;; IMU carries a fixed accel/gyro/quaternion record rather than the generic
;; channels[].samples[] shape, so it gets a dedicated renderer. Identified by
;; schema name for the same reason as markers: there is no channel-frame
;; capability to probe.
(def imu-schema-names #{"NatImuBulkDataSchema" "NatImuDataSchema"})

(defn imu-schema? [schema-name]
  (contains? imu-schema-names schema-name))

(defn marker-schema? [schema-name]
  (= marker-schema-name schema-name))

(defn classification-frame-labels?
  "An lda_classify (or any classifier) output frame is a channel frame whose
  first channel is the predicted class index and whose remaining channels are
  per-class confidences. Detected by LABEL SHAPE, not schema name."
  [channel-labels]
  (boolean
   (and (sequential? channel-labels)
        (>= (count channel-labels) 2)
        (= "predicted_class" (first channel-labels))
        (every? #(and (string? %) (str/starts-with? % "confidence."))
                (rest channel-labels)))))

(defn choose-renderer
  "Pick a renderer keyword for a stream.

  `shape` is an optional live-frame hint {:n_channels :samples_per_channel
  :channel_labels} — the descriptor says a stream IS a channel frame, but only a
  live frame reveals whether it is a rolling waveform, a per-window feature
  vector or a classifier readout. `schema-name-hint` covers streams with no
  channel-frame descriptor (e.g. a marker stream).

  Returns one of :marker :muse :imu :classification :feature_vector
  :channel_frame :inspector."
  ([descriptor-map] (choose-renderer descriptor-map nil nil))
  ([descriptor-map shape] (choose-renderer descriptor-map shape nil))
  ([descriptor-map shape schema-name-hint]
   (let [schema-name (:schema_name descriptor-map)]
     (cond
       ;; Schema-identified renderers come first: they are not channel frames,
       ;; so the capability probes below would misclassify them.
       (or (marker-schema? schema-name) (marker-schema? schema-name-hint))
       :marker

       (descriptor/looks-like-muse? descriptor-map)
       :muse

       (or (imu-schema? schema-name) (imu-schema? schema-name-hint))
       :imu

       (descriptor/supports-numeric-channel-frames? descriptor-map)
       (cond
         (classification-frame-labels? (:channel_labels shape))
         :classification

         ;; A per-window feature vector emits one scalar per channel — there is
         ;; no waveform to trace. Anything with real time-series samples is a
         ;; waveform. With no shape hint at all we default to the waveform,
         ;; which is safe for the common case.
         (and shape
              (some? (:samples_per_channel shape))
              (<= (:samples_per_channel shape) 1)
              (> (or (:n_channels shape) 0) 1))
         :feature_vector

         :else :channel_frame)

       ;; Any other self-describing record falls back to the generic descriptor
       ;; inspector until a capability-matched renderer exists.
       :else :inspector))))
