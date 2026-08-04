(ns natkit.stream.descriptor
  "Schema-descriptor probing. Port of frontend/src/StreamViewer/schemaDescriptor.ts.

  A descriptor is the backend's self-description of a record's shape. Every
  capability question in the app — can this stream feed that transform? which
  viewer renders it? — is answered by probing STRUCTURE here, never by matching a
  schema or sensor name. That is what lets a new sensor onboard with no frontend
  change."
  (:require [clojure.string :as str]))

(def numeric-sample-types #{"int16" "uint32" "uint64" "float32" "float64"})

(defn- numeric-segment? [segment]
  (some? (re-matches #"\d+" segment)))

(defn find-field
  "Resolve a dotted descriptor path (e.g. \"channels.0.samples.0\") against a
  root field. A numeric segment indexes into an array's item field. Returns the
  field descriptor, or nil."
  [root path]
  (when (and root (string? path))
    (reduce (fn [current segment]
              (cond
                (nil? current) (reduced nil)

                (numeric-segment? segment)
                (if (and (= "array" (:type current)) (:items current))
                  (:items current)
                  (reduced nil))

                (not= "object" (:type current)) (reduced nil)

                :else (get-in current [:fields (keyword segment)])))
            root
            (str/split path #"\."))))

(defn- field-type-is?
  [root path allowed-types]
  (let [field (find-field root path)]
    (boolean (and field (contains? allowed-types (:type field))))))

(defn supports-numeric-channel-frames?
  "True when the descriptor matches the canonical numeric channel-frame contract
  (device_id / seq_no / device_ts_us / sample_rate_hz + channels[].samples[] of a
  numeric type). This is the contract a sensor publishes to get transforms,
  waveform plotting and band-passing for free."
  [descriptor]
  (let [root (:root descriptor)]
    (boolean
     (and descriptor
          (field-type-is? root "device_id" #{"string"})
          (field-type-is? root "seq_no" #{"uint64"})
          (field-type-is? root "device_ts_us" #{"uint64"})
          (field-type-is? root "sample_rate_hz" #{"uint32"})
          (field-type-is? root "channels" #{"array"})
          (field-type-is? root "channels.0.samples" #{"array"})
          (field-type-is? root "channels.0.samples.0" numeric-sample-types)))))

(defn looks-like-muse?
  "Structural probe for a Muse-like EEG record: an eeg object carrying the four
  canonical channels as arrays. Identified by SHAPE, not schema_name, so any
  record with this shape gets the Muse renderer."
  [descriptor]
  (let [root (:root descriptor)
        has-array? (fn [path] (field-type-is? root path #{"array"}))]
    (boolean
     (and descriptor
          (has-array? "eeg.tp9")
          (has-array? "eeg.af7")
          (has-array? "eeg.af8")
          (has-array? "eeg.tp10")))))

(defn value-at-path
  "Read the value at a dotted descriptor path out of a decoded record."
  [record path]
  (if (str/blank? path)
    record
    (reduce (fn [current segment]
              (cond
                (nil? current) (reduced nil)

                (numeric-segment? segment)
                (if (sequential? current)
                  (nth current (js/parseInt segment 10) nil)
                  (reduced nil))

                (or (sequential? current) (not (map? current))) (reduced nil)

                :else (get current (keyword segment))))
            record
            (str/split path #"\."))))

(defn format-value
  "Human-readable rendering of a descriptor-path value for the inspector."
  [value]
  (cond
    (nil? value) "Unavailable"
    (string? value) value
    (or (number? value) (boolean? value)) (str value)
    (sequential? value) (str "[" (count value) " items]")
    :else (js/JSON.stringify (clj->js value))))

;; --- Transform input mappings ----------------------------------------------

(defn- supports-explicit-input-mapping?
  [descriptor mapping]
  (and (= "explicit_channel_paths" (:mode mapping))
       (or (nil? (:schema_name mapping))
           (= (:schema_name descriptor) (:schema_name mapping)))
       (let [root (:root descriptor)
             ;; An absent optional path is satisfied.
             expect (fn [path allowed]
                      (or (nil? path) (field-type-is? root path allowed)))
             channels (:channels mapping)]
         (and (seq channels)
              (expect (:seq_no_path mapping) #{"uint32" "uint64"})
              (expect (:device_ts_us_path mapping) #{"uint64"})
              (or (some? (:sample_rate_hz_value mapping))
                  (expect (:sample_rate_hz_path mapping)
                          #{"uint32" "uint64" "float32" "float64"}))
              (every? (fn [channel]
                        (let [array-path (:sample_array_path channel)]
                          (and (field-type-is? root array-path #{"array"})
                               (field-type-is? root (str array-path ".0")
                                               numeric-sample-types))))
                      channels)))))

(defn- mapping-matches?
  [descriptor mapping]
  (if (= "canonical_channel_frame" (:mode mapping))
    (supports-numeric-channel-frames? descriptor)
    (supports-explicit-input-mapping? descriptor mapping)))

(defn supports-any-transform-capability?
  "True when at least one of the catalog's transforms can consume this stream."
  [descriptor capabilities]
  (boolean
   (and descriptor
        (some (fn [capability]
                (some #(mapping-matches? descriptor %) (:input_mappings capability)))
              capabilities))))

(defn compatible-input-mapping-id
  "The id of the first input mapping of `capability` this descriptor satisfies,
  or nil. Drives the editor's auto-pick when a transform node is connected."
  [descriptor capability]
  (when (and descriptor capability)
    (some (fn [mapping]
            (when (mapping-matches? descriptor mapping) (:id mapping)))
          (:input_mappings capability))))
