// Flatten: walk model space, expand every INSERT chain with exact affine composition, and hand back world-space
// curves in the small vocabulary Step21 writes (line, circle/ellipse arc, B-spline).
//
// What is exact and what is derived: coordinates, radii, knots, weights and angles a DWG stores are carried to
// the output untouched whenever no INSERT is involved. Under an INSERT the affine map is applied to the stored
// values (a line's ends, a spline's poles, a conic's centre and conjugate axes), which is exact in real
// arithmetic. A circle under a uniform scale stays a circle. Anything else (a non-uniform scale, a shear
// from the composition of a rotation after a scale) is an ellipse found from the two mapped conjugate
// semi-diameters. A reflection flips the placement frame so the parameter direction of an arc is kept.
using System.Globalization;
using ACadSharp;
using ACadSharp.Entities;
using ACadSharp.Tables;

namespace Dwg2Step;

public readonly record struct V3(double X, double Y, double Z)
{
    public static V3 operator +(V3 a, V3 b) => new(a.X + b.X, a.Y + b.Y, a.Z + b.Z);
    public static V3 operator -(V3 a, V3 b) => new(a.X - b.X, a.Y - b.Y, a.Z - b.Z);
    public static V3 operator *(V3 a, double s) => new(a.X * s, a.Y * s, a.Z * s);
    public static V3 operator /(V3 a, double s) => new(a.X / s, a.Y / s, a.Z / s);
    public double Dot(V3 b) => X * b.X + Y * b.Y + Z * b.Z;
    public V3 Cross(V3 b) => new(Y * b.Z - Z * b.Y, Z * b.X - X * b.Z, X * b.Y - Y * b.X);
    public double Length => Math.Sqrt(Dot(this));
    public V3 Unit() { var l = Length; return new V3(X / l, Y / l, Z / l); }
    public static V3 From(CSMath.XYZ v) => new(v.X, v.Y, v.Z);
}

/// <summary>x -> L x + T, with the facts the output needs about L.</summary>
public sealed class Affine
{
    public readonly double[,] L = new double[3, 3];
    public V3 T;
    public bool Identity = true;      // no INSERT on the path: nothing may be recomputed
    public bool Similar = true;       // every INSERT on the path scales its three axes by one magnitude
    public double Scale = 1.0;        // product of those magnitudes, from 1.0 so an unscaled path leaves radii alone
    public bool Reflects;             // odd number of negative scales

    public static Affine Eye()
    {
        var a = new Affine();
        a.L[0, 0] = a.L[1, 1] = a.L[2, 2] = 1.0;
        return a;
    }

    public V3 Apply(V3 p) => Identity ? p : Linear(p) + T;
    public V3 Linear(V3 v) => new(
        L[0, 0] * v.X + L[0, 1] * v.Y + L[0, 2] * v.Z,
        L[1, 0] * v.X + L[1, 1] * v.Y + L[1, 2] * v.Z,
        L[2, 0] * v.X + L[2, 1] * v.Y + L[2, 2] * v.Z);

    /// <summary>this (the parent path) after child: x -> this(child(x)).</summary>
    public Affine Then(Affine child)
    {
        var r = new Affine { Identity = false, Similar = Similar && child.Similar, Scale = Scale * child.Scale, Reflects = Reflects ^ child.Reflects };
        for (int i = 0; i < 3; i++)
            for (int j = 0; j < 3; j++)
                r.L[i, j] = L[i, 0] * child.L[0, j] + L[i, 1] * child.L[1, j] + L[i, 2] * child.L[2, j];
        r.T = Linear(child.T) + T;
        return r;
    }
}

public abstract record Curve(string Layer);
public sealed record LineCurve(V3 P0, V3 P1, string Layer) : Curve(Layer);

/// <summary>Circle or ellipse, full or trimmed. Circle: A is the radius and B is ignored.</summary>
public sealed record ConicCurve(V3 Center, V3 Normal, V3 XDir, double A, double B, bool IsCircle, double T0, double T1, bool Full, string Layer) : Curve(Layer);

