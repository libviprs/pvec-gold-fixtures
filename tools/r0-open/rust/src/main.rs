//! r0open: write the r0-open probe DWGs with acadrust, and dump what acadrust's reader sees.
//!
//!   r0open write --kt DIR --params DIR --out DIR [--version AC1032]
//!   r0open read  --dwg FILE --out FILE
//!
//! The writer takes every number from two places and nowhere else: the f64_hex fields of the
//! O1.5a/O1.6a expected.math.json records (exact bits, authored before any DWG existed) and, for the
//! transform ops, the decimal strings of the parameter files those records name. It never edits
//! either file and it never reads a converter output, a STEP file or a DWG.
//!
//! When the writer cannot store a probe exactly (it clamps a zero scale, the entity has no DWG
//! form), it does not write a lookalike. It reports the probe as SKIPPED with the reason, and the
//! corpus lists it as excluded.

use acadrust::entities::*;
use acadrust::types::{DxfVersion, Vector2, Vector3};
use acadrust::tables::Layer;
use acadrust::{BlockRecord, CadDocument, DwgReader, DwgWriter, TableEntry};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::f64::consts::TAU;
use std::fs;
use std::path::{Path, PathBuf};

const READER_ID: &str = "acadrust@0.5.5+d35691f";

type Skip = (String, String); // (reason code from ADR 0006, evidence)

fn skip<T>(reason: &str, evidence: impl Into<String>) -> Result<T, Skip> {
    Err((reason.to_string(), evidence.into()))
}

fn hex(x: f64) -> String {
    format!("0x{:016x}", x.to_bits())
}

fn fx(v: &Value) -> f64 {
    let s = v["f64_hex"].as_str().expect("f64_hex");
    f64::from_bits(u64::from_str_radix(s.trim_start_matches("0x"), 16).expect("hex"))
}

fn p3(v: &Value) -> Vector3 {
    let a = v.as_array().expect("point");
    Vector3::new(fx(&a[0]), fx(&a[1]), fx(&a[2]))
}

fn dec(s: &Value) -> f64 {
    s.as_str().expect("decimal string").parse::<f64>().expect("decimal")
}

fn find_expected(kt: &Path, id: &str) -> Option<PathBuf> {
    fn walk(d: &Path, id: &str, out: &mut Option<PathBuf>) {
        if let Ok(rd) = fs::read_dir(d) {
            for e in rd.flatten() {
                let p = e.path();
                if p.is_dir() {
                    if p.file_name().map(|n| n == id).unwrap_or(false) && p.join("expected.math.json").is_file() {
                        *out = Some(p.join("expected.math.json"));
                    }
                    walk(&p, id, out);
                }
            }
        }
    }
    let mut out = None;
    walk(kt, id, &mut out);
    out
}

fn default_x_axis(normal: Vector3, x: Vector3) -> bool {
    // The DWG circle and arc have no x axis of their own: it is the arbitrary-axis result for the
    // normal. For the z normal that is (1, 0, 0).
    normal.x == 0.0 && normal.y == 0.0 && normal.z == 1.0 && x.x == 1.0 && x.y == 0.0 && x.z == 0.0
}

