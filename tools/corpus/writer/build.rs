// The curve and INSERT builders live in tools/r0-open/rust/src/main.rs. I reuse them as they are, so
// the numbers in a mixed fixture are stored by exactly the code that stores the r0-open probes.
// That file is a binary crate root, so its inner doc comments are stripped before it is included.
use std::{env, fs, path::PathBuf};

fn main() {
    let src = PathBuf::from("../../r0-open/rust/src/main.rs");
    println!("cargo:rerun-if-changed={}", src.display());
    let text = fs::read_to_string(&src).expect("r0-open main.rs");
    let body: String = text.lines().filter(|l| !l.starts_with("//!")).map(|l| format!("{l}\n")).collect();
    let out = PathBuf::from(env::var("OUT_DIR").unwrap()).join("r0.rs");
    fs::write(out, body).unwrap();
}
