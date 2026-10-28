// writer-acadsharp: write the r0-open probe DWGs with upstream ACadSharp's DwgWriter.
//
//   writer-acadsharp write --kt DIR --params DIR --out DIR [--version AC1032] [--fixed-header] [--leave-raw FIELD]
//
// It is the second writer family of the corpus (the first is acadrust, tools/r0-open/rust). Like that one it takes
// every number from the f64_hex fields of the authored expected.math.json records and, for the transform ops, from
// the decimal strings of the parameter files, and it never reads a converter output, a STEP file or a DWG. A probe it
// cannot store exactly is reported SKIPPED with the reason, never written as a lookalike.
//
// ACadSharp stamps four header fields on every file: the create and update times (local and universal) and two
// GUIDs (FingerPrintGuid, VersionGuid). They differ from run to run, so --fixed-header pins all of them to constants
// and --leave-raw FIELD leaves one of them alone, which is how the determinism note names the fields.
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using ACadSharp;
using ACadSharp.Entities;
using ACadSharp.IO;
using ACadSharp.Tables;
using CSMath;

const string WriterId = "ACadSharp@3.7.1+d7dc111";
const double Tau = 2 * Math.PI;

static string Arg(string[] a, string name) { int i = Array.IndexOf(a, name); return i >= 0 && i + 1 < a.Length ? a[i + 1] : null; }

static double Fx(JsonNode v) => BitConverter.Int64BitsToDouble((long)Convert.ToUInt64(v["f64_hex"].GetValue<string>().Substring(2), 16));
static XYZ P3(JsonNode v) { var a = v.AsArray(); return new XYZ(Fx(a[0]), Fx(a[1]), Fx(a[2])); }
static double Dec(JsonNode s) => double.Parse(s.GetValue<string>(), System.Globalization.CultureInfo.InvariantCulture);

