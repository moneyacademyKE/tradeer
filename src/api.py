import os
import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from src.state_manager import SHARED_STATE

security = HTTPBasic()

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; "
            "script-src 'self'; "
            "connect-src 'self'; "
            "img-src 'self' data:; "
            "object-src 'none'; "
            "frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

app = FastAPI(title="Tradeer-Hickey API")
app.add_middleware(SecurityHeadersMiddleware)

# Mount static files for the frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

# Validate env-based auth credentials early
_AUTH_USER = os.getenv("DASHBOARD_USERNAME", "admin")
_AUTH_PASS = os.getenv("DASHBOARD_PASSWORD", "admin")

def verify_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """Reject unauthenticated requests using HTTP Basic Auth."""
    expected_user = _AUTH_USER
    expected_pass = _AUTH_PASS
    # Use secrets.compare_digest to prevent timing attacks
    user_ok = secrets.compare_digest(credentials.username, expected_user)
    pass_ok = secrets.compare_digest(credentials.password, expected_pass)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

@app.get("/api/state", dependencies=[Depends(verify_auth)])
async def get_state():
    """Returns the current WorldState as JSON."""
    state = SHARED_STATE.deref()
    return state.model_dump()

@app.get("/api/signals", dependencies=[Depends(verify_auth)])
async def get_signals_code():
    """Returns the source code of active signals for UI visualization."""
    try:
        static_code = ""
        if os.path.exists("src/signals.py"):
            with open("src/signals.py", "r") as f:
                static_code = f.read()
        
        dynamic_code = ""
        if os.path.exists("src/dynamic_signals.py"):
            with open("src/dynamic_signals.py", "r") as f:
                dynamic_code = f.read()
                
        return {
            "static": static_code,
            "dynamic": dynamic_code
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/strategy/{strategy_id}", dependencies=[Depends(verify_auth)])
async def get_strategy_detail(strategy_id: str):
    from src.strategy_pool import POOL
    if strategy_id == "base":
        try:
            with open("src/signals.py", "r") as f:
                return {"id": "base", "name": "Base RSI Strategy", "code": f.read()}
        except OSError as e:
            return {"error": f"Could not read signals.py: {e}"}

    strat = POOL.strategies.get(strategy_id)
    if strat:
        return {
            "id": strat.id,
            "name": strat.name,
            "code": strat.code,
            "explanation": strat.explanation
        }
    return {"error": "Not found"}

@app.get("/api/autoresearch/state", dependencies=[Depends(verify_auth)])
async def get_autoresearch_state():
    """Returns the current state of the autoresearch harness: pool size,
    winners count at the active target, top performers, drawdown leaders."""
    import json as _json
    try:
        with open("strategy_pool.json") as f:
            pool = _json.load(f)
    except Exception:
        pool = {}
    try:
        with open("data/pool_stats.json") as f:
            stats = _json.load(f)
    except Exception:
        stats = {}

    # Read the live target from the seeder
    try:
        from autoresearch.seed_stats import TARGET_PNL, DEFAULT_POOL_SIZE
        target = TARGET_PNL
        pool_size_cap = DEFAULT_POOL_SIZE
    except Exception:
        target = 200.0
        pool_size_cap = 50

    ranked = []
    for sid, s in stats.items():
        if sid == "base":
            continue
        ranked.append({
            "id": sid,
            "name": s.get("name", sid),
            "current_pnl": s.get("current_pnl", 0.0),
            "trades": s.get("trades", 0),
            "wins": s.get("wins", 0),
            "drawdown": s.get("drawdown", 0.0),
            "peak": s.get("peak", 0.0),
            "action": s.get("action", "HOLD"),
        })
    ranked.sort(key=lambda x: -x["current_pnl"])

    winners = [r for r in ranked if r["current_pnl"] > target]
    losers = [r for r in ranked if r["current_pnl"] < 0]
    losers.sort(key=lambda x: x["current_pnl"])
    pool_ids = set(pool.keys())
    orphans = [r for r in ranked if r["id"] not in pool_ids]

    # Read iteration log if it exists
    iterations = []
    try:
        if os.path.exists("data/autoresearch_log.json"):
            with open("data/autoresearch_log.json") as f:
                iterations = _json.load(f)
    except Exception:
        iterations = []

    return {
        "target_pnl": target,
        "pool_size": len(pool),
        "pool_cap": pool_size_cap,
        "stats_size": len(ranked),
        "above_target": len(winners),
        "loser_count": len(losers),
        "orphan_count": len(orphans),
        "top_winners": ranked[:10],
        "top_losers": losers[:5],
        "orphans": orphans[:10],
        "iterations": iterations[-20:],
    }


@app.post("/api/autoresearch/run", dependencies=[Depends(verify_auth)])
async def autoresearch_run(payload: dict = None):
    """Run one autoresearch cycle: reseed the pool from a backtest using
    the current TARGET_PNL. Mirrors python3 -m autoresearch.seed_stats."""
    import json as _json
    try:
        from autoresearch.seed_stats import seed_pool_stats
        seed = int((payload or {}).get("seed", 42))
        pool_size = int((payload or {}).get("pool_size", 50))
        min_above = int((payload or {}).get("min_above_target", 5))
        market_steps = int((payload or {}).get("market_steps", 10000))
        import asyncio
        pool, stats = await asyncio.to_thread(
            seed_pool_stats,
            pool_size=pool_size,
            min_above_target=min_above,
            seed=seed,
            market_steps=market_steps,
        )
        n_above = sum(1 for k, v in stats.items() if k != "base" and v.get("current_pnl", 0) > target)
        # Log the iteration
        log_path = "data/autoresearch_log.json"
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        try:
            with open(log_path) as f:
                log = _json.load(f)
        except Exception:
            log = []
        log.append({
            "ts": int(__import__("time").time()),
            "seed": seed,
            "pool_size": len(pool),
            "n_above_target": n_above,
        })
        with open(log_path, "w") as f:
            _json.dump(log, f, indent=2)
        return {
            "ok": True,
            "pool_size": len(pool),
            "n_above_target": n_above,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"autoresearch run failed: {e}")


@app.post("/api/autoresearch/reseed", dependencies=[Depends(verify_auth)])
async def autoresearch_reseed(payload: dict = None):
    """Keep top n_keep strategies by current P/L, mutate the rest.
    This is the 'Reseed From Top Winners' action — distinct from a full seed_pool_stats run."""
    import json as _json
    import asyncio
    try:
        n_keep = int((payload or {}).get("n_keep", 25))
        from autoresearch.iteration import reseed_strategies
        # Load current pool and stats from disk
        try:
            with open("strategy_pool.json") as f:
                pool = _json.load(f)
        except Exception:
            pool = {}
        try:
            with open("data/pool_stats.json") as f:
                stats = _json.load(f)
        except Exception:
            stats = {}
        await asyncio.to_thread(reseed_strategies, pool, stats, n_keep)
        # Reload to get updated count
        try:
            with open("strategy_pool.json") as f:
                new_pool = _json.load(f)
        except Exception:
            new_pool = {}
        return {"ok": True, "pool_size": len(new_pool)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"reseed failed: {e}")


@app.get("/")
async def root():
    return {"message": "Tradeer-Hickey API is running. Visit /static/index.html for the dashboard."}
