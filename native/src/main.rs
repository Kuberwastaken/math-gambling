use math_gambling_kernel::{run, Task};
use serde_json::{json, Value};
use std::io::{self, BufRead, Write};
use std::time::Instant;
fn main() {
    let mont = std::env::args().any(|s| s == "--montgomery");
    for line in io::stdin().lock().lines() {
        let line = line.expect("read task");
        if line.len() > 2048 {
            eprintln!("task exceeds byte cap");
            std::process::exit(2);
        }
        let started = Instant::now();
        let output: Result<Value, String> = serde_json::from_str::<Task>(&line)
            .map_err(|e| e.to_string())
            .and_then(|t| {
                run(t, mont, |hit| {
                    println!("{}", json!({"type":"identity","hit":hit}));
                    io::stdout().flush().expect("flush identity");
                })
            });
        match output {
            Ok(result) => {
                // Timing is reported outside the receipt so digests never depend on it.
                let cpu_ms = started.elapsed().as_secs_f64() * 1000.0;
                println!("{}", json!({"type":"timing","cpu_ms":cpu_ms}));
                println!("{}", result)
            }
            Err(e) => {
                eprintln!("{e}");
                std::process::exit(2);
            }
        }
        io::stdout().flush().expect("flush receipt");
    }
}
