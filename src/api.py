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
        with open("src/signals.py", "r") as f:
            return {"id": "base", "name": "Base RSI Strategy", "code": f.read()}
    
    strat = POOL.strategies.get(strategy_id)
    if strat:
        return {
            "id": strat.id, 
            "name": strat.name, 
            "code": strat.code,
            "explanation": strat.explanation
        }
    return {"error": "Not found"}

@app.get("/")
async def root():
    return {"message": "Tradeer-Hickey API is running. Visit /static/index.html for the dashboard."}
