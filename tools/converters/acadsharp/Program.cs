// dwg2step-acadsharp: DWG to AP242 Part 21, with ACadSharp's DwgReader as the only decoder.
//
//   dwg2step-acadsharp --in source.dwg --out primary.step [--status primary.status.json]
//
// Writes one status record (schema/converter-status.schema.json) every run, ok or not. The STEP file is
// written under a temporary name and renamed into place only after it passes the checks below, so a failed
// run leaves no output, not even a stale one from an earlier run.
//
// Exit codes (the ones docs/converters/*-qualification.md share across converters):
//   0 ok  10 bad arguments  11 input missing or unreadable  12 input malformed  13 DWG version unsupported
//   15 conversion failed  16 output not produced  17 declared schema not AP242  20 internal error
//   (14, licence unavailable, cannot happen here: there is no licence)
using System.Diagnostics;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using ACadSharp;
using ACadSharp.IO;
using ACadSharp.Types.Units;

namespace Dwg2Step;

static class Program
{
    // Stub until the schema change of ADR 0009 (issue 47) turns `converter` into a string id.
    const string ConverterId = "acadsharp-dwg2step";
    const string ProductName = "ACadSharp";
    // The pinned upstream commit the image builds (the Dockerfile checks the clone against ACADSHARP_COMMIT).
    const string ProductVersion = "3.7.1+d7dc111";
    const string ToolVersion = "1";
    static readonly string[] SupportedMagic = { "AC1014", "AC1015", "AC1018", "AC1021", "AC1024", "AC1027", "AC1032" };

    static int Main(string[] args)
    {
        var clock = Stopwatch.StartNew();
        string inPath = null, outPath = null, statusPath = null, policyPath = null;
        bool badArgs = false;
        for (int i = 0; i < args.Length; i++)
        {
            string a = args[i];
            string next() => i + 1 < args.Length ? args[++i] : null;
            if (a == "--in") inPath = next();
            else if (a == "--out") outPath = next();
            else if (a == "--status") statusPath = next();
            else if (a == "--policy") policyPath = next();
            else badArgs = true;
        }
        if (badArgs || string.IsNullOrEmpty(inPath) || string.IsNullOrEmpty(outPath))
        {
            statusPath ??= (outPath != null ? Regex.Replace(outPath, @"\.step$", "") + ".status.json" : "unset.status.json");
            var rec = new Record { Input = inPath ?? "", Output = outPath ?? "unset.step", Status = statusPath, Clock = clock };
            return Fail(rec, 10, "BAD_ARGUMENTS", "usage: dwg2step-acadsharp --in source.dwg --out primary.step [--status file]");
        }
        statusPath ??= Regex.Replace(outPath, @"\.step$", "") + ".status.json";
        var r = new Record { Input = inPath, Output = outPath, Status = statusPath, Clock = clock };
        string tmp = outPath + ".partial." + Environment.ProcessId;
        try
        {
            SafeDelete(outPath);   // never leave a stale output behind a failed run
            if (!File.Exists(inPath)) return Fail(r, 11, "INPUT_UNREADABLE", "cannot read input");
            byte[] bytes;
            try { bytes = File.ReadAllBytes(inPath); }
            catch (Exception e) { return Fail(r, 11, "INPUT_UNREADABLE", "cannot read input: " + e.Message); }
            r.InputSha = Hex(SHA256.HashData(bytes));

            string magic = bytes.Length >= 6 ? Encoding.ASCII.GetString(bytes, 0, 6) : "";
            if (!Regex.IsMatch(magic, "^AC[0-9]{4}$") && !magic.StartsWith("AC1.") && !magic.StartsWith("MC0."))
                return Fail(r, 12, "INPUT_MALFORMED", "not a DWG file: no AC10xx version header");
            if (Array.IndexOf(SupportedMagic, magic) < 0)
                return Fail(r, 13, "DWG_VERSION_UNSUPPORTED", "DWG version " + magic + " is not read by ACadSharp's DwgReader");

            double rel = LoadRel(policyPath, out string policyVersion);

            CadDocument doc;
            var notes = new List<string>();
            try
            {
                var cfg = new DwgReaderConfiguration { CrcCheck = true, Failsafe = false };
                using var ms = new MemoryStream(bytes);
                doc = DwgReader.Read(ms, cfg, (s, e) => { if (notes.Count < 50) notes.Add("reader " + e.NotificationType + ": " + e.Message); });
            }
            catch (Exception e)
            {
                return Fail(r, 12, "INPUT_MALFORMED", "DwgReader: " + e.GetType().Name + ": " + e.Message);
            }
            r.Warnings.AddRange(notes);

            var flat = new Flattener(rel);
            try { flat.Run(doc); }
            catch (ConvertException ce) { return Fail(r, ce.Code, ce.Klass, ce.Message); }
            foreach (var kv in flat.Skipped) r.Warnings.Add("skipped " + kv.Value + " entity(ies) of type " + kv.Key);
            if (flat.Curves.Count == 0) return Fail(r, 15, "CONVERSION_FAILED", "no supported curve in model space");

            string unit = LengthUnit(doc.Header.InsUnits, r.Warnings, out bool unitOk);
            if (!unitOk) return Fail(r, 15, "CONVERSION_FAILED", "drawing unit " + doc.Header.InsUnits + " is not supported (metre, millimetre, centimetre, kilometre and unitless are)");

            var w = new Step21();
            try { foreach (var c in flat.Curves) w.Write(c); }
            catch (ConvertException ce) { return Fail(r, ce.Code, ce.Klass, ce.Message); }

            string stamp = TimeStamp();
            string desc = "dwg2step-acadsharp " + ToolVersion + "; " + ProductName + " " + ProductVersion + "; " + policyVersion + "; source sha256 " + r.InputSha;
            string text = w.Document(Path.GetFileName(outPath), stamp, desc, unit);

            File.WriteAllText(tmp, text, new UTF8Encoding(false));
            if (new FileInfo(tmp).Length == 0) return Fail(r, 16, "OUTPUT_NOT_WRITTEN", "converter wrote no output");
            var m = Regex.Match(text, @"FILE_SCHEMA\s*\(\s*\(\s*'([^']*)'");
            r.Declared = m.Success ? m.Groups[1].Value : null;
            if (r.Declared == null || !(r.Declared.Contains("AP242") || r.Declared.Contains("10303 442")))
                return Fail(r, 17, "SCHEMA_NOT_AP242", "declared schema is '" + (r.Declared ?? "none") + "', not AP242");
            try { File.Move(tmp, outPath, false); }
            catch (Exception e) { return Fail(r, 16, "OUTPUT_NOT_WRITTEN", "could not move output into place: " + e.Message); }
            r.OutputSha = Hex(SHA256.HashData(File.ReadAllBytes(outPath)));
            return Done(r, 0, null, null);
        }
        catch (Exception e)
        {
            return Fail(r, 20, "INTERNAL", e.GetType().Name + ": " + e.Message);
        }
        finally
        {
            SafeDelete(tmp);
        }
    }