/// <summary>B-spline; Weights is null when the spline is not rational. Knots is the full vector as written.</summary>
public sealed record SplineCurve(int Degree, List<V3> Poles, List<double> Knots, List<double> Weights, bool Closed, string Layer) : Curve(Layer);

public sealed class ConvertException : Exception
{
    public readonly int Code;
    public readonly string Klass;
    public ConvertException(int code, string klass, string message) : base(message) { Code = code; Klass = klass; }
}

public sealed class Flattener
{
    const int MaxDepth = 64;
    readonly double _rel;   // NP-19's REL, read from the vendored policy
    public readonly List<Curve> Curves = new();
    public readonly SortedDictionary<string, int> Skipped = new(StringComparer.Ordinal);
    static readonly double TwoPi = Math.PI * 2.0;

    readonly double _toMetre;   // 1.0 unless the drawing's unit has to be scaled to metre (inches, feet)

    public Flattener(double rel, double toMetre = 1.0) { _rel = rel; _toMetre = toMetre; }

    public void Run(CadDocument doc)
    {
        var model = doc.ModelSpace;
        // A unit scale is a uniform scale at the root of every path, so a circle stays a circle with radius r * s and
        // nothing else in the flattening needs to know about units. At 1.0 the root stays the identity and no stored
        // value is recomputed.
        var root = Affine.Eye();
        if (_toMetre != 1.0)
        {
            root.L[0, 0] = root.L[1, 1] = root.L[2, 2] = _toMetre;
            root.Identity = false;
            root.Scale = _toMetre;
        }
        Walk(model, root, 0, new HashSet<string>(StringComparer.Ordinal));
    }

    void Walk(BlockRecord br, Affine m, int depth, HashSet<string> open)
    {
        foreach (var e in br.Entities)
            Emit(e, m, depth, open);
    }

    void Emit(Entity e, Affine m, int depth, HashSet<string> open)
    {
        string layer = e.Layer?.Name ?? "0";
        switch (e)
        {
            case Insert ins: Expand(ins, m, depth, open); break;
            case Line l: Curves.Add(new LineCurve(m.Apply(V3.From(l.StartPoint)), m.Apply(V3.From(l.EndPoint)), layer)); break;
            case Arc a: AddArc(a, m, layer); break;
            case Circle c: AddCircle(c, m, layer); break;
            case Ellipse x: AddEllipse(x, m, layer); break;
            case LwPolyline p:
                {
                    var pts = p.Vertices.Select(v => (new V3(v.Location.X, v.Location.Y, p.Elevation), v.Bulge)).ToList();
                    AddPolyline(pts, p.IsClosed, V3.From(p.Normal), m, layer);
                    break;
                }
            case Polyline2D p2:
                {
                    var pts = p2.Vertices.Select(v => (new V3(v.Location.X, v.Location.Y, p2.Elevation), v.Bulge)).ToList();
                    AddPolyline(pts, p2.IsClosed, V3.From(p2.Normal), m, layer);
                    break;
                }
            case Polyline3D p3:
                {
                    var pts = p3.Vertices.Select(v => (V3.From(v.Location), 0.0)).ToList();
                    AddPolyline(pts, p3.IsClosed, new V3(0, 0, 1), m, layer);
                    break;
                }
            case Spline s: AddSpline(s, m, layer); break;
            default:
                var n = e.GetType().Name;
                Skipped[n] = Skipped.GetValueOrDefault(n) + 1;
                break;
        }
    }

    // ---- INSERT ---------------------------------------------------------------------------------

    void Expand(Insert ins, Affine parent, int depth, HashSet<string> open)
    {
        if (ins.Block == null) throw new ConvertException(15, "CONVERSION_FAILED", "INSERT without a block record");
        if (ins.IsMultiple) throw new ConvertException(15, "CONVERSION_FAILED", "MINSERT arrays are not supported (block " + ins.Block.Name + ")");
        if (depth >= MaxDepth) throw new ConvertException(15, "CONVERSION_FAILED", "INSERT nesting deeper than " + MaxDepth);
        var name = ins.Block.Name;
        if (!open.Add(name)) throw new ConvertException(15, "CONVERSION_FAILED", "block " + name + " contains itself");
        var local = InsertMap(ins);
        var m = parent.Then(local);
        RefuseSingular(m, name);
        Walk(ins.Block, m, depth + 1, open);
        open.Remove(name);
    }