fn make_curve(e: &Value, dwg_entity: Option<&str>) -> Result<EntityType, Skip> {
    let class = e["class"].as_str().unwrap();
    let g = &e["geometry"];
    let cl = &e["closure"];
    match class {
        "line" => Ok(EntityType::Line(Line {
            start: p3(&g["start"]),
            end: p3(&g["end"]),
            ..Line::new()
        })),
        "circle" | "circular_arc" => {
            let n = p3(&g["normal"]);
            if !default_x_axis(n, p3(&g["x_axis"])) {
                return skip("UNSUPPORTED_ENTITY", "the probe's x_axis is not the DWG arbitrary-axis default, and a DWG circle or arc cannot carry one");
            }
            if class == "circle" {
                Ok(EntityType::Circle(Circle {
                    center: p3(&g["center"]),
                    radius: fx(&g["radius"]),
                    normal: n,
                    ..Circle::new()
                }))
            } else {
                let start = fx(&g["start_angle"]);
                let mut end = start + fx(&g["sweep_angle"]);
                if !(0.0..TAU).contains(&start) {
                    return skip("UNSUPPORTED_ENTITY", "start angle outside [0, 2pi)");
                }
                if end >= TAU {
                    end -= TAU; // DWG stores the end angle reduced into [0, 2pi)
                }
                Ok(EntityType::Arc(Arc {
                    center: p3(&g["center"]),
                    radius: fx(&g["radius"]),
                    start_angle: start,
                    end_angle: end,
                    normal: n,
                    ..Arc::new()
                }))
            }
        }
        "ellipse" | "elliptical_arc" => {
            let m = p3(&g["major_axis"]);
            let a = fx(&g["semi_major"]);
            let b = fx(&g["semi_minor"]);
            let (s, t) = if class == "ellipse" {
                (0.0, TAU)
            } else {
                let s = fx(&g["start_angle"]);
                (s, s + fx(&g["sweep_angle"]))
            };
            Ok(EntityType::Ellipse(Ellipse {
                center: p3(&g["center"]),
                major_axis: Vector3::new(m.x * a, m.y * a, m.z * a),
                minor_axis_ratio: b / a,
                start_parameter: s,
                end_parameter: t,
                normal: p3(&g["normal"]),
                ..Ellipse::new()
            }))
        }
        "polyline" => {
            let vs = g["vertices"].as_array().unwrap();
            let bs = g["bulges"].as_array().unwrap();
            let mut pl = LwPolyline::new();
            let z0 = fx(&vs[0].as_array().unwrap()[2]);
            for (v, b) in vs.iter().zip(bs) {
                let v = p3(v);
                if v.z != z0 {
                    return skip("UNSUPPORTED_ENTITY", "an LWPOLYLINE has one elevation, the probe's vertices have different z");
                }
                pl.add_point_with_bulge(Vector2::new(v.x, v.y), fx(b));
            }
            pl.elevation = z0;
            let closed = cl["closed_by_endpoint"].as_bool().unwrap();
            if dwg_entity == Some("POLYLINE") {
                let mut p2 = Polyline2D::new();
                p2.elevation = z0;
                for (v, b) in vs.iter().zip(bs) {
                    let v = p3(v);
                    p2.add_vertex(Vertex2D::new(Vector3::new(v.x, v.y, z0)).with_bulge(fx(b)));
                }
                if closed {
                    p2.close();
                }
                return Ok(EntityType::Polyline2D(p2));
            }
            // For a closed record the closing segment is implicit: the flag is the closure.
            pl.is_closed = closed;
            Ok(EntityType::LwPolyline(pl))
        }
        "bezier" | "bspline" | "nurbs" => {
            let degree = g["degree"].as_i64().unwrap() as i32;
            let cps: Vec<Vector3> = g["control_points"].as_array().unwrap().iter().map(p3).collect();
            let knots: Vec<f64> = if class == "bezier" {
                let d = degree as usize + 1;
                let mut k = vec![fx(&e["parameter_domain"]["start"]); d];
                k.extend(vec![fx(&e["parameter_domain"]["end"]); d]);
                k
            } else {
                let mut k = Vec::new();
                for kn in g["knots"].as_array().unwrap() {
                    for _ in 0..kn["multiplicity"].as_u64().unwrap() {
                        k.push(fx(&kn["value"]));
                    }
                }
                k
            };
            let mut sp = Spline::new();
            sp.degree = degree;
            sp.control_points = cps;
            sp.knots = knots;
            if class == "nurbs" {
                sp.weights = g["weights"].as_array().unwrap().iter().map(fx).collect();
                sp.flags.rational = true;
            }
            // closed-by-knots and closed-by-endpoint stay separate: only the knot closure is a flag.
            sp.flags.closed = cl["closed_by_knots"].as_bool().unwrap();
            sp.flags.periodic = cl["periodic"].as_bool().unwrap();
            Ok(EntityType::Spline(sp))
        }
        other => skip("UNSUPPORTED_ENTITY", format!("no DWG form written for class {other}")),
    }
}

struct Op {
    kind: String,
    v: [f64; 3],
}

fn parse_ops(params: &Value) -> Result<Vec<Op>, Skip> {
    let mut ops = Vec::new();
    for o in params["ops"].as_array().unwrap() {
        let kind = o["op"].as_str().unwrap().to_string();
        match kind.as_str() {
            "translate" => {
                let a = o["v"].as_array().unwrap();
                ops.push(Op { kind, v: [dec(&a[0]), dec(&a[1]), dec(&a[2])] });
            }
            "scale" => {
                let a = o["s"].as_array().unwrap();
                ops.push(Op { kind, v: [dec(&a[0]), dec(&a[1]), dec(&a[2])] });
            }
            "rotate_z" => {
                let ang = if o.get("angle_rad").is_some() {
                    dec(&o["angle_rad"])
                } else {
                    let cs = o["cos_sin"].as_array().unwrap();
                    dec(&cs[1]).atan2(dec(&cs[0]))
                };
                ops.push(Op { kind, v: [ang, 0.0, 0.0] });
            }
            other => {
                return skip(
                    "UNSUPPORTED_ENTITY",
                    format!("op '{other}' (a general matrix) has no single INSERT form: one INSERT carries translation, one rotation about the normal and three scales, and no shear. A three-level nested INSERT chain (rotate, scale, rotate) could carry its 2x2 part through a singular value decomposition, but those factors would be derived values compared under policy and not EXACT, and the probe's own truth is a rejection outcome that no reader-mapping check can exercise, so that was not attempted"),
                )
            }
        }
    }
    Ok(ops)
}

