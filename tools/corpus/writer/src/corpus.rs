// Included into the same module as tools/r0-open/rust/src/main.rs (see main.rs), so the r0-open
// builders (make_curve, parse_ops, insert_for, add_block, cmd_write) are used as they stand.

use acadrust::types::Color;

fn param_files(dir: &Path) -> Vec<PathBuf> {
    let mut v: Vec<PathBuf> = fs::read_dir(dir)
        .map(|rd| rd.flatten().map(|e| e.path()).filter(|p| p.extension().map(|x| x == "json").unwrap_or(false)).collect())
        .unwrap_or_default();
    v.sort();
    v
}

fn load(p: &Path) -> Value {
    serde_json::from_str(&fs::read_to_string(p).unwrap_or_else(|e| panic!("{}: {e}", p.display()))).unwrap()
}

fn add(doc: &mut CadDocument, e: EntityType) -> Result<(), Skip> {
    doc.add_entity(e).map(|_| ()).map_err(|e| ("MALFORMED_FIXTURE".to_string(), format!("add_entity: {e:?}")))
}

/// Several entity classes in one model space, some of them reached through nested INSERTs. Entity i
/// of the authored record is built from entity i of the parameter file.
fn build_mixed(id: &str, expected: &Value, params: &Value, version: DxfVersion) -> Result<CadDocument, Skip> {
    let mut doc = CadDocument::with_version(version);
    let specs = params["entities"].as_array().unwrap();
    for (i, (e, s)) in expected["entities"].as_array().unwrap().iter().zip(specs).enumerate() {
        let curve = make_curve(e, None)?;
        if e["structure"].as_str() == Some("CURVE_ONLY") {
            add(&mut doc, curve)?;
            continue;
        }
        let ops = parse_ops(s)?;
        let nested = ops.len() > 1;
        let groups: Vec<Vec<&Op>> = if nested { ops.iter().map(|o| vec![o]).collect() } else { vec![ops.iter().collect()] };
        let names: Vec<String> = (1..=groups.len()).map(|l| format!("MIX_{}_E{}_L{}", id.replace('-', "_").to_uppercase(), i + 1, l)).collect();
        let handles: Vec<_> = names.iter().map(|n| add_block(&mut doc, n)).collect::<Result<_, _>>()?;
        let mut base = curve;
        base.common_mut().owner_handle = *handles.last().unwrap();
        add(&mut doc, base)?;
        for (l, g) in groups.iter().enumerate() {
            let mut ins = EntityType::Insert(insert_for(&names[l], g)?);
            if l > 0 {
                ins.common_mut().owner_handle = handles[l - 1];
            }
            add(&mut doc, ins)?;
        }
    }
    Ok(doc)
}

fn dec3(v: &Value) -> Vector3 {
    let a = v.as_array().expect("point");
    Vector3::new(dec(&a[0]), dec(&a[1]), dec(&a[2]))
}

/// Authored degenerate geometry, stored as the decimal strings say.
fn build_degenerate(params: &Value, version: DxfVersion) -> Result<CadDocument, Skip> {
    let mut doc = CadDocument::with_version(version);
    let e = match params["dwg_entity"].as_str().unwrap() {
        "LINE" => EntityType::Line(Line { start: dec3(&params["start"]), end: dec3(&params["end"]), ..Line::new() }),
        "CIRCLE" => EntityType::Circle(Circle { center: dec3(&params["center"]), radius: dec(&params["radius"]), ..Circle::new() }),
        "SPLINE" => {
            let mut sp = Spline::new();
            sp.degree = params["degree"].as_i64().unwrap() as i32;
            sp.control_points = params["control_points"].as_array().unwrap().iter().map(dec3).collect();
            sp.knots = params["knots"].as_array().unwrap().iter().map(dec).collect();
            EntityType::Spline(sp)
        }
        other => return skip("UNSUPPORTED_ENTITY", format!("no degenerate form for {other}")),
    };
    add(&mut doc, e)?;
    Ok(doc)
}

fn square() -> Vec<Vector2> {
    vec![Vector2::new(0.0, 0.0), Vector2::new(4.0, 0.0), Vector2::new(4.0, 3.0), Vector2::new(0.0, 3.0)]
}

fn hatch(gradient: bool) -> EntityType {
    let mut h = Hatch::solid();
    let mut bp = BoundaryPath::external();
    bp.add_edge(BoundaryEdge::Polyline(PolylineEdge::new(square(), true)));
    h.paths.push(bp);
    if gradient {
        h.is_solid = false;
        h.gradient_color.enabled = true;
        h.gradient_color.name = "LINEAR".to_string();
        h.gradient_color.add_color(0.0, Color::Index(1));
        h.gradient_color.add_color(1.0, Color::Index(5));
    }
    EntityType::Hatch(h)
}

const SAT: &str = "400 0 1 0\n";