    // p_parent = W (R S (p - base) + insert_point), W the arbitrary-axis matrix of the INSERT's normal
    static Affine InsertMap(Insert ins)
    {
        var (ax, ay, az) = ArbitraryAxes(V3.From(ins.Normal));
        double sx = ins.XScale, sy = ins.YScale, sz = ins.ZScale;
        double c = Math.Cos(ins.Rotation), s = Math.Sin(ins.Rotation);
        // R S in OCS
        var rs = new double[3, 3] { { c * sx, -s * sy, 0 }, { s * sx, c * sy, 0 }, { 0, 0, sz } };
        var w = new double[3, 3] { { ax.X, ay.X, az.X }, { ax.Y, ay.Y, az.Y }, { ax.Z, ay.Z, az.Z } };
        var a = new Affine { Identity = false };
        for (int i = 0; i < 3; i++)
            for (int j = 0; j < 3; j++)
                a.L[i, j] = w[i, 0] * rs[0, j] + w[i, 1] * rs[1, j] + w[i, 2] * rs[2, j];
        var bp = V3.From(ins.Block.BlockEntity?.BasePoint ?? CSMath.XYZ.Zero);
        var ip = V3.From(ins.InsertPoint);
        var inner = new V3(rs[0, 0] * bp.X + rs[0, 1] * bp.Y + rs[0, 2] * bp.Z, rs[1, 0] * bp.X + rs[1, 1] * bp.Y + rs[1, 2] * bp.Z, rs[2, 0] * bp.X + rs[2, 1] * bp.Y + rs[2, 2] * bp.Z);
        var off = ip - inner;
        a.T = new V3(w[0, 0] * off.X + w[0, 1] * off.Y + w[0, 2] * off.Z, w[1, 0] * off.X + w[1, 1] * off.Y + w[1, 2] * off.Z, w[2, 0] * off.X + w[2, 1] * off.Y + w[2, 2] * off.Z);
        double mx = Math.Abs(sx);
        a.Similar = mx == Math.Abs(sy) && mx == Math.Abs(sz);
        a.Scale = a.Similar ? mx : 1.0;
        a.Reflects = (sx < 0) ^ (sy < 0) ^ (sz < 0);
        return a;
    }

    // NP-19: refuse an affine map whose |ad - bc| <= REL * big^2 (the 2D part), or that is not finite.
    void RefuseSingular(Affine m, string block)
    {
        double a = m.L[0, 0], b = m.L[0, 1], c = m.L[1, 0], d = m.L[1, 1];
        double big = Math.Max(Math.Max(Math.Abs(a), Math.Abs(b)), Math.Max(Math.Abs(c), Math.Abs(d)));
        double det = Math.Abs(a * d - b * c);
        if (!double.IsFinite(det) || det <= _rel * big * big)
            throw new ConvertException(15, "CONVERSION_FAILED",
                "NEAR_SINGULAR_TRANSFORM: the composed map of block " + block + " has |ad - bc| = " + det.ToString("R", CultureInfo.InvariantCulture) + " with big = " + big.ToString("R", CultureInfo.InvariantCulture) + " (PVec numeric policy NP-19)");
    }

    // ---- OCS ------------------------------------------------------------------------------------

    public static (V3 x, V3 y, V3 z) ArbitraryAxes(V3 n)
    {
        n = n.Unit();
        // the 1/64 rule of the arbitrary axis algorithm
        double lim = 1.0 / 64.0;
        var x = (Math.Abs(n.X) < lim && Math.Abs(n.Y) < lim) ? new V3(0, 1, 0).Cross(n) : new V3(0, 0, 1).Cross(n);
        x = x.Unit();
        var y = n.Cross(x);
        return (x, y, n);
    }

