// The write and read commands live in tools/r0-open/rust/src/main.rs, and I use them as they stand, so the DWG is written
// and the record is shaped by exactly the code that handles every r0-open probe. That file is a binary crate root, so
// its inner doc comments are stripped. Two things change, both because this is a different acadrust tree: the
// reader and writer id it stamps (the r0-open pin becomes this crate's commit), and the three checked scale setters in
// insert_for become the unchecked one, since the checked ones rewrite the zero singular-001 authors.
use std::{env, fs, path::PathBuf};

const CHECKED: &str = "                ins.set_x_scale(o.v[0]);\n                ins.set_y_scale(o.v[1]);\n                ins.set_z_scale(o.v[2]);\n";
const UNCHECKED: &str = "                ins.set_scale_unchecked(o.v[0], o.v[1], o.v[2]);\n";

fn main() {
    let src = PathBuf::from("../../../r0-open/rust/src/main.rs");
    println!("cargo:rerun-if-changed={}", src.display());
    println!("cargo:rerun-if-changed=Cargo.toml");
    let manifest = fs::read_to_string("Cargo.toml").expect("Cargo.toml");
    let rev = manifest.lines().find_map(|l| l.split("rev = \"").nth(1)).and_then(|r| r.split('"').next()).expect("rev").to_string();
    let text = fs::read_to_string(&src).expect("r0-open main.rs");
    let body: String = text.lines().filter(|l| !l.starts_with("//!")).map(|l| format!("{l}\n")).collect();
    assert_eq!(body.matches(CHECKED).count(), 1, "insert_for's scale setters moved");
    let body = body.replace(CHECKED, UNCHECKED).replace("acadrust@0.5.5+d35691f", &format!("acadrust@0.5.5+{}", &rev[..7]));
    assert!(!body.contains("d35691f"), "an r0-open id was left in");
    fs::write(PathBuf::from(env::var("OUT_DIR").unwrap()).join("r0.rs"), body).unwrap();
}
