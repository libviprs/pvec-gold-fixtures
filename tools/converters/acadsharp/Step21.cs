// Step21: the AP242 Part 21 subset this converter writes, and nothing else. Every real is written at 17
// significant digits (E16 format), which round-trips an IEEE double exactly. The entities are the ones the
// existing hand-written evaluator self-test files use (fixtures/validator-selftest), so what step_eval reads
// here is what it was checked against: LINE, CIRCLE, ELLIPSE, TRIMMED_CURVE,
// B_SPLINE_CURVE_WITH_KNOTS and the RATIONAL_B_SPLINE_CURVE complex entity, AXIS2_PLACEMENT_3D and
// GEOMETRIC_CURVE_SET. No geometry kernel is involved in writing it.
using System.Globalization;
using System.Text;

namespace Dwg2Step;

public sealed class Step21
{
    readonly StringBuilder _data = new();
    int _next = 100;
    readonly List<int> _curves = new();

    public static string Real(double d)
    {
        if (!double.IsFinite(d)) throw new ConvertException(15, "CONVERSION_FAILED", "non-finite coordinate");
        if (d == 0.0) d = 0.0;  // no negative zero
        return d.ToString("E16", CultureInfo.InvariantCulture);
    }

    static string R3(V3 v) => "(" + Real(v.X) + "," + Real(v.Y) + "," + Real(v.Z) + ")";

    int Add(string body)
    {
        int id = _next++;
        _data.Append('#').Append(id).Append('=').Append(body).Append(";\n");
        return id;
    }

    int Point(V3 p) => Add("CARTESIAN_POINT('',"+ R3(p) + ")");
    int Dir(V3 d) => Add("DIRECTION('',"+ R3(d) + ")");
    int Place(V3 origin, V3 axis, V3 refDir) { int o = Point(origin), a = Dir(axis), r = Dir(refDir); return Add("AXIS2_PLACEMENT_3D('',#" + o + ",#" + a + ",#" + r + ")"); }
    int Trim(int basis, double t0, double t1) => Add("TRIMMED_CURVE('',#" + basis + ",(PARAMETER_VALUE(" + Real(t0) + ")),(PARAMETER_VALUE(" + Real(t1) + ")),.T.,.PARAMETER.)");

    public void Write(Curve c)
    {
        switch (c)
        {
            case LineCurve l:
                {
                    var d = l.P1 - l.P0;
                    double len = d.Length;
                    if (len == 0.0) return;
                    int p = Point(l.P0), dir = Dir(d / len);
                    int v = Add("VECTOR('',#" + dir + "," + Real(len) + ")");
                    int ln = Add("LINE('',#" + p + ",#" + v + ")");
                    _curves.Add(Trim(ln, 0.0, 1.0));   // a STEP line's parameter runs over the VECTOR's magnitude
                    break;
                }
            case ConicCurve k:
                {
                    int pl = Place(k.Center, k.Normal, k.XDir);
                    int basis = k.IsCircle ? Add("CIRCLE('',#" + pl + "," + Real(k.A) + ")") : Add("ELLIPSE('',#" + pl + "," + Real(k.A) + "," + Real(k.B) + ")");
                    _curves.Add(Trim(basis, k.T0, k.T1));
                    break;
                }
            case SplineCurve s:
                _curves.Add(Spline(s));
                break;
        }
    }

    int Spline(SplineCurve s)
    {
        var ids = s.Poles.Select(Point).ToList();
        string pts = "(" + string.Join(",", ids.Select(i => "#" + i)) + ")";
        // Closed is only set for a wrapped periodic spline. A clamped spline whose ends coincide is written .F.:
        // with .T. the OCCT reader rebuilds it as a periodic spline and drops a pole.
        string closed = s.Closed ? ".T." : ".F.";
        var distinct = new List<double>();
        var mult = new List<int>();
        foreach (var k in s.Knots)
        {
            if (distinct.Count > 0 && distinct[^1] == k) mult[^1]++;
            else { distinct.Add(k); mult.Add(1); }
        }
        string km = "(" + string.Join(",", mult) + ")";
        string kv = "(" + string.Join(",", distinct.Select(Real)) + ")";
        if (s.Weights != null)
        {
            string w = "(" + string.Join(",", s.Weights.Select(Real)) + ")";
            return Add("(BOUNDED_CURVE()B_SPLINE_CURVE(" + s.Degree + "," + pts + ",.UNSPECIFIED.," + closed + ",.F.)B_SPLINE_CURVE_WITH_KNOTS(" + km + "," + kv + ",.UNSPECIFIED.)CURVE()GEOMETRIC_REPRESENTATION_ITEM()RATIONAL_B_SPLINE_CURVE(" + w + ")REPRESENTATION_ITEM(''))");
        }
        return Add("B_SPLINE_CURVE_WITH_KNOTS(''," + s.Degree + "," + pts + ",.UNSPECIFIED.," + closed + ",.F.," + km + "," + kv + ",.UNSPECIFIED.)");
    }

