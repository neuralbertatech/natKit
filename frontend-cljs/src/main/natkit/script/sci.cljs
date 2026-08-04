(ns natkit.script.sci
  "The `script_sci` runner: user ClojureScript evaluated with SCI.

  SANDBOXING
  ----------
  SCI is sandboxed by construction, which is the reason this runner can ship
  ahead of the Python one. The evaluation context is an explicit ALLOW-LIST of
  vars and namespaces; anything not bound is unresolvable. Verified empirically:

    (sci/eval-string \"(js/eval \\\"1+1\\\")\")   => Could not resolve symbol: js/eval
    (sci/eval-string \"(str/upper-case \\\"x\\\")\") => Could not resolve symbol (unless bound)

  So there is no host interop, no DOM, no network and no filesystem reachable
  from a script unless this namespace hands it over — and it hands over nothing
  but pure functions.

  WHAT IS NOT SOLVED HERE — MEASURED, NOT ASSUMED
  -----------------------------------------------
  SCI restricts REACH, not RESOURCE USE. A script cannot touch the host, but it
  can burn unbounded CPU and memory:

    (loop [] (recur))          ; wedges the calling thread
    (vec (range))              ; exhausts the heap

  Both were verified. In particular SCI's `:realize-max` does NOT contain the
  second case — it bounds certain lazy-seq realizations at the REPL boundary, not
  arbitrary work inside a script, so it is deliberately not used here rather than
  left in to imply protection it does not give.

  Containment is an execution-venue problem, not an evaluator one: the script must
  run in a Web Worker with a wall-clock kill, so a runaway script terminates a
  worker instead of the tab. That is a UI-phase deliverable; this namespace is the
  pure, testable core that sits underneath it. Until it exists, a script node can
  hang the browser tab that authors it — acceptable while the author is the
  operator, and the reason the Python runner (which faces the same problem without
  SCI's reach guarantees) needs process isolation before it ships.

  NOTHING HERE THROWS. A script runs on a data path, so every failure has to
  become a node error state carrying a useful message — never an exception that
  unwinds the caller."
  (:require [clojure.set]
            [clojure.string :as str]
            [natkit.script.contract :as contract]
            [sci.core :as sci]))

;; --- The toolkit exposed to scripts -----------------------------------------

(defn- mean [samples]
  (if (seq samples) (/ (reduce + samples) (count samples)) 0))

(defn- rms [samples]
  (if (seq samples)
    (js/Math.sqrt (/ (reduce + (map #(* % %) samples)) (count samples)))
    0))

(defn- variance [samples]
  (if (seq samples)
    (let [m (mean samples)]
      (/ (reduce + (map #(let [d (- % m)] (* d d)) samples)) (count samples)))
    0))

(def ^:private nk-namespace
  "The `nk` helper namespace — the frame vocabulary that makes scripts pleasant to
  write. All pure, all safe to expose."
  {'map-samples contract/map-samples
   'map-channels contract/map-channels
   'reduce-channels contract/reduce-channels
   'select-channels contract/select-channels
   'channel-by-label contract/channel-by-label
   'channel-labels contract/channel-labels
   'channel-count contract/channel-count
   'samples-per-channel contract/samples-per-channel
   'frame-shape contract/frame-shape
   ;; Small stats vocabulary — the things a feature-extraction script reaches for
   ;; first, and which are tedious to hand-roll.
   'mean mean
   'rms rms
   'variance variance
   'std (fn [samples] (js/Math.sqrt (variance samples)))
   'abs abs
   'sum (fn [samples] (reduce + samples))
   'min-of (fn [samples] (when (seq samples) (reduce min samples)))
   'max-of (fn [samples] (when (seq samples) (reduce max samples)))
   'zero-crossings (fn [samples]
                     (count (filter (fn [[a b]] (neg? (* a b)))
                                    (partition 2 1 samples))))
   'diff (fn [samples] (mapv - (rest samples) (butlast samples)))
   'clamp (fn [x low high] (max low (min high x)))})

(def ^:private math-namespace
  {'sqrt js/Math.sqrt 'pow js/Math.pow 'exp js/Math.exp 'log js/Math.log
   'sin js/Math.sin 'cos js/Math.cos 'tan js/Math.tan 'atan js/Math.atan
   'atan2 js/Math.atan2 'floor js/Math.floor 'ceil js/Math.ceil
   'round js/Math.round 'abs js/Math.abs 'PI js/Math.PI 'E js/Math.E})

(def allowed-namespaces
  "Everything a script may reach. Deliberately small: clojure.core comes from SCI
  itself, and these are the only additions. No js/, no DOM, no I/O."
  {'str {'join str/join 'split str/split 'trim str/trim
         'upper-case str/upper-case 'lower-case str/lower-case
         'starts-with? str/starts-with? 'ends-with? str/ends-with?
         'includes? str/includes? 'replace str/replace 'blank? str/blank?}
   'set {'union clojure.set/union 'intersection clojure.set/intersection
         'difference clojure.set/difference}
   'math math-namespace
   'nk nk-namespace})

(defn- context []
  (sci/init {:namespaces allowed-namespaces}))

;; --- Compile ----------------------------------------------------------------

(defn- detect-arity
  "Whether the script takes [frame] or [state frame].

  Read off the function's own arity rather than guessed by calling it: a
  wrong-arity call to an SCI fn does NOT throw, it silently binds the missing
  parameter to nil. A stateful script invoked as `(f frame)` would therefore bind
  state=frame, frame=nil and fail somewhere confusing downstream. Verified that
  `.-length` is 1 for `(fn [frame] …)` and 2 for `(fn [state frame] …)`."
  [f]
  (if (= 2 (.-length f)) :stateful :stateless))

(defn compile-script
  "Evaluate `source` and check it yields something callable.

  Returns {:ok? true :fn f :arity :stateless|:stateful} or
          {:ok? false :phase :compile :error msg}."
  [source]
  (if (str/blank? source)
    {:ok? false :phase :compile :error "script is empty"}
    (try
      (let [value (sci/eval-string* (context) source)]
        (cond
          (nil? value)
          {:ok? false :phase :compile
           :error "script evaluated to nil — it must evaluate to a function"}

          (not (fn? value))
          {:ok? false :phase :compile
           :error (str "script evaluated to " (goog/typeOf value)
                       ", not a function — wrap it in (fn [frame] …)")}

          :else {:ok? true :fn value :arity (detect-arity value)}))
      (catch :default e
        {:ok? false :phase :compile :error (or (.-message e) (str e))}))))

;; --- Run --------------------------------------------------------------------

(defn- invoke
  "Call the script at its declared arity."
  [f arity state frame]
  (try
    {:ok? true :value (if (= :stateful arity) (f state frame) (f frame))}
    (catch :default e
      {:ok? false :error (or (.-message e) (str e))})))

(defn run-frame
  "Run a compiled script over one frame.

  Returns {:ok? true :frame f' :state s' :arity a :elapsed-ms n}
       or {:ok? false :phase :invoke|:contract :error msg}."
  ([compiled frame] (run-frame compiled frame nil))
  ([compiled frame state]
   (let [started (js/performance.now)]
     (if-not (:ok? compiled)
       compiled
       (let [arity (:arity compiled)
             outcome (invoke (:fn compiled) arity state frame)]
         (if-not (:ok? outcome)
           (assoc outcome :phase :invoke :arity arity
                  :elapsed-ms (- (js/performance.now) started))
           (let [normalized (contract/normalize-result (:value outcome) state)]
             (assoc normalized
                    :arity arity
                    :elapsed-ms (- (js/performance.now) started)
                    :phase (when-not (:ok? normalized) :contract)))))))))

(defn eval-frame
  "Compile and run in one step — the convenience path for a one-off preview.
  Prefer compiling once and reusing on a live stream."
  ([source frame] (eval-frame source frame nil))
  ([source frame state] (run-frame (compile-script source) frame state)))
