// AcSharpDump: read one DWG with upstream ACadSharp and dump the entities the r0-open probes use, in the
// same schema (pvec-gold/r0-open-dwg-read/1) the acadrust side writes. Doubles are f64 bit patterns in hex.
//
//   AcSharpDump <file.dwg> <out.json> <reader-id>
//
// It reads with ACadSharp's own DwgReader and does nothing else with the file: no conversion, no repair.
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using ACadSharp;
using ACadSharp.Entities;
using ACadSharp.IO;
using ACadSharp.Tables;
using CSMath;

static string H(double d) => "0x" + BitConverter.DoubleToInt64Bits(d).ToString("x16");
static JsonArray V3(XYZ v) => new JsonArray(H(v.X), H(v.Y), H(v.Z));
static JsonArray Hs(IEnumerable<double> xs) { var a = new JsonArray(); foreach (var x in xs) a.Add(H(x)); return a; }

static JsonObject Dump(Entity e)
{
    var o = DumpGeometry(e);
    o["layer"] = e.Layer?.Name;
    return o;
}

static JsonObject DumpGeometry(Entity e)
{
    switch (e)
    {
        case Polyline2D p2:
            {
                var vs = new JsonArray();
                foreach (var v in p2.Vertices) vs.Add(new JsonArray(H(v.Location.X), H(v.Location.Y), H(v.Bulge)));
                return new JsonObject { ["type"] = "POLYLINE", ["vertices"] = vs, ["closed"] = p2.IsClosed, ["elevation"] = H(p2.Elevation), ["normal"] = V3(p2.Normal) };
            }
        case Arc a:
            return new JsonObject { ["type"] = "ARC", ["center"] = V3(a.Center), ["radius"] = H(a.Radius), ["start_angle"] = H(a.StartAngle), ["end_angle"] = H(a.EndAngle), ["normal"] = V3(a.Normal) };
        case Circle c:
            return new JsonObject { ["type"] = "CIRCLE", ["center"] = V3(c.Center), ["radius"] = H(c.Radius), ["normal"] = V3(c.Normal) };
        case Line l:
            return new JsonObject { ["type"] = "LINE", ["start"] = V3(l.StartPoint), ["end"] = V3(l.EndPoint) };
        case Ellipse x:
            return new JsonObject { ["type"] = "ELLIPSE", ["center"] = V3(x.Center), ["major_axis"] = V3(x.MajorAxisEndPoint), ["ratio"] = H(x.RadiusRatio), ["start_param"] = H(x.StartParameter), ["end_param"] = H(x.EndParameter), ["normal"] = V3(x.Normal) };
        case LwPolyline p:
            {
                var vs = new JsonArray();
                foreach (var v in p.Vertices) vs.Add(new JsonArray(H(v.Location.X), H(v.Location.Y), H(v.Bulge)));
                return new JsonObject { ["type"] = "LWPOLYLINE", ["vertices"] = vs, ["closed"] = p.IsClosed, ["elevation"] = H(p.Elevation), ["normal"] = V3(p.Normal) };
            }
        case Spline s:
            {
                var cps = new JsonArray();
                foreach (var c in s.ControlPoints) cps.Add(V3(c));
                return new JsonObject { ["type"] = "SPLINE", ["degree"] = s.Degree, ["closed"] = s.Flags.HasFlag(SplineFlags.Closed), ["periodic"] = s.Flags.HasFlag(SplineFlags.Periodic), ["rational"] = s.Flags.HasFlag(SplineFlags.Rational),
                    ["knots"] = Hs(s.Knots), ["control_points"] = cps, ["weights"] = Hs(s.Weights), ["fit_point_count"] = s.FitPoints.Count, ["normal"] = V3(s.Normal) };
            }
        case Insert i:
            return new JsonObject { ["type"] = "INSERT", ["block"] = i.Block?.Name, ["insert_point"] = V3(i.InsertPoint), ["scale"] = new JsonArray(H(i.XScale), H(i.YScale), H(i.ZScale)), ["rotation"] = H(i.Rotation), ["normal"] = V3(i.Normal) };
        default:
            return new JsonObject { ["type"] = "OTHER", ["name"] = e.GetType().Name };
    }
}

var path = args[0];
var bytes = File.ReadAllBytes(path);
var doc = DwgReader.Read(path);
var blocks = new JsonArray();
foreach (var br in doc.BlockRecords.OrderBy(b => b.Name, StringComparer.Ordinal))
{
    var n = br.Name;
    if (n.StartsWith("*") && n != "*Model_Space") continue;
    var es = new JsonArray();
    foreach (var e in br.Entities) es.Add(Dump(e));
    blocks.Add(new JsonObject { ["name"] = n, ["entities"] = es });
}
var layers = new JsonArray();
foreach (var l in doc.Layers.OrderBy(l => l.Name, StringComparer.Ordinal))
    layers.Add(new JsonObject { ["name"] = l.Name, ["on"] = l.IsOn, ["frozen"] = l.Flags.HasFlag(LayerFlags.Frozen) });
var rec = new JsonObject
{
    ["schema"] = "pvec-gold/r0-open-dwg-read/2",
    ["layers"] = layers,
    ["reader"] = args[2],
    ["dwg_sha256"] = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
    ["dwg_version"] = doc.Header.Version.ToString(),
    ["blocks"] = blocks,
};
File.WriteAllText(args[1], rec.ToJsonString(new JsonSerializerOptions { WriteIndented = true }) + "\n");