static Entity MakeCurve(JsonNode e, string dwgEntity)
{
    string cls = e["class"].GetValue<string>();
    var g = e["geometry"]; var cl = e["closure"];
    switch (cls)
    {
        case "line":
            return new Line(P3(g["start"]), P3(g["end"]));
        case "circle":
        case "circular_arc":
            {
                var n = P3(g["normal"]); var x = P3(g["x_axis"]);
                if (!(n.X == 0 && n.Y == 0 && n.Z == 1 && x.X == 1 && x.Y == 0 && x.Z == 0))
                    throw new Skip("UNSUPPORTED_ENTITY", "the probe's x_axis is not the DWG arbitrary-axis default, and a DWG circle or arc cannot carry one");
                if (cls == "circle")
                    return new Circle { Center = P3(g["center"]), Radius = Fx(g["radius"]), Normal = n };
                double start = Fx(g["start_angle"]);
                double end = start + Fx(g["sweep_angle"]);
                if (!(start >= 0.0 && start < Tau)) throw new Skip("UNSUPPORTED_ENTITY", "start angle outside [0, 2pi)");
                if (end >= Tau) end -= Tau; // DWG stores the end angle reduced into [0, 2pi)
                return new Arc { Center = P3(g["center"]), Radius = Fx(g["radius"]), StartAngle = start, EndAngle = end, Normal = n };
            }
        case "ellipse":
        case "elliptical_arc":
            {
                var m = P3(g["major_axis"]); double a = Fx(g["semi_major"]); double b = Fx(g["semi_minor"]);
                double s = 0.0, t = Tau;
                if (cls == "elliptical_arc") { s = Fx(g["start_angle"]); t = s + Fx(g["sweep_angle"]); }
                return new Ellipse
                {
                    Center = P3(g["center"]),
                    MajorAxisEndPoint = new XYZ(m.X * a, m.Y * a, m.Z * a),
                    RadiusRatio = b / a,
                    StartParameter = s,
                    EndParameter = t,
                    Normal = P3(g["normal"]),
                };
            }
        case "polyline":
            {
                var vs = g["vertices"].AsArray(); var bs = g["bulges"].AsArray();
                double z0 = Fx(vs[0].AsArray()[2]);
                bool closed = cl["closed_by_endpoint"].GetValue<bool>();
                var pts = new List<(XYZ p, double b)>();
                for (int i = 0; i < vs.Count; i++)
                {
                    var v = P3(vs[i]);
                    if (v.Z != z0) throw new Skip("UNSUPPORTED_ENTITY", "an LWPOLYLINE has one elevation, the probe's vertices have different z");
                    pts.Add((v, Fx(bs[i])));
                }
                if (dwgEntity == "POLYLINE")
                {
                    var p2 = new Polyline2D { Elevation = z0 };
                    foreach (var (p, b) in pts) p2.Vertices.Add(new Vertex2D(new XYZ(p.X, p.Y, z0)) { Bulge = b });
                    if (closed) p2.IsClosed = true;
                    return p2;
                }
                var pl = new LwPolyline { Elevation = z0 };
                foreach (var (p, b) in pts) pl.Vertices.Add(new LwPolyline.Vertex(new XY(p.X, p.Y)) { Bulge = b });
                pl.IsClosed = closed; // the closing segment is implicit: the flag is the closure
                return pl;
            }
        case "bezier":
        case "bspline":
        case "nurbs":
            {
                int degree = g["degree"].GetValue<int>();
                var sp = new Spline { Degree = degree };
                foreach (var c in g["control_points"].AsArray()) sp.ControlPoints.Add(P3(c));
                if (cls == "bezier")
                {
                    double d0 = Fx(e["parameter_domain"]["start"]), d1 = Fx(e["parameter_domain"]["end"]);
                    for (int i = 0; i <= degree; i++) sp.Knots.Add(d0);
                    for (int i = 0; i <= degree; i++) sp.Knots.Add(d1);
                }
                else
                {
                    foreach (var kn in g["knots"].AsArray())
                        for (int i = 0; i < kn["multiplicity"].GetValue<int>(); i++) sp.Knots.Add(Fx(kn["value"]));
                }
                var fl = default(SplineFlags);
                if (cls == "nurbs")
                {
                    foreach (var w in g["weights"].AsArray()) sp.Weights.Add(Fx(w));
                    fl |= SplineFlags.Rational;
                }
                // closed-by-knots and closed-by-endpoint stay separate: only the knot closure is a flag.
                if (cl["closed_by_knots"].GetValue<bool>()) fl |= SplineFlags.Closed;
                if (cl["periodic"].GetValue<bool>()) fl |= SplineFlags.Periodic;
                sp.Flags = fl;
                return sp;
            }
        default:
            throw new Skip("UNSUPPORTED_ENTITY", $"no DWG form written for class {cls}");
    }
}

static List<Op> ParseOps(JsonNode prm)
{
    var ops = new List<Op>();
    foreach (var o in prm["ops"].AsArray())
    {
        string kind = o["op"].GetValue<string>();
        switch (kind)
        {
            case "translate": { var a = o["v"].AsArray(); ops.Add(new Op(kind, new[] { Dec(a[0]), Dec(a[1]), Dec(a[2]) })); break; }
            case "scale": { var a = o["s"].AsArray(); ops.Add(new Op(kind, new[] { Dec(a[0]), Dec(a[1]), Dec(a[2]) })); break; }
            case "rotate_z":
                {
                    double ang;
                    if (o["angle_rad"] != null) ang = Dec(o["angle_rad"]);
                    else { var cs = o["cos_sin"].AsArray(); ang = Math.Atan2(Dec(cs[1]), Dec(cs[0])); }
                    ops.Add(new Op(kind, new[] { ang, 0.0, 0.0 }));
                    break;
                }
            default:
                throw new Skip("UNSUPPORTED_ENTITY", $"op '{kind}' (a general matrix) has no single INSERT form: one INSERT carries translation, one rotation about the normal and three scales, and no shear. A three-level nested INSERT chain could carry its 2x2 part through a singular value decomposition, but those factors would be derived values compared under policy and not EXACT, and the probe's own truth is a rejection outcome that no reader-mapping check can exercise, so that was not attempted");
        }
    }
    return ops;
}

