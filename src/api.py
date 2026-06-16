import os
import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from src.state_manager import SHARED_STATE

app = FastAPI(title="Tradeer-Hickey API")

# Mount static files for the frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, os.getenv("DASHBOARD_USERNAME", "admin"))
    correct_password = secrets.compare_digest(credentials.password, os.getenv("DASHBOARD_PASSWORD", "admin"))
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.get("/api/state")
async def get_state(username: str = Depends(authenticate)):
    """Returns the current WorldState as JSON."""
    state = SHARED_STATE.deref()
    return state.model_dump()

@app.get("/api/signals")
async def get_signals_code(username: str = Depends(authenticate)):
    """Returns the source code of active signals for UI visualization."""
    try:
        with open("src/signals.py", "r") as f:
            static_code = f.read()
        with open("src/dynamic_signals.py", "r") as f:
            dynamic_code = f.read()
        return {
            "static": static_code,
            "dynamic": dynamic_code
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/strategy/{strategy_id}")
async def get_strategy_detail(strategy_id: str, username: str = Depends(authenticate)):
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
