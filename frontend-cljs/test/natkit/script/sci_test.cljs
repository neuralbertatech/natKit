(ns natkit.script.sci-test
  "Tests for the script contract and the SCI runner.

  Three things are being pinned here: that a script is a pure frame -> frame
  function, that a script which violates the contract becomes a NODE ERROR rather
  than a corrupt frame reaching downstream consumers, and that the sandbox
  actually denies what it claims to deny."
  (:require [cljs.test :refer-macros [deftest testing is]]
            [natkit.script.contract :as contract]
            [natkit.script.sci :as script]
            [natkit.stream.viewer-registry :as registry]))

(defn frame
  ([] (frame [[-1 2 -3 4] [5 -6 7 -8]]))
  ([channel-samples]
   {:device_id "exg-01"
    :seq_no 1234
    :device_ts_us 1784308749619698
    :sample_rate_hz 500
    :channels (vec (map-indexed (fn [i samples]
                                  {:label (str "ch" i) :samples (vec samples)})
                                channel-samples))}))

;; --- The contract -----------------------------------------------------------

(deftest a-canonical-frame-satisfies-the-contract
  (is (true? (contract/valid-frame? (frame))))
  (is (nil? (contract/explain-frame (frame)))))

(deftest the-contract-rejects-malformed-frames
  (testing "a missing channels vector"
    (is (some? (contract/explain-frame {:device_id "x"}))))
  (testing "a channel with no label"
    (is (some? (contract/explain-frame {:channels [{:samples [1 2]}]}))))
  (testing "non-numeric samples"
    (is (some? (contract/explain-frame {:channels [{:label "a" :samples ["x"]}]})))))

