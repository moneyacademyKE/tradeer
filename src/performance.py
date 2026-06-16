import json
import os
from datetime import datetime

import logging

logger = logging.getLogger("tradeer")
PERFORMANCE_LOG_PATH = "performance_log.json"

def log_performance(timestamp: float, pnl: float, rsi: float, last_price: float):
    """
    Append performance snapshot to a JSON log for the AI researcher to analyze.
    """
    entry = {
        "timestamp": timestamp,
        "datetime": datetime.fromtimestamp(timestamp/1000).isoformat(),
        "pnl": pnl,
        "rsi": rsi,
        "price": last_price
    }
    
    # Read existing logs
    logs = []
    if os.path.exists(PERFORMANCE_LOG_PATH):
        try:
            with open(PERFORMANCE_LOG_PATH, "r") as f:
                logs = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load performance logs from {PERFORMANCE_LOG_PATH}: {e}")
            logs = []
            
    logs.append(entry)
    
    # Keep only last 1000 entries to avoid bloat
    if len(logs) > 1000:
        logs = logs[-1000:]
        
    with open(PERFORMANCE_LOG_PATH, "w") as f:
        json.dump(logs, f, indent=2)