static Insert InsertFor(BlockRecord block, List<Op> ops)
{
    var ins = new Insert(block) { InsertPoint = XYZ.Zero };
    int rank = 0;
    foreach (var o in ops)
    {
        int r = o.Kind == "translate" ? 0 : o.Kind == "rotate_z" ? 1 : 2;
        if (r < rank) throw new Skip("UNSUPPORTED_ENTITY", "ops are not in translate, rotate, scale order, which is the only order one INSERT composes");
        rank = r;
        if (o.Kind == "translate") ins.InsertPoint = new XYZ(o.V[0], o.V[1], o.V[2]);
        else if (o.Kind == "rotate_z") ins.Rotation = o.V[0];
        else
        {
            if (o.V[0] == 0 || o.V[1] == 0 || o.V[2] == 0)
                throw new Skip("UNSUPPORTED_ENTITY", $"ACadSharp's Insert scale setters throw on a zero scale (asked for [{o.V[0]}, {o.V[1]}, {o.V[2]}]), so the file would not carry the transform that was authored");
            ins.XScale = o.V[0]; ins.YScale = o.V[1]; ins.ZScale = o.V[2];
        }
    }
    return ins;
}

static CadDocument NewDoc(ACadVersion version)
{
    var doc = new CadDocument();
    doc.Header.Version = version;
    return doc;
}

static CadDocument Build(string id, JsonNode expected, JsonNode prm, ACadVersion version)
{
    var ent = expected["entities"][0];
    var doc = NewDoc(version);
    string dwgEntity = prm["dwg_entity"]?.GetValue<string>();
    if (ent["layer"] != null)
    {
        foreach (var e in expected["entities"].AsArray())
        {
            var l = e["layer"];
            var layer = new Layer(l["name"].GetValue<string>());
            layer.IsOn = l["on"].GetValue<bool>();
            if (l["frozen"].GetValue<bool>()) layer.Flags |= LayerFlags.Frozen;
            doc.Layers.Add(layer);
            var curve = MakeCurve(e, null);
            curve.Layer = layer;
            doc.Entities.Add(curve);
        }
        return doc;
    }
    var baseCurve = MakeCurve(ent, dwgEntity);
    if (ent["structure"].GetValue<string>() == "CURVE_ONLY")
    {
        doc.Entities.Add(baseCurve);
        return doc;
    }
    // INSTANCE_PLUS_TRANSFORM: world = op0 * op1 * ... * base, one INSERT level per op when there is more than one.
    var ops = ParseOps(prm);
    bool nested = ops.Count > 1;
    var groups = nested ? ops.Select(o => new List<Op> { o }).ToList() : new List<List<Op>> { ops };
    string stem = "PROBE_" + id.Replace('-', '_').ToUpperInvariant();
    var blocks = Enumerable.Range(1, groups.Count).Select(i => new BlockRecord($"{stem}_L{i}")).ToList();
    blocks[^1].Entities.Add(baseCurve);
    // Level i's INSERT references block i and sits in block i-1 (level 0 sits in model space).
    for (int i = groups.Count - 1; i >= 0; i--)
    {
        var ins = InsertFor(blocks[i], groups[i]);
        if (i > 0) blocks[i - 1].Entities.Add(ins); else doc.Entities.Add(ins);
    }
    return doc;
}

// The eight fields ACadSharp stamps at write time. Two of the setters are internal, so I set them by reflection.

static void PinHeader(CadDocument doc, string leaveRaw)
{
    var t = new DateTime(2000, 1, 1, 0, 0, 0, DateTimeKind.Utc);
    foreach (var f in Types.Stamped)
    {
        if (f == leaveRaw) continue;
        if (f == "SummaryInfo.CreatedDate") { doc.SummaryInfo.CreatedDate = t; continue; }
        if (f == "SummaryInfo.ModifiedDate") { doc.SummaryInfo.ModifiedDate = t; continue; }
        var p = typeof(ACadSharp.Header.CadHeader).GetProperty(f, BindingFlags.Public | BindingFlags.Instance);
        if (p.PropertyType == typeof(DateTime)) p.GetSetMethod(true).Invoke(doc.Header, new object[] { t });
        else p.GetSetMethod(true).Invoke(doc.Header, new object[] { "00000000-0000-0000-0000-000000000000" });
    }
}