(deftest frame-shape-drives-renderer-selection
  (testing "a multi-sample frame reads as a waveform"
    (is (= :channel_frame
           (registry/choose-renderer contract/output-descriptor
                                     (contract/frame-shape (frame))))))
  (testing "a script that collapses each channel to one value reads as a feature vector"
    ;; This is the payoff of fixing the output descriptor: the viewer follows the
    ;; script's actual output shape with no configuration.
    (let [collapsed (contract/reduce-channels (frame) #(reduce + %))]
      (is (= 1 (contract/samples-per-channel collapsed)))
      (is (= :feature_vector
             (registry/choose-renderer contract/output-descriptor
                                       (contract/frame-shape collapsed)))))))

(deftest contract-helpers-preserve-frame-metadata
  (let [result (contract/map-samples (frame) abs)]
    (is (= "exg-01" (:device_id result)))
    (is (= 1234 (:seq_no result)))
    (is (= 500 (:sample_rate_hz result)))
    (is (= ["ch0" "ch1"] (contract/channel-labels result)))))

(deftest select-channels-reorders-and-filters
  (let [result (contract/select-channels (frame) ["ch1"])]
    (is (= ["ch1"] (contract/channel-labels result)))
    (is (= 1 (contract/channel-count result))))
  (testing "an unknown label is dropped rather than producing a nil channel"
    (is (= ["ch0"] (contract/channel-labels
                    (contract/select-channels (frame) ["ch0" "nope"]))))))

;; --- Compiling --------------------------------------------------------------

(deftest compiles-a-stateless-script
  (let [compiled (script/compile-script "(fn [frame] frame)")]
    (is (true? (:ok? compiled)))
    (is (fn? (:fn compiled)))))

(deftest reports-a-syntax-error-without-throwing
  (let [compiled (script/compile-script "(fn [frame] ")]
    (is (false? (:ok? compiled)))
    (is (= :compile (:phase compiled)))
    (is (string? (:error compiled)))))

(deftest rejects-a-script-that-is-not-a-function
  (let [compiled (script/compile-script "42")]
    (is (false? (:ok? compiled)))
    (is (= :compile (:phase compiled)))
    (is (re-find #"not a function" (:error compiled)))))

(deftest rejects-an-empty-script
  (is (false? (:ok? (script/compile-script ""))))
  (is (false? (:ok? (script/compile-script "   ")))))

;; --- Running ----------------------------------------------------------------

(deftest runs-the-identity-script
  (let [result (script/eval-frame "(fn [frame] frame)" (frame))]
    (is (true? (:ok? result)))
    (is (= (frame) (:frame result)))
    (is (= :stateless (:arity result)))
    (is (number? (:elapsed-ms result)))))

(deftest runs-the-default-starter-script
  (testing "a new script node opens with code that actually runs"
    (let [result (script/eval-frame contract/default-clojure-script (frame))]
      (is (true? (:ok? result)))
      (testing "and the starter rectifies, as its comment claims"
        (is (= [1 2 3 4] (:samples (first (:channels (:frame result))))))))))

(deftest runs-a-feature-extraction-script
  (let [result (script/eval-frame
                "(fn [frame] (nk/reduce-channels frame nk/rms))"
                (frame [[3 4] [0 0]]))]
    (is (true? (:ok? result)))
    (is (= 1 (contract/samples-per-channel (:frame result))))
    (testing "rms of [3 4] is 3.535…"
      (is (< 3.53 (first (:samples (first (:channels (:frame result))))) 3.54)))))

(deftest exposes-the-nk-and-math-toolkit
  (doseq [[label source expected-fn]
          [["nk/mean" "(fn [f] (nk/reduce-channels f nk/mean))" some?]
           ["nk/channel-labels" "(fn [f] (assoc f :device_id (first (nk/channel-labels f))))" some?]
           ["math/sqrt" "(fn [f] (nk/map-samples f (fn [s] (math/sqrt (math/abs s)))))" some?]
           ["str/join" "(fn [f] (assoc f :device_id (str/join \"+\" (nk/channel-labels f))))" some?]
           ["nk/zero-crossings" "(fn [f] (nk/reduce-channels f nk/zero-crossings))" some?]
           ["nk/diff" "(fn [f] (nk/map-channels f (fn [c] (update c :samples #(vec (nk/diff %))))))" some?]]]
    (testing label
      (let [result (script/eval-frame source (frame))]
        (is (true? (:ok? result)) (str label " failed: " (:error result)))
        (is (expected-fn (:frame result)))))))

(deftest a-runtime-error-becomes-a-node-error
  (testing "calling a nil value — the archetypal typo — is reported as :invoke"
    (let [result (script/eval-frame "(fn [frame] ((:no-such-key frame) 1))" (frame))]
      (is (false? (:ok? result)))
      (is (= :invoke (:phase result)))
      (is (string? (:error result)))))
  (testing "an explicit throw is caught too"
    (let [result (script/eval-frame "(fn [frame] (throw (ex-info \"boom\" {})))" (frame))]
      (is (false? (:ok? result)))
      (is (= :invoke (:phase result)))))
  (testing "arithmetic on nil is NOT a throw in ClojureScript — it yields NaN, so
            it surfaces as a CONTRACT violation rather than a runtime error"
    ;; Worth pinning: the failure mode a user sees for (/ 1 nil) is "returned
    ;; value does not satisfy the frame contract", not a stack trace.
    (let [result (script/eval-frame "(fn [frame] (/ 1 nil))" (frame))]
      (is (false? (:ok? result)))
      (is (= :contract (:phase result))))))

;; --- The contract is ENFORCED, not assumed ----------------------------------

(deftest a-script-returning-a-non-frame-is-rejected
  (testing "downstream consumers trust the descriptor, so a bad shape must not pass"
    (doseq [[label source] [["a number" "(fn [frame] 42)"]
                            ["a string" "(fn [frame] \"nope\")"]
                            ["nil" "(fn [frame] nil)"]
                            ["a map with no channels" "(fn [frame] {:device_id \"x\"})"]
                            ["channels with bad samples"
                             "(fn [frame] {:channels [{:label \"a\" :samples [\"x\"]}]})"]]]
      (testing label
        (let [result (script/eval-frame source (frame))]
          (is (false? (:ok? result)))
          (is (contains? #{:contract :invoke} (:phase result)))
          (is (string? (:error result))))))))

(deftest a-script-may-freely-change-channels-labels-and-values
  (testing "the contract fixes the KIND of output, not its dimensions"
    (let [result (script/eval-frame
                  "(fn [frame]
                     {:device_id (:device_id frame)
                      :seq_no (:seq_no frame)
                      :sample_rate_hz (:sample_rate_hz frame)
                      :channels [{:label \"derived\" :samples [1.0 2.0 3.0]}]})"
                  (frame))]
      (is (true? (:ok? result)))
      (is (= ["derived"] (contract/channel-labels (:frame result))))
      (is (= 1 (contract/channel-count (:frame result)))))))

;; --- Stateful scripts -------------------------------------------------------

(deftest runs-a-stateful-script-and-threads-state
  ;; Stateful scripts are what make IIR-like work possible: a filter needs the
  ;; previous sample, and a running counter needs the previous count.
  (let [source "(fn [state frame]
                  (let [n (inc (or (:n state) 0))]
                    {:state {:n n}
                     :frame (assoc frame :seq_no n)}))"
        compiled (script/compile-script source)
        first-run (script/run-frame compiled (frame) nil)
        second-run (script/run-frame compiled (frame) (:state first-run))]
    (is (true? (:ok? first-run)))
    (is (= :stateful (:arity first-run)))
    (is (= 1 (:seq_no (:frame first-run))))
    (is (= {:n 1} (:state first-run)))
    (testing "state carries into the next frame"
      (is (= 2 (:seq_no (:frame second-run))))
      (is (= {:n 2} (:state second-run))))))

(deftest a-stateless-script-leaves-state-untouched
  (let [result (script/run-frame (script/compile-script "(fn [frame] frame)")
                                 (frame)
                                 {:carried "value"})]
    (is (true? (:ok? result)))
    (is (= {:carried "value"} (:state result)))))

;; --- The sandbox ------------------------------------------------------------

(deftest the-sandbox-denies-host-interop
  (testing "js/ is unreachable — no DOM, no network, no eval"
    (doseq [source ["(fn [frame] (js/eval \"1+1\"))"
                    "(fn [frame] (js/fetch \"http://example.com\"))"
                    "(fn [frame] js/window)"
                    "(fn [frame] js/process)"
                    "(fn [frame] (.-cookie js/document))"]]
      (let [result (script/eval-frame source (frame))]
        (is (false? (:ok? result))
            (str "sandbox allowed: " source))))))

(deftest the-sandbox-denies-unbound-namespaces
  (testing "only the explicit allow-list resolves"
    (doseq [source ["(fn [frame] (clojure.java.io/file \"/etc/passwd\"))"
                    "(fn [frame] (requiring-resolve 'clojure.core/slurp))"
                    "(fn [frame] (slurp \"/etc/passwd\"))"]]
      (is (false? (:ok? (script/eval-frame source (frame))))
          (str "sandbox allowed: " source)))))

(deftest the-sandbox-allows-plain-clojure-core
  (testing "core stays available — the sandbox restricts reach, not expressiveness"
    (let [result (script/eval-frame
                  "(fn [frame]
                     (update frame :channels
                             (fn [cs] (vec (map-indexed
                                             (fn [i c] (assoc c :label (str \"c\" i)))
                                             cs)))))"
                  (frame))]
      (is (true? (:ok? result)))
      (is (= ["c0" "c1"] (contract/channel-labels (:frame result)))))))

(deftest the-sandbox-restricts-reach-but-NOT-resource-use
  ;; Documenting a real, measured limitation rather than asserting a guarantee we
  ;; do not have.
  ;;
  ;; SCI contains what a script can REACH, not what it can SPEND. `(vec (range))`
  ;; exhausts the heap and `(loop [] (recur))` wedges the calling thread; SCI's
  ;; `:realize-max` does not contain either (verified: it bounds certain lazy-seq
  ;; realizations at the REPL boundary, not arbitrary work inside a script). There
  ;; is deliberately NO test executing those forms — it would kill this runner.
  ;;
  ;; Containment is an execution-venue problem: a Web Worker with a wall-clock
  ;; kill, which is a UI-phase deliverable. What we can pin here is that a large
  ;; BOUNDED computation completes and stays within the contract.
  (let [result (script/eval-frame
                "(fn [frame]
                   (assoc frame :channels
                          [{:label \"big\" :samples (vec (range 50000))}]))"
                (frame))]
    (is (true? (:ok? result)))
    (is (= 50000 (contract/samples-per-channel (:frame result))))))

(deftest arity-is-read-from-the-function-not-guessed
  ;; REGRESSION: the first implementation tried (f frame) and fell back to
  ;; (f state frame) on error. That is unsound — a wrong-arity call to an SCI fn
  ;; does NOT throw, it binds the missing parameter to nil. A stateful script
  ;; invoked as (f frame) therefore bound state=frame, frame=nil and failed the
  ;; contract check with a baffling message instead of running correctly.
  (is (= :stateless (:arity (script/compile-script "(fn [frame] frame)"))))
  (is (= :stateful (:arity (script/compile-script "(fn [state frame] {:frame frame})"))))
  (testing "arity is reported on the run result too, for the node's status readout"
    (is (= :stateful (:arity (script/eval-frame "(fn [state frame] {:frame frame})"
                                                (frame)))))))

;; --- Starter scripts for both languages -------------------------------------

(deftest both-languages-ship-a-starter
  (is (= contract/default-clojure-script (contract/default-script-for "clojure")))
  (is (= contract/default-python-script (contract/default-script-for "python")))
  (testing "an unknown language falls back to clojure rather than a blank editor"
    (is (= contract/default-clojure-script (contract/default-script-for "elvish"))))
  (testing "the python starter documents the same frame contract"
    (is (re-find #"channels" contract/default-python-script))
    (is (re-find #"samples" contract/default-python-script))
    (is (re-find #"def process" contract/default-python-script))))