/// One unsupported entity (or none at all), alone in an otherwise empty drawing.
fn build_negative(variant: &str, version: DxfVersion) -> Result<CadDocument, Skip> {
    let mut doc = CadDocument::with_version(version);
    let o = Vector3::new(0.0, 0.0, 0.0);
    let e = match variant {
        "empty" => return Ok(doc),
        "hatch" => hatch(false),
        "hatch-gradient" => hatch(true),
        "dimension" => EntityType::Dimension(Dimension::Linear(DimensionLinear::new(o, Vector3::new(5.0, 0.0, 0.0)))),
        "text" => EntityType::Text(Text::with_value("NOTE", Vector3::new(1.0, 1.0, 0.0))),
        "mtext" => {
            let mut m = MText::new();
            m.value = "NOTE".to_string();
            m.insertion_point = Vector3::new(1.0, 1.0, 0.0);
            EntityType::MText(m)
        }
        "solid3d" => EntityType::Solid3D(Solid3D::from_sat(SAT)),
        "mesh" => EntityType::Mesh(Mesh::from_triangles(
            vec![o, Vector3::new(1.0, 0.0, 0.0), Vector3::new(0.0, 1.0, 0.0)],
            &[(0, 1, 2)],
        )),
        "region" => EntityType::Region(Region::from_sat(SAT)),
        "proxy" => EntityType::Unknown(UnknownEntity::new("ACAD_PROXY_ENTITY")),
        "ole" => {
            let mut f = Ole2Frame::new();
            f.lower_right_corner = Vector3::new(5.0, 5.0, 0.0);
            f.envelope = OleFrameEnvelope::Geometry { marker: 1, extension_records: Vec::new() };
            EntityType::Ole2Frame(f)
        }
        "wipeout" => EntityType::Wipeout(Wipeout::from_corners(o, Vector3::new(4.0, 3.0, 0.0))),
        "table" => EntityType::Table(Table::default()),
        "image" => EntityType::RasterImage(RasterImage::new("scan.png", o, 100.0, 80.0)),
        "xref" => {
            let mut br = BlockRecord::new("SITE_XREF");
            br.flags.is_xref = true;
            br.xref_path = "site-plan.dwg".to_string();
            let h = doc.allocate_handle();
            br.set_handle(h);
            br.block_entity_handle = doc.allocate_handle();
            br.block_end_handle = doc.allocate_handle();
            if let Err(e) = doc.block_records.add(br) {
                return skip("MALFORMED_FIXTURE", format!("block_records.add: {e}"));
            }
            EntityType::Insert(Insert::new("SITE_XREF", o))
        }
        other => return skip("UNSUPPORTED_ENTITY", format!("no negative form for {other}")),
    };
    add(&mut doc, e)?;
    Ok(doc)
}

fn save(out: &Path, id: &str, doc: &CadDocument, report: &mut Vec<Value>) {
    let dir = out.join(id);
    fs::create_dir_all(&dir).unwrap();
    let f = dir.join("source.dwg");
    match DwgWriter::write_to_file(&f, doc) {
        Ok(()) => {
            let bytes = fs::read(&f).unwrap();
            report.push(json!({"id": id, "status": "WRITTEN", "dwg_sha256": sha_hex(&bytes), "bytes": bytes.len()}));
        }
        Err(e) => report.push(json!({"id": id, "status": "SKIPPED", "reason": "MALFORMED_FIXTURE", "evidence": format!("DwgWriter: {e:?}")})),
    }
}

fn write_group(out: &Path, ver: &str, report: Vec<Value>) {
    fs::create_dir_all(out).unwrap();
    let rep = json!({"writer": "acadrust@0.5.5+d35691f", "dwg_version": ver, "fixtures": report});
    fs::write(out.join("write-report.json"), serde_json::to_string_pretty(&rep).unwrap() + "\n").unwrap();
}

fn skipped(id: &str, (reason, evidence): Skip) -> Value {
    json!({"id": id, "status": "SKIPPED", "reason": reason, "evidence": evidence})
}

pub fn run() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.first().map(|s| s.as_str()) == Some("read") {
        return cmd_read(&args);
    }
    if args.first().map(|s| s.as_str()) != Some("all") {
        eprintln!("usage: corpus-writer all --root REPO --out DIR [--version V] | read --dwg FILE --out FILE");
        std::process::exit(2);
    }
    let root = PathBuf::from(arg(&args, "--root").unwrap());
    let out = PathBuf::from(arg(&args, "--out").unwrap());
    let ver = arg(&args, "--version").unwrap_or_else(|| "AC1032".into());
    let kt = root.join("fixtures/edge");
    let kt_mixed = root.join("fixtures/mixed");
    let params = root.join("tools/authoring/corpus-params");

    // edge: ordinary single-entity probes, through the r0-open writer unchanged.
    let edge_args: Vec<String> = ["write", "--kt", kt.to_str().unwrap(), "--params", params.join("edge").to_str().unwrap(), "--out", out.join("edge").to_str().unwrap(), "--version", &ver]
        .iter().map(|s| s.to_string()).collect();
    cmd_write(&edge_args);

    let mut rep = Vec::new();
    for p in param_files(&params.join("mixed")) {
        let pj = load(&p);
        let id = pj["id"].as_str().unwrap().to_string();
        let ep = find_expected(&kt_mixed, &id).unwrap_or_else(|| panic!("no expected.math.json for {id}"));
        match build_mixed(&id, &load(&ep), &pj, version_of(&ver)) {
            Ok(doc) => save(&out.join("mixed"), &id, &doc, &mut rep),
            Err(s) => rep.push(skipped(&id, s)),
        }
    }
    write_group(&out.join("mixed"), &ver, rep);

    let mut rep = Vec::new();
    for p in param_files(&params.join("degenerate")) {
        let pj = load(&p);
        let id = pj["id"].as_str().unwrap().to_string();
        match build_degenerate(&pj, version_of(&ver)) {
            Ok(doc) => save(&out.join("degenerate"), &id, &doc, &mut rep),
            Err(s) => rep.push(skipped(&id, s)),
        }
    }
    write_group(&out.join("degenerate"), &ver, rep);

    let mut rep = Vec::new();
    for p in param_files(&params.join("negative")) {
        let pj = load(&p);
        let id = pj["id"].as_str().unwrap().to_string();
        match build_negative(pj["variant"].as_str().unwrap(), version_of(&ver)) {
            Ok(doc) => save(&out.join("negative"), &id, &doc, &mut rep),
            Err(s) => rep.push(skipped(&id, s)),
        }
    }
    write_group(&out.join("negative"), &ver, rep);
}