    public int CurveCount => _curves.Count;

    /// <summary>The unit the file declares. Program.cs has already scaled inches and feet to metre, the others are only labelled.</summary>
    public string Document(string fileName, string timeStamp, string description, string lengthUnit)
    {
        var sb = new StringBuilder();
        sb.Append("ISO-10303-21;\nHEADER;\n");
        sb.Append("FILE_DESCRIPTION(('").Append(Esc(description)).Append("'),'2;1');\n");
        sb.Append("FILE_NAME('").Append(Esc(fileName)).Append("','").Append(timeStamp).Append("',(''),(''),'dwg2step-acadsharp','','');\n");
        sb.Append("FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF { 1 0 10303 442 1 1 4 }'));\n");
        sb.Append("ENDSEC;\nDATA;\n");
        sb.Append("#1=APPLICATION_CONTEXT('managed model based 3d engineering');\n");
        sb.Append("#2=APPLICATION_PROTOCOL_DEFINITION('international standard','ap242_managed_model_based_3d_engineering',2011,#1);\n");
        sb.Append("#3=PRODUCT_CONTEXT('',#1,'mechanical');\n");
        sb.Append("#4=PRODUCT('drawing','drawing','',(#3));\n");
        sb.Append("#5=PRODUCT_DEFINITION_CONTEXT('part definition',#1,'design');\n");
        sb.Append("#6=PRODUCT_DEFINITION_FORMATION('',' ',#4);\n");
        sb.Append("#7=PRODUCT_DEFINITION('design','',#6,#5);\n");
        sb.Append("#8=PRODUCT_DEFINITION_SHAPE('','',#7);\n");
        sb.Append("#9=SHAPE_DEFINITION_REPRESENTATION(#8,#10);\n");
        sb.Append("#10=GEOMETRICALLY_BOUNDED_WIREFRAME_SHAPE_REPRESENTATION('',(#11,#20),#30);\n");
        sb.Append("#11=AXIS2_PLACEMENT_3D('',#12,#13,#14);\n");
        sb.Append("#12=CARTESIAN_POINT('',(").Append(Real(0)).Append(',').Append(Real(0)).Append(',').Append(Real(0)).Append("));\n");
        sb.Append("#13=DIRECTION('',(").Append(Real(0)).Append(',').Append(Real(0)).Append(',').Append(Real(1)).Append("));\n");
        sb.Append("#14=DIRECTION('',(").Append(Real(1)).Append(',').Append(Real(0)).Append(',').Append(Real(0)).Append("));\n");
        sb.Append("#20=GEOMETRIC_CURVE_SET('',(").Append(string.Join(",", _curves.Select(i => "#" + i))).Append("));\n");
        sb.Append("#30=(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#31))GLOBAL_UNIT_ASSIGNED_CONTEXT((#32,#33,#34))REPRESENTATION_CONTEXT('Context3D','3D Context with UNIT and UNCERTAINTY'));\n");
        sb.Append("#31=UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.0000000000000000E-007),#32,'distance_accuracy_value','confusion accuracy');\n");
        sb.Append("#32=(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(").Append(lengthUnit).Append("));\n");
        sb.Append("#33=(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.));\n");
        sb.Append("#34=(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT());\n");
        sb.Append(_data);
        sb.Append("ENDSEC;\nEND-ISO-10303-21;\n");
        return sb.ToString();
    }

    static string Esc(string s) => s.Replace("'", "''").Replace("\\", "\\\\");
}