    static V3 OcsPoint(V3 p, V3 x, V3 y, V3 z) => new(p.X * x.X + p.Y * y.X + p.Z * z.X, p.X * x.Y + p.Y * y.Y + p.Z * z.Y, p.X * x.Z + p.Y * y.Z + p.Z * z.Z);

    // ---- conics ---------------------------------------------------------------------------------

    void AddCircle(Circle c, Affine m, string layer)
    {
        var (x, _, z) = ArbitraryAxes(V3.From(c.Normal));
        var k = new ConicCurve(Ocs(V3.From(c.Center), V3.From(c.Normal)), z, x, c.Radius, c.Radius, true, 0.0, TwoPi, true, layer);
        Curves.Add(MapConic(k, m));
    }

    void AddArc(Arc a, Affine m, string layer)
    {
        var (x, _, z) = ArbitraryAxes(V3.From(a.Normal));
        double t0 = a.StartAngle, t1 = a.EndAngle;
        if (t1 <= t0) t1 += TwoPi;
        var k = new ConicCurve(Ocs(V3.From(a.Center), V3.From(a.Normal)), z, x, a.Radius, a.Radius, true, t0, t1, false, layer);
        Curves.Add(MapConic(k, m));
    }

    static V3 Ocs(V3 p, V3 normal)
    {
        var (x, y, z) = ArbitraryAxes(normal);
        return OcsPoint(p, x, y, z);
    }

    void AddEllipse(Ellipse e, Affine m, string layer)
    {
        var u = V3.From(e.MajorAxisEndPoint);
        var n = V3.From(e.Normal).Unit();
        double a = u.Length;
        bool full = e.StartParameter == 0.0 && e.EndParameter == TwoPi;
        double t0 = e.StartParameter, t1 = e.EndParameter;
        if (!full && t1 <= t0) t1 += TwoPi;
        var k = new ConicCurve(V3.From(e.Center), n, u / a, a, e.RadiusRatio * a, false, full ? 0.0 : t0, full ? TwoPi : t1, full, layer);
        Curves.Add(MapConic(k, m));
    }

    /// <summary>Apply an affine map to a conic, exactly: see the header of this file.</summary>
    static ConicCurve MapConic(ConicCurve k, Affine m)
    {
        if (m.Identity) return k;
        var centre = m.Apply(k.Center);
        var yDir = k.Normal.Cross(k.XDir);
        if (k.IsCircle && m.Similar)
        {
            var xd = m.Linear(k.XDir).Unit();
            var nz = m.Linear(k.Normal).Unit();
            if (m.Reflects) nz = nz * -1.0;
            return k with { Center = centre, Normal = nz, XDir = xd, A = k.A * m.Scale, B = k.A * m.Scale };
        }
        var p = m.Linear(k.XDir * k.A);
        var q = m.Linear(yDir * k.B);
        double shift = 0.0;
        double pq = p.Dot(q);
        if (pq != 0.0)
        {
            shift = 0.5 * Math.Atan2(2.0 * pq, p.Dot(p) - q.Dot(q));
            double cs = Math.Cos(shift), sn = Math.Sin(shift);
            var p2 = p * cs + q * sn;
            var q2 = q * cs - p * sn;
            p = p2; q = q2;
        }
        if (q.Length > p.Length)
        {
            var t = p; p = q; q = t * -1.0;
            shift += Math.PI / 2.0;
        }
        double ra = p.Length, rb = q.Length;
        var normal = p.Cross(q).Unit();
        var xdir = p / ra;
        double t0 = k.Full ? 0.0 : k.T0 - shift, t1 = k.Full ? TwoPi : k.T1 - shift;
        bool circle = k.IsCircle && ra == rb && pq == 0.0;
        return new ConicCurve(centre, normal, xdir, ra, rb, circle, t0, t1, k.Full, k.Layer);
    }

    // ---- polylines ------------------------------------------------------------------------------