static ACadVersion VersionOf(string s) => s switch
{
    "AC1014" => ACadVersion.AC1014,
    "AC1015" => ACadVersion.AC1015,
    "AC1018" => ACadVersion.AC1018,
    "AC1024" => ACadVersion.AC1024,
    "AC1027" => ACadVersion.AC1027,
    "AC1032" => ACadVersion.AC1032,
    _ => throw new ArgumentException("unsupported version " + s),
};

static string Sha(byte[] b) => Convert.ToHexString(SHA256.HashData(b)).ToLowerInvariant();

if (args.Length == 0 || args[0] != "write")
{
    Console.Error.WriteLine("usage: writer-acadsharp write --kt DIR --params DIR --out DIR [--version V] [--fixed-header] [--leave-raw FIELD] [--only ID]");
    return 2;
}
string kt = Arg(args, "--kt"), prms = Arg(args, "--params"), outDir = Arg(args, "--out");
string ver = Arg(args, "--version") ?? "AC1032";
string leaveRaw = Arg(args, "--leave-raw");
string only = Arg(args, "--only");
bool fixedHeader = args.Contains("--fixed-header");

var ids = new List<(string id, string path)>();
foreach (var f in Directory.EnumerateFiles(prms, "*.json", SearchOption.AllDirectories).OrderBy(x => x, StringComparer.Ordinal))
    ids.Add((JsonNode.Parse(File.ReadAllText(f))["id"].GetValue<string>(), f));
ids.Sort((a, b) => string.CompareOrdinal(a.id, b.id));

var report = new JsonArray();
foreach (var (id, pf) in ids)
{
    if (only != null && id != only) continue;
    var pj = JsonNode.Parse(File.ReadAllText(pf));
    var ep = Directory.EnumerateFiles(kt, "expected.math.json", SearchOption.AllDirectories).First(p => Path.GetFileName(Path.GetDirectoryName(p)) == id);
    var ej = JsonNode.Parse(File.ReadAllText(ep));
    try
    {
        var doc = Build(id, ej, pj, VersionOf(ver));
        if (fixedHeader) PinHeader(doc, leaveRaw);
        var dir = Path.Combine(outDir, id);
        Directory.CreateDirectory(dir);
        var file = Path.Combine(dir, "source.dwg");
        DwgWriter.Write(file, doc);
        var bytes = File.ReadAllBytes(file);
        report.Add(new JsonObject { ["id"] = id, ["status"] = "WRITTEN", ["dwg_sha256"] = Sha(bytes), ["bytes"] = bytes.Length });
    }
    catch (Skip s)
    {
        report.Add(new JsonObject { ["id"] = id, ["status"] = "SKIPPED", ["reason"] = s.Reason, ["evidence"] = s.Evidence });
    }
}
var rep = new JsonObject { ["writer"] = WriterId, ["dwg_version"] = ver, ["fixtures"] = report };
Directory.CreateDirectory(outDir);
var text = rep.ToJsonString(new JsonSerializerOptions { WriteIndented = true }) + "\n";
File.WriteAllText(Path.Combine(outDir, "write-report.json"), text);
Console.Write(text);
return 0;

// (reason code from ADR 0006, evidence)
class Skip : Exception { public string Reason; public string Evidence; public Skip(string r, string e) : base(e) { Reason = r; Evidence = e; } }

record Op(string Kind, double[] V);

static class Types
{
    // The header fields ACadSharp stamps at write time. Two of the setters are internal, so I set them by reflection.
    public static readonly string[] Stamped = { "CreateDateTime", "UpdateDateTime", "UniversalCreateDateTime", "UniversalUpdateDateTime", "FingerPrintGuid", "VersionGuid", "SummaryInfo.CreatedDate", "SummaryInfo.ModifiedDate" };
}
