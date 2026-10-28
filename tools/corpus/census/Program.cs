// Census: read one DWG with upstream ACadSharp's DwgReader and write what is in it, class by class.
//
//   Census <file.dwg> <out.json> <reader-id>
//
// It records the entity class of everything the reader returns (nothing is converted, repaired or
// dropped by this program), the block nesting depth, and the extent of the entities that report a
// bounding box. The negative suite compares the census to its expected classification, and the
// real-world corpus takes its per-fixture metrics from it.
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using ACadSharp;
using ACadSharp.Blocks;
using ACadSharp.Entities;
using ACadSharp.IO;
using ACadSharp.Tables;

static string H(double d) => "0x" + BitConverter.DoubleToInt64Bits(d).ToString("x16");

var path = args[0];
var bytes = File.ReadAllBytes(path);
CadDocument doc;
try { doc = DwgReader.Read(path); }
catch (Exception ex)
{
    var fail = new JsonObject
    {
        ["schema"] = "pvec-gold/dwg-census/1",
        ["reader"] = args[2],
        ["dwg_sha256"] = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
        ["read_error"] = ex.GetType().Name + ": " + ex.Message,
    };
    File.WriteAllText(args[1], fail.ToJsonString(new JsonSerializerOptions { WriteIndented = true }) + "\n");
    return;
}

double lo = double.PositiveInfinity, hi = double.NegativeInfinity, maxAbs = 0;
double[] mn = { double.PositiveInfinity, double.PositiveInfinity, double.PositiveInfinity };
double[] mx = { double.NegativeInfinity, double.NegativeInfinity, double.NegativeInfinity };
int bboxFailures = 0;

string ClassOf(Entity e)
{
    if (e is Insert i && i.Block != null && i.Block.Flags.HasFlag(BlockTypeFlags.XRef)) return "XRef";
    return e.GetType().Name;
}

var blocks = new JsonArray();
var histogram = new SortedDictionary<string, int>(StringComparer.Ordinal);
int total = 0, splines = 0;
var children = new Dictionary<string, List<string>>();
foreach (var br in doc.BlockRecords.OrderBy(b => b.Name, StringComparer.Ordinal))
{
    var n = br.Name;
    if (n.StartsWith("*") && n != "*Model_Space") continue;
    var es = new JsonArray();
    children[n] = new List<string>();
    foreach (var e in br.Entities)
    {
        var cls = ClassOf(e);
        var o = new JsonObject { ["type"] = cls, ["layer"] = e.Layer?.Name };
        if (e is Hatch h) o["gradient"] = h.GradientColor != null && h.GradientColor.Enabled;
        if (e is Insert ins && ins.Block != null) { o["block"] = ins.Block.Name; children[n].Add(ins.Block.Name); }
        es.Add(o);
        histogram[cls] = histogram.GetValueOrDefault(cls) + 1;
        total++;
        if (e is Spline) splines++;
        try
        {
            var bb = e.GetBoundingBox();
            if (bb.Min.X > bb.Max.X || double.IsInfinity(bb.Min.X) || double.IsNaN(bb.Min.X) || double.IsInfinity(bb.Max.X)) continue;
            mn[0] = Math.Min(mn[0], bb.Min.X); mn[1] = Math.Min(mn[1], bb.Min.Y); mn[2] = Math.Min(mn[2], bb.Min.Z);
            mx[0] = Math.Max(mx[0], bb.Max.X); mx[1] = Math.Max(mx[1], bb.Max.Y); mx[2] = Math.Max(mx[2], bb.Max.Z);
        }
        catch { bboxFailures++; }
    }
    blocks.Add(new JsonObject { ["name"] = n, ["xref"] = br.Flags.HasFlag(BlockTypeFlags.XRef), ["entities"] = es });
}

int Depth(string name, HashSet<string> seen)
{
    if (!children.TryGetValue(name, out var kids) || !seen.Add(name)) return 0;
    int d = 0;
    foreach (var k in kids) d = Math.Max(d, 1 + Depth(k, seen));
    seen.Remove(name);
    return d;
}

var hist = new JsonObject();
foreach (var kv in histogram) hist[kv.Key] = kv.Value;
var hasBox = !double.IsInfinity(mn[0]);
foreach (var v in mn.Concat(mx)) if (!double.IsInfinity(v)) maxAbs = Math.Max(maxAbs, Math.Abs(v));
var summary = new JsonObject
{
    ["entity_count"] = total,
    ["class_histogram"] = hist,
    ["max_block_depth"] = Depth("*Model_Space", new HashSet<string>()),
    ["spline_count"] = splines,
    ["max_abs_coordinate"] = hasBox ? maxAbs : null,
    ["extent"] = hasBox ? new JsonObject
    {
        ["min"] = new JsonArray(mn[0], mn[1], mn[2]),
        ["max"] = new JsonArray(mx[0], mx[1], mx[2]),
        ["largest_side"] = Math.Max(mx[0] - mn[0], Math.Max(mx[1] - mn[1], mx[2] - mn[2])),
    } : null,
    ["bounding_box_unavailable"] = bboxFailures,
};
var rec = new JsonObject
{
    ["schema"] = "pvec-gold/dwg-census/1",
    ["reader"] = args[2],
    ["dwg_sha256"] = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
    ["dwg_version"] = doc.Header.Version.ToString(),
    ["summary"] = summary,
    ["blocks"] = blocks,
};
File.WriteAllText(args[1], rec.ToJsonString(new JsonSerializerOptions { WriteIndented = true }) + "\n");