fn add_block(doc: &mut CadDocument, name: &str) -> Result<acadrust::types::Handle, Skip> {
    let mut br = BlockRecord::new(name);
    let h = doc.allocate_handle();
    br.set_handle(h);
    br.block_entity_handle = doc.allocate_handle();
    br.block_end_handle = doc.allocate_handle();
    if let Err(e) = doc.block_records.add(br) {
        return skip("MALFORMED_FIXTURE", format!("block_records.add: {e}"));
    }
    Ok(h)
}

/// One INSERT for one group of ops, which must come outermost first as translate, rotate, scale.
fn insert_for(name: &str, ops: &[&Op]) -> Result<Insert, Skip> {
    let mut ins = Insert::new(name, Vector3::new(0.0, 0.0, 0.0));
    let mut rank = 0;
    for o in ops {
        let r = match o.kind.as_str() {
            "translate" => 0,
            "rotate_z" => 1,
            _ => 2,
        };
        if r < rank {
            return skip("UNSUPPORTED_ENTITY", "ops are not in translate, rotate, scale order, which is the only order one INSERT composes");
        }
        rank = r;
        match o.kind.as_str() {
            "translate" => ins.insert_point = Vector3::new(o.v[0], o.v[1], o.v[2]),
            "rotate_z" => ins.rotation = o.v[0],
            _ => {
                ins.set_x_scale(o.v[0]);
                ins.set_y_scale(o.v[1]);
                ins.set_z_scale(o.v[2]);
                if ins.x_scale() != o.v[0] || ins.y_scale() != o.v[1] || ins.z_scale() != o.v[2] {
                    return skip(
                        "UNSUPPORTED_ENTITY",
                        format!(
                            "acadrust's Insert scale setters rewrite a scale below 1e-12 in magnitude (asked for {:?}, stored {:?}), so the file would carry a different transform from the one authored",
                            o.v,
                            [ins.x_scale(), ins.y_scale(), ins.z_scale()]
                        ),
                    );
                }
            }
        }
    }
    Ok(ins)
}

fn build_layers(expected: &Value, doc: &mut CadDocument) -> Result<(), Skip> {
    for e in expected["entities"].as_array().unwrap() {
        let l = &e["layer"];
        let name = l["name"].as_str().unwrap();
        let mut layer = Layer::new(name);
        if !l["on"].as_bool().unwrap() {
            layer.turn_off();
        }
        if l["frozen"].as_bool().unwrap() {
            layer.freeze();
        }
        if let Err(err) = doc.layers.add(layer) {
            return skip("MALFORMED_FIXTURE", format!("layers.add: {err}"));
        }
        let mut curve = make_curve(e, None)?;
        curve.common_mut().layer = name.to_string();
        if let Err(err) = doc.add_entity(curve) {
            return skip("MALFORMED_FIXTURE", format!("add_entity: {err:?}"));
        }
    }
    Ok(())
}

fn build(id: &str, expected: &Value, params: &Value, version: DxfVersion) -> Result<CadDocument, Skip> {
    let ent = &expected["entities"][0];
    let mut doc = CadDocument::with_version(version);
    let dwg_entity = params.get("dwg_entity").and_then(|v| v.as_str());
    if ent.get("layer").is_some() {
        build_layers(expected, &mut doc)?;
        return Ok(doc);
    }
    let curve = make_curve(ent, dwg_entity)?;
    let structure = ent["structure"].as_str().unwrap();
    if structure == "CURVE_ONLY" {
        if let Err(e) = doc.add_entity(curve) {
            return skip("MALFORMED_FIXTURE", format!("add_entity: {e:?}"));
        }
        return Ok(doc);
    }
    // INSTANCE_PLUS_TRANSFORM: the base entity lives in a block, reached through INSERTs.
    let ops = parse_ops(params)?;
    // The composition is world = op0 * op1 * ... * base. The expected record keeps a chain of separate
    // transforms (transform_chain) whenever there is more than one op, so each op gets its own INSERT
    // level: collapsing them into one INSERT would carry the product and lose the chain.
    let nested = ops.len() > 1;
    let groups: Vec<Vec<&Op>> = if nested { ops.iter().map(|o| vec![o]).collect() } else { vec![ops.iter().collect()] };
    let names: Vec<String> = (1..=groups.len()).map(|i| format!("PROBE_{}_L{}", id.replace('-', "_").to_uppercase(), i)).collect();
    let handles: Vec<_> = names.iter().map(|n| add_block(&mut doc, n)).collect::<Result<_, _>>()?;
    // The base curve goes into the innermost block.
    let mut base = curve;
    base.common_mut().owner_handle = *handles.last().unwrap();
    if let Err(e) = doc.add_entity(base) {
        return skip("MALFORMED_FIXTURE", format!("add_entity: {e:?}"));
    }
    // Level i's INSERT references block i and sits in block i-1 (level 0 sits in model space).
    for (i, g) in groups.iter().enumerate() {
        let mut ins = EntityType::Insert(insert_for(&names[i], g)?);
        if i > 0 {
            ins.common_mut().owner_handle = handles[i - 1];
        }
        if let Err(e) = doc.add_entity(ins) {
            return skip("MALFORMED_FIXTURE", format!("add_entity: {e:?}"));
        }
    }
    Ok(doc)
}

