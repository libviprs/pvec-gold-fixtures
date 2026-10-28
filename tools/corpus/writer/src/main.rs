//! corpus-writer: write the corpus DWGs that the r0-open writer has no form for.
//!
//!   corpus-writer all --root REPO --out DIR [--version AC1032]
//!
//! It writes four groups under DIR: `edge` (valid edge cases, through the r0-open writer unchanged),
//! `mixed` (several entity classes with nested blocks in one drawing), `degenerate` (authored
//! degenerate geometry that a pipeline must refuse) and `negative` (one unsupported entity each).
//! Numbers come from the f64_hex fields of the authored expected.math.json records, or from the
//! decimal strings of the parameter file where there is no record. It never reads a converter output.
#[allow(dead_code)]
mod w {
    include!(concat!(env!("OUT_DIR"), "/r0.rs"));
    include!("corpus.rs");
}

fn main() {
    w::run();
}
