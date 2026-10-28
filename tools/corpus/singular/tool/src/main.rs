// singular-tool: the r0-open write and read commands, built against the acadrust commit pinned in Cargo.toml.
//   singular-tool write --kt DIR --params DIR --out DIR | read --dwg FILE --out FILE
include!(concat!(env!("OUT_DIR"), "/r0.rs"));