fn sha_hex(b: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(b);
    h.finalize().iter().map(|x| format!("{x:02x}")).collect()
}

fn version_of(s: &str) -> DxfVersion {
    match s {
        "AC1015" => DxfVersion::AC1015,
        "AC1018" => DxfVersion::AC1018,
        "AC1021" => DxfVersion::AC1021,
        "AC1024" => DxfVersion::AC1024,
        "AC1027" => DxfVersion::AC1027,
        "AC1032" => DxfVersion::AC1032,
        _ => panic!("unsupported version {s}"),
    }
}

fn arg(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1).cloned())
}

fn cmd_write(args: &[String]) {
    let kt = PathBuf::from(arg(args, "--kt").unwrap());
    let params = PathBuf::from(arg(args, "--params").unwrap());
    let out = PathBuf::from(arg(args, "--out").unwrap());
    let ver = arg(args, "--version").unwrap_or_else(|| "AC1032".into());
    let mut ids: Vec<(String, PathBuf)> = Vec::new();
    fn walk(d: &Path, v: &mut Vec<(String, PathBuf)>) {
        let mut es: Vec<_> = fs::read_dir(d).unwrap().flatten().map(|e| e.path()).collect();
        es.sort();
        for p in es {
            if p.is_dir() {
                walk(&p, v)
            } else if p.extension().map(|x| x == "json").unwrap_or(false) {
                let j: Value = serde_json::from_str(&fs::read_to_string(&p).unwrap()).unwrap();
                v.push((j["id"].as_str().unwrap().to_string(), p));
            }
        }
    }
    walk(&params, &mut ids);
    ids.sort();
    let mut report = Vec::new();
    for (id, pf) in ids {
        let pj: Value = serde_json::from_str(&fs::read_to_string(&pf).unwrap()).unwrap();
        let ep = find_expected(&kt, &id).unwrap_or_else(|| panic!("no expected.math.json for {id}"));
        let ej: Value = serde_json::from_str(&fs::read_to_string(&ep).unwrap()).unwrap();
        match build(&id, &ej, &pj, version_of(&ver)) {
            Ok(doc) => {
                let dir = out.join(&id);
                fs::create_dir_all(&dir).unwrap();
                let f = dir.join("source.dwg");
                DwgWriter::write_to_file(&f, &doc).unwrap_or_else(|e| panic!("{id}: {e:?}"));
                let bytes = fs::read(&f).unwrap();
                report.push(json!({"id": id, "status": "WRITTEN", "dwg_sha256": sha_hex(&bytes), "bytes": bytes.len()}));
            }
            Err((reason, evidence)) => {
                report.push(json!({"id": id, "status": "SKIPPED", "reason": reason, "evidence": evidence}));
            }
        }
    }
    let rep = json!({"writer": "acadrust@0.5.5+d35691f", "dwg_version": ver, "fixtures": report});
    fs::write(out.join("write-report.json"), serde_json::to_string_pretty(&rep).unwrap() + "\n").unwrap();
    println!("{}", serde_json::to_string_pretty(&rep).unwrap());
}

fn v3(v: &Vector3) -> Value {
    json!([hex(v.x), hex(v.y), hex(v.z)])
}

fn dump_entity(e: &EntityType) -> Value {
    let mut v = dump_geometry(e);
    v["layer"] = json!(e.common().layer);
    v
}

