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

(defn test-api-state []
  (println "--- Testing API State and JSON Compliance ---")
  (try
    (let [env (load-env)
          user (get env "DASHBOARD_USERNAME" "admin")
          pass (get env "DASHBOARD_PASSWORD" "admin")
          headers {"Authorization" (basic-auth-header user pass)}
          response (http/get "http://localhost:8001/api/state" {:headers headers})
          status (:status response)
          body (json/parse-string (:body response) true)]
      (println "API Response Status:" status)
      (if (= status 200)
        (do
          (println "Verification Successful: API returned 200 OK.")
          (println "Checking state fields...")
          (let [timestamp (:timestamp body)
                signals (:signals body)
                balance (:balance body)]
            (println "  - Timestamp:" timestamp)
            (println "  - Signals count:" (count signals))
            (println "  - Balance keys:" (keys balance))
            (if (and timestamp signals balance)
              (do
                (println "All core state fields are present.")
                (println "Verifying JSON compliance (no NaN/Infinity values)...")
                (let [sig-vals (vals signals)
                      has-invalid-val? (some (fn [v]
                                               (or (nil? v)
                                                   (and (float? v)
                                                        (or (Double/isNaN v)
                                                            (Double/isInfinite v)))))
                                             sig-vals)]
                  (if has-invalid-val?
                    (do
                      (println "FAIL: Found NaN/Infinity/Null in signals!")
                      (System/exit 1))
                    (do
                      (println "SUCCESS: All signals are compliant JSON numbers.")
                      (System/exit 0)))))
              (do
                (println "FAIL: Missing core state fields!")
                (System/exit 1)))))
        (do
          (println "FAIL: API returned status" status)
          (System/exit 1))))
    (catch Exception e
      (println "FAIL: Could not connect to API server or authentication failed.")
      (println "Error message:" (.getMessage e))
      (System/exit 1))))

(test-api-state)
