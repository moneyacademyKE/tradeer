import asyncio
import uvicorn
from src.api import app
from src.main import run_bot
from src.researcher import run_forever

async def main():
    # 1. Start the Trading Bot loop in the background
    bot_task = asyncio.create_task(run_bot('BTC/USDT'))
    
    # 2. Start the AI Researcher loop in the background
    researcher_task = asyncio.to_thread(run_forever)
    
    # 3. Start the FastAPI server
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    await asyncio.gather(
        server.serve(),
        bot_task,
        researcher_task
    )

if __name__ == "__main__":
    asyncio.run(main())