    void AddPolyline(List<(V3 p, double bulge)> pts, bool closed, V3 normal, Affine m, string layer)
    {
        if (pts.Count < 2) { Skipped["Polyline(<2 vertices)"] = Skipped.GetValueOrDefault("Polyline(<2 vertices)") + 1; return; }
        var (ax, ay, az) = ArbitraryAxes(normal);
        int n = closed ? pts.Count : pts.Count - 1;
        for (int i = 0; i < n; i++)
        {
            var (a, bulge) = pts[i];
            var b = pts[(i + 1) % pts.Count].p;
            if (a == b) continue;  // a zero-length segment draws nothing
            var wa = OcsPoint(a, ax, ay, az);
            var wb = OcsPoint(b, ax, ay, az);
            if (bulge == 0.0) { Curves.Add(new LineCurve(m.Apply(wa), m.Apply(wb), layer)); continue; }
            // a bulge is tan(sweep / 4), positive counter-clockwise about the normal
            var d = b - a;
            double chord = d.Length;
            var left = new V3(-d.Y, d.X, 0.0) / chord;
            var mid = (a + b) * 0.5;
            double k = chord * 0.5 * ((1.0 - bulge * bulge) / (2.0 * bulge));
            var centre = mid + left * k;
            double radius = chord * (1.0 + bulge * bulge) / (4.0 * Math.Abs(bulge));
            double sweep = 4.0 * Math.Atan(bulge);
            var from = bulge > 0 ? a : b;
            double a0 = Math.Atan2(from.Y - centre.Y, from.X - centre.X);
            double span = Math.Abs(sweep);
            var kc = new ConicCurve(OcsPoint(centre, ax, ay, az), az, ax, radius, radius, true, a0, a0 + span, false, layer);
            Curves.Add(MapConic(kc, m));
        }
    }

    // ---- splines --------------------------------------------------------------------------------

    void AddSpline(Spline s, Affine m, string layer)
    {
        int d = s.Degree;
        var poles = s.ControlPoints.Select(p => m.Apply(V3.From(p))).ToList();
        int n = poles.Count;
        if (n == 0 && s.FitPoints.Count > 0)
        {
            // Fit points alone do not fix a B-spline (the tangents and the fitting method do), so this entity is
            // left out and counted, and the rest of the drawing converts.
            const string kind = "Spline (fit points only)";
            Skipped[kind] = Skipped.GetValueOrDefault(kind) + 1;
            return;
        }
        if (n == 0)
            throw new ConvertException(15, "CONVERSION_FAILED", "SPLINE without control points");
        if (n < d + 1) throw new ConvertException(15, "CONVERSION_FAILED", "SPLINE with fewer than degree + 1 control points");
        var knots = s.Knots.ToList();
        List<double> weights = null;
        bool rational = s.Flags.HasFlag(SplineFlags.Rational) || (s.Weights.Count == n && s.Weights.Any(w => w != 1.0));
        if (rational)
        {
            if (s.Weights.Count != n) throw new ConvertException(15, "CONVERSION_FAILED", "rational SPLINE with " + s.Weights.Count + " weights for " + n + " control points");
            weights = s.Weights.ToList();
        }
        bool closed;
        if (s.Flags.HasFlag(SplineFlags.Periodic) && knots.Count == n + 1)
        {
            // A periodic spline stores one knot per distinct span boundary and no wrapped poles. Write it as the
            // same curve over one period: the first d poles repeated at the end, the knot vector extended by the
            // period. STEP has no periodic flag, so it arrives as an open (not clamped) B-spline.
            int spans = n;
            double period = knots[spans] - knots[0];
            var ext = new List<double>();
            for (int i = -d; i <= spans + d; i++)
            {
                int j = ((i % spans) + spans) % spans;
                int wraps = (i - j) / spans;
                ext.Add(knots[j] + wraps * period);
            }
            for (int i = 0; i < d; i++) poles.Add(poles[i]);
            if (weights != null) for (int i = 0; i < d; i++) weights.Add(weights[i]);
            knots = ext;
            closed = true;
        }
        else
        {
            if (knots.Count != n + d + 1) throw new ConvertException(15, "CONVERSION_FAILED", "SPLINE has " + knots.Count + " knots, expected " + (n + d + 1));
            closed = false;
        }
        Curves.Add(new SplineCurve(d, poles, knots, weights, closed, layer));
    }
}