fn dump_geometry(e: &EntityType) -> Value {
    match e {
        EntityType::Polyline2D(p) => json!({"type": "POLYLINE",
            "vertices": p.vertices.iter().map(|v| json!([hex(v.location.x), hex(v.location.y), hex(v.bulge)])).collect::<Vec<_>>(),
            "closed": p.is_closed(), "elevation": hex(p.elevation), "normal": v3(&p.normal)}),
        EntityType::Line(l) => json!({"type": "LINE", "start": v3(&l.start), "end": v3(&l.end)}),
        EntityType::Circle(c) => json!({"type": "CIRCLE", "center": v3(&c.center), "radius": hex(c.radius), "normal": v3(&c.normal)}),
        EntityType::Arc(a) => json!({"type": "ARC", "center": v3(&a.center), "radius": hex(a.radius), "start_angle": hex(a.start_angle), "end_angle": hex(a.end_angle), "normal": v3(&a.normal)}),
        EntityType::Ellipse(x) => json!({"type": "ELLIPSE", "center": v3(&x.center), "major_axis": v3(&x.major_axis), "ratio": hex(x.minor_axis_ratio), "start_param": hex(x.start_parameter), "end_param": hex(x.end_parameter), "normal": v3(&x.normal)}),
        EntityType::LwPolyline(p) => json!({"type": "LWPOLYLINE",
            "vertices": p.vertices.iter().map(|v| json!([hex(v.location.x), hex(v.location.y), hex(v.bulge)])).collect::<Vec<_>>(),
            "closed": p.is_closed, "elevation": hex(p.elevation), "normal": v3(&p.normal)}),
        EntityType::Spline(s) => json!({"type": "SPLINE", "degree": s.degree, "closed": s.flags.closed, "periodic": s.flags.periodic, "rational": s.flags.rational,
            "knots": s.knots.iter().map(|k| hex(*k)).collect::<Vec<_>>(),
            "control_points": s.control_points.iter().map(v3).collect::<Vec<_>>(),
            "weights": s.weights.iter().map(|k| hex(*k)).collect::<Vec<_>>(),
            "fit_point_count": s.fit_points.len(), "normal": v3(&s.normal)}),
        EntityType::Insert(i) => json!({"type": "INSERT", "block": i.block_name, "insert_point": v3(&i.insert_point),
            "scale": [hex(i.x_scale()), hex(i.y_scale()), hex(i.z_scale())], "rotation": hex(i.rotation), "normal": v3(&i.normal)}),
        other => {
            let d = format!("{:?}", other);
            json!({"type": "OTHER", "name": d.split('(').next().unwrap_or("?")})
        }
    }
}

fn dump_layers(doc: &CadDocument) -> Vec<Value> {
    let mut v: Vec<(String, Value)> = doc.layers.iter().map(|l| (l.name.clone(), json!({"name": l.name, "on": !l.is_off(), "frozen": l.is_frozen()}))).collect();
    v.sort_by(|a, b| a.0.cmp(&b.0));
    v.into_iter().map(|x| x.1).collect()
}

fn cmd_read(args: &[String]) {
    let dwg = PathBuf::from(arg(args, "--dwg").unwrap());
    let out = PathBuf::from(arg(args, "--out").unwrap());
    let bytes = fs::read(&dwg).unwrap();
    let doc = DwgReader::from_file(&dwg).unwrap_or_else(|e| panic!("acadrust could not read {}: {e:?}", dwg.display())).read().unwrap();
    let mut blocks: BTreeMap<String, Vec<Value>> = BTreeMap::new();
    for br in doc.block_records.iter() {
        let n = br.name().to_string();
        if n.starts_with("*Paper_Space") || n.starts_with("*") && n != "*Model_Space" {
            continue;
        }
        let es: Vec<Value> = doc.entities_in_block(&n).map(dump_entity).collect();
        blocks.insert(n, es);
    }
    let rec = json!({
        "schema": "pvec-gold/r0-open-dwg-read/2",
        "layers": dump_layers(&doc),
        "reader": READER_ID,
        "dwg_sha256": sha_hex(&bytes),
        "dwg_version": format!("{:?}", doc.version),
        "blocks": blocks.iter().map(|(k, v)| json!({"name": k, "entities": v})).collect::<Vec<_>>(),
    });
    fs::write(&out, serde_json::to_string_pretty(&rec).unwrap() + "\n").unwrap();
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.first().map(|s| s.as_str()) {
        Some("write") => cmd_write(&args),
        Some("read") => cmd_read(&args),
        _ => {
            eprintln!("usage: r0open write --kt DIR --params DIR --out DIR [--version V] | read --dwg F --out F");
            std::process::exit(2)
        }
    }
}