    // NP-19's REL comes from the vendored policy file the image carries; there is no default.
    static double LoadRel(string path, out string version)
    {
        path ??= Environment.GetEnvironmentVariable("DWG2STEP_POLICY") ?? "/opt/dwg2step/policy/pvec-numeric-policy.v1.json";
        using var d = JsonDocument.Parse(File.ReadAllText(path));
        version = d.RootElement.GetProperty("policy_version").GetString();
        return d.RootElement.GetProperty("constants").GetProperty("REL").GetDouble();
    }

    static string LengthUnit(UnitsType u, List<string> warnings, out bool ok)
    {
        ok = true;
        switch (u)
        {
            case UnitsType.Meters: return "$,.METRE.";
            case UnitsType.Millimeters: return ".MILLI.,.METRE.";
            case UnitsType.Centimeters: return ".CENTI.,.METRE.";
            case UnitsType.Kilometers: return ".KILO.,.METRE.";
            case UnitsType.Unitless:
                warnings.Add("INSUNITS is unitless: values are written unscaled and labelled metre");
                return "$,.METRE.";
            default: ok = false; return null;
        }
    }

    static string TimeStamp()
    {
        var epoch = Environment.GetEnvironmentVariable("SOURCE_DATE_EPOCH");
        var t = long.TryParse(epoch, NumberStyles.None, CultureInfo.InvariantCulture, out long s) ? DateTimeOffset.FromUnixTimeSeconds(s) : DateTimeOffset.UtcNow;
        return t.UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss", CultureInfo.InvariantCulture);
    }

    static string Hex(byte[] b) => Convert.ToHexString(b).ToLowerInvariant();
    static void SafeDelete(string p) { try { if (p != null && File.Exists(p)) File.Delete(p); } catch { } }

    // ---- the status record ----------------------------------------------------------------------

    sealed class Record
    {
        public string Input, Output, Status, InputSha, OutputSha, Declared;
        public Stopwatch Clock;
        public List<string> Warnings = new();
    }

    static int Fail(Record r, int code, string klass, string message)
    {
        SafeDelete(r.Output);
        return Done(r, code, klass, message);
    }

    static int Done(Record r, int code, string klass, string message)
    {
        string J(string s) => JsonSerializer.Serialize(s);
        string N(string s) => s == null ? "null" : J(s);
        var sb = new StringBuilder();
        sb.Append("{\n  \"schema_version\": \"pvec-gold/converter-status/1\",\n");
        sb.Append("  \"converter\": ").Append(J(ConverterId)).Append(",\n");
        sb.Append("  \"status\": ").Append(code == 0 ? "\"OK\"" : "\"ERROR\"").Append(",\n");
        sb.Append("  \"exit_code\": ").Append(code).Append(",\n");
        sb.Append("  \"input\": {\"path\": ").Append(J(r.Input)).Append(", \"sha256\": ").Append(N(r.InputSha)).Append("},\n");
        sb.Append("  \"output\": ").Append(code == 0 ? "{\"path\": " + J(r.Output) + ", \"sha256\": " + J(r.OutputSha) + "}" : "null").Append(",\n");
        sb.Append("  \"product\": {\"name\": ").Append(J(ProductName)).Append(", \"version\": ").Append(J(ProductVersion)).Append("},\n");
        sb.Append("  \"declared_schema\": ").Append(N(code == 0 ? r.Declared : null)).Append(",\n");
        sb.Append("  \"wall_time_seconds\": ").Append(J(r.Clock.Elapsed.TotalSeconds.ToString("F3", CultureInfo.InvariantCulture))).Append(",\n");
        sb.Append("  \"warnings\": [").Append(string.Join(", ", r.Warnings.Select(J))).Append("],\n");
        sb.Append("  \"error\": ").Append(code == 0 ? "null" : "{\"code\": " + code + ", \"class\": " + J(klass) + ", \"message\": " + J(message.Length > 400 ? message[..400] : message) + "}").Append("\n}\n");
        try
        {
            var dir = Path.GetDirectoryName(Path.GetFullPath(r.Status));
            if (dir != null) Directory.CreateDirectory(dir);
            File.WriteAllText(r.Status, sb.ToString(), new UTF8Encoding(false));
        }
        catch (Exception e) { Console.Error.WriteLine("cannot write the status record: " + e.Message); }
        if (code != 0) Console.Error.WriteLine(message);
        return code;
    }
}
