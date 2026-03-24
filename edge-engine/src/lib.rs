use worker::*;
use rhai::Engine;

#[durable_object]
pub struct TradeLab {
    state: State,
    env: Env,
}

#[durable_object]
impl DurableObject for TradeLab {
    fn new(state: State, env: Env) -> Self {
        Self { state, env }
    }

    async fn fetch(&mut self, _req: Request) -> Result<Response> {
        // Initialize Rhai Scripting Engine
        let mut engine = Engine::new();
        
        // Evaluate a basic AI script to prove embedding works
        let ai_script = "
            let roc = 0.05;
            let momentum = 0.02;
            if roc > 0.04 && momentum > 0.01 {
                return 1; // BUY
            } else {
                return -1; // SELL
            }
        ";
        
        let signal = engine.eval::<i64>(ai_script).unwrap_or(0);
        
        let action = match signal {
            1 => "BUY",
            -1 => "SELL",
            _ => "HOLD",
        };

        let msg = format!("Hello from the Rust WASM TradeLab DO! 🦀\nRhai embedded script evaluated action: {}", action);
        Response::ok(msg)
    }
}

#[event(fetch)]
pub async fn main(req: Request, env: Env, _ctx: Context) -> Result<Response> {
    // We create a singleton Durable Object named 'GlobalLab'
    // This perfectly mirrors our stateful while-loop in Python, but scales infinitely on CF Edge.
    let namespace = env.durable_object("TRADE_LAB")?;
    let id = namespace.id_from_name("GlobalLab")?;
    let stub = id.get_stub()?;
    
    // Forward the HTTP request to the singleton TradeLab executing our Rhai scripts
    stub.fetch_with_request(req).await
}
