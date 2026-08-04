(ns natkit.stream.viewer-registry-test
  "Ported from frontend/src/StreamViewer/viewerRegistry.test.ts. The contract these
  pin: a renderer is chosen from descriptor STRUCTURE plus live frame shape, so
  onboarding a sensor never means adding a viewer branch."
  (:require [cljs.test :refer-macros [deftest testing is]]
            [natkit.stream.viewer-registry :as registry]))

;; --- Descriptor fixtures ----------------------------------------------------

(defn field
  ([id type] (field id type nil))
  ([id type extra] (merge {:id id :label id :type type :optional false} extra)))

(defn obj [id fields]
  (field id "object" {:fields fields}))

(defn channel-frame-descriptor
  "The canonical numeric channel frame: device_id/seq_no/… + channels[].samples[]."
  []
  {:schema_name "SomeSensorFrameV1"
   :descriptor_version 1
   :root (obj "root"
              {:device_id (field "device_id" "string")
               :seq_no (field "seq_no" "uint64")
               :device_ts_us (field "device_ts_us" "uint64")
               :sample_rate_hz (field "sample_rate_hz" "uint32")
               :channels (field "channels" "array"
                                {:items (obj "channel"
                                             {:samples (field "samples" "array"
                                                              {:items (field "sample" "float32")})})})})})

(defn muse-descriptor []
  (let [band #(field "band" "array" {:items (field "v" "float32")})]
    {:schema_name "SomeEegSchema"
     :descriptor_version 1
     :root (obj "root"
                {:eeg (obj "eeg" {:tp9 (band) :af7 (band) :af8 (band) :tp10 (band)})})}))

(defn imu-descriptor
  "An IMU-shaped record — NOT a channel frame, NOT muse."
  []
  {:schema_name "SomeImuSchema"
   :descriptor_version 1
   :root (obj "root"
              {:accel (obj "accel" {:x (field "x" "float64")
                                    :y (field "y" "float64")
                                    :z (field "z" "float64")})})})

;; --- choose-renderer --------------------------------------------------------

(deftest routes-a-muse-shaped-descriptor-to-the-muse-renderer
  (is (= :muse (registry/choose-renderer (muse-descriptor)))))

(deftest routes-a-multi-sample-channel-frame-to-the-waveform-renderer
  (is (= :channel_frame
         (registry/choose-renderer (channel-frame-descriptor)
                                  {:n_channels 8 :samples_per_channel 64}))))

(deftest routes-a-per-window-feature-vector-to-the-feature-vector-renderer
  (is (= :feature_vector
         (registry/choose-renderer (channel-frame-descriptor)
                                  {:n_channels 27 :samples_per_channel 1}))))

(deftest routes-a-classifier-output-frame-to-the-classification-renderer
  (is (= :classification
         (registry/choose-renderer (channel-frame-descriptor)
                                  {:n_channels 4
                                   :samples_per_channel 1
                                   :channel_labels ["predicted_class"
                                                    "confidence.rest"
                                                    "confidence.flex"
                                                    "confidence.extend"]}))))

(deftest defaults-a-channel-frame-with-no-shape-hint-to-the-waveform-renderer
  ;; Without a live frame we cannot tell waveform from feature vector, so we
  ;; default to the waveform renderer (safe for the common case).
  (is (= :channel_frame (registry/choose-renderer (channel-frame-descriptor)))))

(deftest falls-back-to-the-inspector-for-an-unknown-descriptor
  (is (= :inspector (registry/choose-renderer (imu-descriptor))))
  (testing "and for no descriptor at all"
    (is (= :inspector (registry/choose-renderer nil)))))

(deftest selects-the-imu-renderer-for-the-nat-imu-schemas
  (testing "from the descriptor's schema name"
    (is (= :imu (registry/choose-renderer
                 (assoc (imu-descriptor) :schema_name "NatImuBulkDataSchema")))))
  (testing "and from an explicit hint when there is no descriptor"
    (is (= :imu (registry/choose-renderer nil nil "NatImuDataSchema")))))

;; --- marker selection -------------------------------------------------------

(deftest picks-the-marker-renderer-from-a-marker-descriptor-schema
  ;; A marker stream may carry no channel-frame descriptor at all.
  (is (= :marker (registry/choose-renderer {:schema_name registry/marker-schema-name}))))

(deftest picks-the-marker-renderer-from-an-explicit-schema-hint
  (is (= :marker (registry/choose-renderer nil nil registry/marker-schema-name))))

(deftest does-not-pick-marker-for-a-non-marker-schema-hint
  (is (= :inspector (registry/choose-renderer nil nil "ExgPillEmgDataSchemaV1"))))

(deftest marker-schema-only-matches-marker-event-v1
  (is (true? (registry/marker-schema? registry/marker-schema-name)))
  (is (false? (registry/marker-schema? "SomethingElse")))
  (is (false? (registry/marker-schema? nil))))

;; --- classification label shape ---------------------------------------------

(deftest detects-the-predicted-class-and-confidence-label-shape
  (is (true? (registry/classification-frame-labels?
              ["predicted_class" "confidence.a" "confidence.b"]))))

(deftest rejects-ordinary-channel-labels
  (is (false? (registry/classification-frame-labels? ["ch0" "ch1" "ch2"]))))

(deftest rejects-nil-and-too-short-label-lists
  (is (false? (registry/classification-frame-labels? nil)))
  (is (false? (registry/classification-frame-labels? ["predicted_class"]))))

(deftest rejects-a-label-list-whose-tail-is-not-all-confidences
  (testing "a stray non-confidence label disqualifies the frame"
    (is (false? (registry/classification-frame-labels?
                 ["predicted_class" "confidence.a" "ch2"])))))
