#!/usr/bin/env bb

(require '[babashka.http-client :as http]
         '[cheshire.core :as json]
         '[clojure.string :as str])

(defn load-env []
  (try
    (let [content (slurp ".env")
          lines (str/split-lines content)]
      (into {}
            (keep (fn [line]
                    (let [trimmed (str/trim line)]
                      (when (and (not (str/starts-with? trimmed "#"))
                                 (str/includes? trimmed "="))
                        (let [[k v] (str/split trimmed #"=" 2)]
                          [(str/trim k) (str/trim v)]))))
                  lines)))
    (catch Exception _
      {})))

(defn basic-auth-header [user pass]
  (let [credentials (str user ":" pass)
        encoded (.encodeToString (java.util.Base64/getEncoder) (.getBytes credentials))]
    (str "Basic " encoded)))

(defn get-headers [env]
  (let [user (get env "DASHBOARD_USERNAME" "admin")
        pass (get env "DASHBOARD_PASSWORD" "admin")]
    {"Authorization" (basic-auth-header user pass)
     "Content-Type" "application/json"}))

(defn fetch-autoresearch-state [base-url headers]
  (try
    (let [url (str base-url "/api/autoresearch/state")
          response (http/get url {:headers headers})
          body (json/parse-string (:body response) true)]
      body)
    (catch Exception e
      (println "Error fetching autoresearch state:" (.getMessage e))
      nil)))

(defn run-evolution-cycle [base-url headers seed pool-size market-steps]
  (println (format "Triggering evolution cycle (seed=%d, pool-size=%d, steps=%d)..." seed pool-size market-steps))
  (try
    (let [url (str base-url "/api/autoresearch/run")
          payload (json/generate-string {:seed seed :pool_size pool-size :market_steps market-steps})
          response (http/post url {:headers headers :body payload})
          body (json/parse-string (:body response) true)]
      body)
    (catch Exception e
      (println "Error running evolution cycle:" (.getMessage e))
      nil)))

(defn verify-state-compliance [base-url headers]
  (println "Verifying state compliance for all active strategies...")
  (try
    (let [url (str base-url "/api/state")
          response (http/get url {:headers headers})
          body (json/parse-string (:body response) true)
          signals (:signals body)]
      (if signals
        (let [invalid-vals (keep (fn [[k v]]
                                   (when (or (nil? v)
                                             (and (float? v)
                                                  (or (Double/isNaN v)
                                                      (Double/isInfinite v))))
                                     [k v]))
                                 signals)]
          (if (seq invalid-vals)
            (do
              (println "COMPLIANCE FAILURE: Found invalid non-JSON numbers in signals:" invalid-vals)
              false)
            (do
              (println "COMPLIANCE SUCCESS: All signals are valid, compliant JSON floats.")
              true)))
        (do
          (println "Warning: No signals present in current state to verify.")
          true)))
    (catch Exception e
      (println "Error verifying state compliance:" (.getMessage e))
      false)))

(defn -main []
  (println "=========================================================")
  (println "🧬 Tradeer Babashka Autoresearch Orchestrator 🧬")
  (println "=========================================================")
  
  (let [env (load-env)
        port (get env "PORT" "8001")
        base-url (str "http://localhost:" port)
        headers (get-headers env)]
    
    (println "Connecting to API at:" base-url)
    
    ;; 1. Fetch current state
    (if-let [state (fetch-autoresearch-state base-url headers)]
      (do
        (println "\n--- Current Autoresearch State ---")
        (println "  Pool Size:     " (:pool_size state) "/" (:pool_cap state))
        (println "  Above Target:  " (:above_target state) "strategies (Target P/L: $" (:target_pnl state) ")")
        (println "  Orphans:       " (:orphan_count state))
        (println "  Loser Count:   " (:loser_count state))
        
        (when (seq (:top_winners state))
          (println "\n  Top Winners:")
          (doseq [w (take 3 (:top_winners state))]
            (println (format "    - %s (%s): PnL=$%.2f (trades=%d, wins=%d)" 
                             (:name w) (subs (:id w) 0 8) (:current_pnl w) (:trades w) (:wins w)))))
        
        ;; 2. Run an evolution cycle
        (let [seed (rand-int 100000)
              run-result (run-evolution-cycle base-url headers seed 50 10000)]
          (if (and run-result (:ok run-result))
            (do
              (println "\nEvolution Cycle Succeeded!")
              (println "  New Pool Size:        " (:pool_size run-result))
              (println "  New Strategies > $2000:" (:n_above_2000 run-result))
              
              ;; 3. Verify compliance
              (if (verify-state-compliance base-url headers)
                (do
                  (println "\n=========================================================")
                  (println "✅ ITERATION COMPLETE & RICH HICKEY CERTIFIED ✅")
                  (println "=========================================================")
                  (System/exit 0))
                (do
                  (println "\n❌ Compliance check failed! ❌")
                  (System/exit 1))))
            (do
              (println "\n❌ Evolution cycle failed or returned invalid response.")
              (System/exit 1)))))
      (do
        (println "Could not connect to API server. Please ensure run_dashboard.py is running.")
        (System/exit 1)))))

(-main)
