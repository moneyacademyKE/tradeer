# 📈 Tradeer — AI-Powered Evolutionary Crypto Trading Bot

Tradeer is a cryptocurrency high-frequency trading bot designed with **Rich Hickey's de-complection principles**. It decouples state from identity, represents history as a list of immutable facts, and implements an automated **AI Evolutionary Loop** that spawns, evaluates, and prunes dynamic trading strategies.

---

## 🏗️ Architecture & Philosophy

```
  ┌────────────────────────────────────────────────────────┐
  │                   AI Evolutionary Loop                 │
  │  (Mutates parent strategy -> injects to pool -> tests) │
  └───────────┬────────────────────────────────────────────┘
              │ (updates POOL.strategies)
              ▼
  ┌────────────────────────────────────────────────────────┐
  │                 FastAPI API Server                     │
  │    (Exposes state & strategy details securely)        │
  └───────────┬────────────────────────────────────────────┘
              │ (feeds telemetry)
              ▼
  ┌────────────────────────────────────────────────────────┐
  │                 StateAtom (Identity)                   │
  │      (Holds single immutable WorldState snapshot)      │
  └───────────┬────────────────────▲───────────────────────┘
              │ (checks risk)      │ (derives transitions)
              ▼                    │
  ┌───────────────────────┐ ┌──────┴───────────────────────┐
  │      Risk Engine      │ │      next_state (Core)       │
  │ (Drawdown Circuit Brk)│ │   (Pure State Transitions)   │
  └───────────────────────┘ └──────────────────────────────┘
```

- **De-complected Core**: System evolution is driven by a pure functional transition: `(State, Event) -> (NextState, Commands)`.
- **Identity vs. State**: The `WorldState` is completely frozen (immutable). The continuity of the system is managed by an Atom structure (`StateAtom`) through functional swaps and resets.
- **AST-Based Sandbox**: AI-generated code is checked statically using Python's `ast` library before execution, preventing code imports or double-underscore attribute escapes.
- **Drawdown Circuit Breakers**: Built-in institutional risk management monitors strategy-level metrics. Strategies that breach drawdown limits are automatically de-activated and pruned.

---

## ⚙️ Configuration & Environment

Create a `.env` file in the root directory (do not commit this to git).

Refer to [.env.example](file:///.env.example) for defaults:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API Key for generative strategy mutations | *Required* |
| `BINANCE_API_KEY` | Binance Exchange API Key (optional, falls to simulation) | `""` |
| `BINANCE_SECRET` | Binance Exchange Secret (optional, falls to simulation) | `""` |
| `PAPER_TRADING` | Run mock trades instead of executing on exchange | `true` |
| `MAX_STRATEGY_DRAWDOWN`| Max strategy drawdown (USD) before deactivation | `150.0` |
| `DASHBOARD_USERNAME` | HTTP Basic Auth username for API dashboard | `admin` |
| `DASHBOARD_PASSWORD` | HTTP Basic Auth password for API dashboard | `admin` |

---

## 🚀 Running the Bot & Dashboard

### 1. Installation
Install project dependencies using Poetry:
```bash
poetry install
```
Or use pip with pyproject:
```bash
pip install .
```

### 2. Start the Bot & API
Run the consolidated bot dashboard process:
```bash
python3 run_dashboard.py
```
This concurrently boots:
1. The Trading Bot ticker loop.
2. The AI Researcher evolutionary strategy generator.
3. The FastAPI server, bound to `127.0.0.1:8001`.

Open [http://127.0.0.1:8001/static/index.html](http://127.0.0.1:8001/static/index.html) in your browser.

---

## 🧪 Testing

We verify the state transitions, AST sandboxing parameters, API authentication limits, and resilience decorators using `pytest`.

Run the automated test suite:
```bash
python3 -m pytest
```
