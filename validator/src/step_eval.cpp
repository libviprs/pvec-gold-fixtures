// step_eval: read a STEP file with Open CASCADE and describe every curve in it.
//
//   step_eval --in file.step --out file.verification.json --policy-version <id>
//
// The record per curve: semantic class, units, parameter domain, degree, control points, knots
// with multiplicities, weights, closure and periodicity, the composed transform, and evaluated
// point / tangent / curvature samples. Scalars are {decimal, f64_hex} pairs (shortest decimal
// that round-trips, plus the bits), the same representation as expected.math.json.
//
// This program decides nothing about equality. It has no tolerance and no epsilon: the only
// comparisons are exact ones on stored values (a weight equal to 1.0, a span equal to 2*pi).
// Comparison verdicts come from the vendored numeric policy, elsewhere.
#include <algorithm>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include <BRep_Tool.hxx>
#include <Geom_BSplineCurve.hxx>
#include <Geom_BezierCurve.hxx>
#include <Geom_Circle.hxx>
#include <Geom_Curve.hxx>
#include <Geom_Ellipse.hxx>
#include <Geom_Line.hxx>
#include <Geom_TrimmedCurve.hxx>
#include <IFSelect_ReturnStatus.hxx>
#include <Interface_Static.hxx>
#include <STEPControl_Reader.hxx>
#include <Standard_Version.hxx>
#include <TColStd_SequenceOfAsciiString.hxx>
#include <TopExp.hxx>
#include <TopLoc_Location.hxx>
#include <TopTools_IndexedMapOfShape.hxx>
#include <TopoDS.hxx>
#include <TopoDS_Edge.hxx>
#include <gp_Ax1.hxx>
#include <gp_Ax2.hxx>
#include <gp_Circ.hxx>
#include <gp_Dir.hxx>
#include <gp_Elips.hxx>
#include <gp_Pnt.hxx>
#include <gp_Trsf.hxx>
#include <gp_Vec.hxx>

static const char *kEvaluatorVersion = "1";
static const int kUniformSamples = 16;  // a count of sample intervals, not a tolerance

// ---- scalar and JSON helpers -------------------------------------------------------------

static std::string hex64(double x) {
  uint64_t b;
  std::memcpy(&b, &x, sizeof b);
  char buf[32];
  std::snprintf(buf, sizeof buf, "0x%016llx", (unsigned long long)b);
  return buf;
}

static std::string scalar(double x) {
  if (!std::isfinite(x)) {
    std::cerr << "step_eval: non-finite value\n";
    std::exit(3);
  }
  char buf[64];
  auto r = std::to_chars(buf, buf + sizeof buf, x);
  std::string d(buf, r.ptr);
  // to_chars writes "1e+22"; JSON text must still match the decimal pattern, which allows it.
  return std::string("{\"decimal\": \"") + d + "\", \"f64_hex\": \"" + hex64(x) + "\"}";
}

static std::string jstr(const std::string &s) {
  std::string o = "\"";
  for (char c : s) {
    if (c == '"' || c == '\\') o += '\\';
    o += c;
  }
  return o + "\"";
}

static std::string vec3(double x, double y, double z) { return "[" + scalar(x) + ", " + scalar(y) + ", " + scalar(z) + "]"; }
static std::string pnt(const gp_Pnt &p) { return vec3(p.X(), p.Y(), p.Z()); }
static std::string dir(const gp_Dir &d) { return vec3(d.X(), d.Y(), d.Z()); }

// ---- units -------------------------------------------------------------------------------

struct Unit { const char *occt; double scale_to_metre; const char *name; };
static const Unit kUnits[] = {
    {"M", 1.0, "METRE"}, {"MM", 1.0 / 1000.0, "MILLIMETRE"}, {"CM", 1.0 / 100.0, "CENTIMETRE"}, {"KM", 1000.0, "KILOMETRE"},
    {"UM", 1.0 / 1000000.0, "MICROMETRE"}, {"INCH", 254.0 / 10000.0, "INCH"}, {"FT", 3048.0 / 10000.0, "FOOT"}, {"MI", 1609344.0 / 1000.0, "MILE"},
};

static const Unit *unit_for(const std::string &name) {
  std::string u;
  for (char c : name) u += (char)std::toupper((unsigned char)c);
  for (const Unit &k : kUnits)
    if (u == k.occt || u == k.name) return &k;
  if (u == "INCHES") return &kUnits[5];
  if (u == "FEET") return &kUnits[6];
  return nullptr;
}

// ---- curve description -------------------------------------------------------------------

struct Entity {
  std::string cls, geometry, domain, closure;
  std::vector<double> exclusions;
};

static std::string closure_json(bool endpoint, bool knots, bool periodic) {
  return std::string("{\"closed_by_endpoint\": ") + (endpoint ? "true" : "false") + ", \"closed_by_knots\": " + (knots ? "true" : "false") +
         ", \"periodic\": " + (periodic ? "true" : "false") + "}";
}

static std::string domain_json(double a, double b) { return "{\"start\": " + scalar(a) + ", \"end\": " + scalar(b) + "}"; }

static const double kTwoPi = 2.0 * 3.14159265358979323846;

static bool describe(Handle(Geom_Curve) c, double f, double l, Entity &e, std::vector<double> &knot_params,
                     std::vector<std::pair<double, int>> &knots_mult, int &degree) {
  while (c->IsKind(STANDARD_TYPE(Geom_TrimmedCurve))) c = Handle(Geom_TrimmedCurve)::DownCast(c)->BasisCurve();
  degree = 0;
  if (auto ln = Handle(Geom_Line)::DownCast(c)) {
    gp_Pnt a = c->Value(f), b = c->Value(l);
    e.cls = "line";
    e.geometry = "{\"start\": " + pnt(a) + ", \"end\": " + pnt(b) + "}";
    e.domain = domain_json(f, l);
    e.closure = closure_json(false, false, false);
    return true;
  }
  if (auto ci = Handle(Geom_Circle)::DownCast(c)) {
    gp_Circ k = ci->Circ();
    bool full = (l - f) == kTwoPi;
    e.cls = full ? "circle" : "circular_arc";
    e.geometry = "{\"center\": " + pnt(k.Location()) + ", \"normal\": " + dir(k.Axis().Direction()) + ", \"x_axis\": " + dir(k.XAxis().Direction()) +
                 ", \"radius\": " + scalar(k.Radius());
    if (!full) e.geometry += ", \"start_angle\": " + scalar(f) + ", \"sweep_angle\": " + scalar(l - f);
    e.geometry += "}";
    e.domain = domain_json(f, l);
    e.closure = full ? closure_json(true, false, true) : closure_json(false, false, false);
    return true;
  }
  if (auto el = Handle(Geom_Ellipse)::DownCast(c)) {
    gp_Elips k = el->Elips();
    bool full = (l - f) == kTwoPi;
    e.cls = full ? "ellipse" : "elliptical_arc";
    e.geometry = "{\"center\": " + pnt(k.Location()) + ", \"normal\": " + dir(k.Axis().Direction()) + ", \"major_axis\": " + dir(k.XAxis().Direction()) +
                 ", \"semi_major\": " + scalar(k.MajorRadius()) + ", \"semi_minor\": " + scalar(k.MinorRadius());
    if (!full) e.geometry += ", \"start_angle\": " + scalar(f) + ", \"sweep_angle\": " + scalar(l - f);
    e.geometry += "}";
    e.domain = domain_json(f, l);
    e.closure = full ? closure_json(true, false, true) : closure_json(false, false, false);
    return true;
  }
  Handle(Geom_BSplineCurve) bs = Handle(Geom_BSplineCurve)::DownCast(c);
  Handle(Geom_BezierCurve) bz = Handle(Geom_BezierCurve)::DownCast(c);
  if (bs.IsNull() && bz.IsNull()) {
    e.cls = "unsupported";
    e.geometry = "{\"occt_type\": " + jstr(c->DynamicType()->Name()) + "}";
    e.domain = domain_json(f, l);
    e.closure = closure_json(false, false, false);
    return false;
  }
  int n = bs.IsNull() ? bz->NbPoles() : bs->NbPoles();
  degree = bs.IsNull() ? bz->Degree() : bs->Degree();
  bool rational = bs.IsNull() ? bz->IsRational() : bs->IsRational();
  std::string cps = "[";
  std::vector<double> w;
  for (int i = 1; i <= n; ++i) {
    gp_Pnt p = bs.IsNull() ? bz->Pole(i) : bs->Pole(i);
    cps += (i > 1 ? ", " : "") + pnt(p);
    w.push_back(rational ? (bs.IsNull() ? bz->Weight(i) : bs->Weight(i)) : 1.0);
  }
  cps += "]";
  gp_Pnt first = bs.IsNull() ? bz->Pole(1) : bs->Pole(1), last = bs.IsNull() ? bz->Pole(n) : bs->Pole(n);
  bool endpoint = first.X() == last.X() && first.Y() == last.Y() && first.Z() == last.Z();
  bool periodic = !bs.IsNull() && bs->IsPeriodic();
  std::string knots = "[";
  if (bs.IsNull()) {
    knots_mult = {{0.0, degree + 1}, {1.0, degree + 1}};
  } else {
    for (int i = 1; i <= bs->NbKnots(); ++i) knots_mult.push_back({bs->Knot(i), bs->Multiplicity(i)});
  }
  for (size_t i = 0; i < knots_mult.size(); ++i)
    knots += (i ? ", " : "") + std::string("{\"value\": ") + scalar(knots_mult[i].first) + ", \"multiplicity\": " + std::to_string(knots_mult[i].second) + "}";
  knots += "]";
  e.cls = rational ? "nurbs" : (bs.IsNull() ? "bezier" : "bspline");
  e.geometry = "{\"degree\": " + std::to_string(degree) + ", \"control_points\": " + cps;
  if (bs.IsNull() && !rational) {
    // a Bezier record has no knots field
  } else {
    e.geometry += ", \"knots\": " + knots;
  }
  if (rational) {
    bool unit = std::all_of(w.begin(), w.end(), [](double x) { return x == 1.0; });
    std::string ws = "[";
    for (size_t i = 0; i < w.size(); ++i) ws += (i ? ", " : "") + scalar(w[i]);
    e.geometry += ", \"weights\": " + ws + "], \"weights_all_unit\": " + (unit ? "true" : "false");
  }
  e.geometry += "}";
  e.domain = domain_json(f, l);
  e.closure = closure_json(endpoint, periodic, periodic);
  for (auto &km : knots_mult) knot_params.push_back(km.first);
  return true;
}

static const char *classify(const gp_Trsf &t) {
  bool lin_identity = true;
  for (int r = 1; r <= 3; ++r)
    for (int c = 1; c <= 3; ++c)
      if (t.Value(r, c) != (r == c ? 1.0 : 0.0)) lin_identity = false;
  bool trans = t.Value(1, 4) != 0.0 || t.Value(2, 4) != 0.0 || t.Value(3, 4) != 0.0;
  if (lin_identity) return trans ? "TRANSLATION" : "IDENTITY";
  if (t.IsNegative()) return "REFLECTION";
  if (t.ScaleFactor() != 1.0) return "GENERAL_AFFINE";
  return "ROTATION";
}

static std::string transform_json(const gp_Trsf &t) {
  std::string m = "[";
  for (int r = 1; r <= 3; ++r)
    for (int c = 1; c <= 4; ++c) m += scalar(t.Value(r, c)) + ", ";
  m += scalar(0.0) + ", " + scalar(0.0) + ", " + scalar(0.0) + ", " + scalar(1.0) + "]";
  double det = t.Value(1, 1) * (t.Value(2, 2) * t.Value(3, 3) - t.Value(2, 3) * t.Value(3, 2)) -
               t.Value(1, 2) * (t.Value(2, 1) * t.Value(3, 3) - t.Value(2, 3) * t.Value(3, 1)) +
               t.Value(1, 3) * (t.Value(2, 1) * t.Value(3, 2) - t.Value(2, 2) * t.Value(3, 1));
  return "{\"convention\": \"ROW_MAJOR_COLUMN_VECTOR_PARENT_LEFT\", \"matrix\": " + m + ", \"determinant\": " + scalar(det) +
         ", \"classification\": \"" + classify(t) + "\"}";
}

static int mult_at(const std::vector<std::pair<double, int>> &km, double u) {
  for (auto &k : km)
    if (k.first == u) return k.second;
  return 0;
}

int main(int argc, char **argv) {
  std::string in, out, policy;
  for (int i = 1; i + 1 < argc; i += 2) {
    std::string a = argv[i];
    if (a == "--in") in = argv[i + 1];
    else if (a == "--out") out = argv[i + 1];
    else if (a == "--policy-version") policy = argv[i + 1];
  }
  if (in.empty() || out.empty() || policy.empty()) {
    std::cerr << "usage: step_eval --in f.step --out f.verification.json --policy-version ID\n";
    return 2;
  }
  STEPControl_Reader reader;
  if (reader.ReadFile(in.c_str()) != IFSelect_RetDone) {
    std::cerr << "step_eval: cannot read " << in << "\n";
    return 4;
  }
  TColStd_SequenceOfAsciiString lens, angs, sols;
  reader.FileUnits(lens, angs, sols);
  const Unit *unit = &kUnits[0];
  std::string unit_src = "default";
  if (lens.Length() > 0) {
    unit = unit_for(lens.Value(1).ToCString());
    if (!unit) {
      std::cerr << "step_eval: unsupported length unit " << lens.Value(1).ToCString() << "\n";
      return 5;
    }
    unit_src = "file";
  }
  // Keep the file's own length unit so no coordinate is rescaled on the way in.
  Interface_Static::SetCVal("xstep.cascade.unit", unit->occt);
  reader.TransferRoots();
  TopoDS_Shape shape = reader.OneShape();
  TopTools_IndexedMapOfShape edges;
  if (!shape.IsNull()) TopExp::MapShapes(shape, TopAbs_EDGE, edges);

  std::ostringstream os;
  os << "{\n  \"schema_version\": \"pvec-gold/verification/1\",\n";
  os << "  \"tool\": {\"name\": \"step_eval\", \"evaluator_version\": " << jstr(kEvaluatorVersion) << ", \"occt_version\": " << jstr(OCC_VERSION_STRING_EXT)
     << "},\n";
  os << "  \"numeric_policy_version\": " << jstr(policy) << ",\n";
  os << "  \"units\": {\"name\": " << jstr(unit->name) << ", \"canonical\": \"metre\", \"scale_to_canonical\": " << scalar(unit->scale_to_metre)
     << ", \"source\": " << jstr(unit_src) << "},\n";
  os << "  \"entities\": [";
  int idx = 0;
  for (int k = 1; k <= edges.Extent(); ++k) {
    TopoDS_Edge edge = TopoDS::Edge(edges(k));
    TopLoc_Location loc;
    double f, l;
    Handle(Geom_Curve) c = BRep_Tool::Curve(edge, loc, f, l);
    if (c.IsNull()) continue;
    Entity e;
    std::vector<double> knot_params;
    std::vector<std::pair<double, int>> km;
    int degree = 0;
    bool supported = describe(c, f, l, e, knot_params, km, degree);
    gp_Trsf t = loc.Transformation();
    std::ostringstream id;
    id << "edge-" << (++idx);
    os << (idx > 1 ? ",\n" : "\n") << "    {\n      \"id\": " << jstr(id.str()) << ",\n      \"class\": " << jstr(e.cls) << ",\n      \"structure\": \"CURVE_ONLY\",\n"
       << "      \"geometry\": " << e.geometry << ",\n      \"parameter_domain\": " << e.domain << ",\n      \"closure\": " << e.closure << ",\n"
       << "      \"transform\": " << transform_json(t) << ",\n";
    // samples
    std::vector<double> params;
    for (int i = 0; i <= kUniformSamples; ++i) params.push_back(f + (l - f) * (double)i / (double)kUniformSamples);
    for (double u : knot_params)
      if (u > f && u < l) params.push_back(u);
    std::sort(params.begin(), params.end());
    params.erase(std::unique(params.begin(), params.end()), params.end());
    std::vector<std::pair<double, std::string>> excl;
    os << "      \"samples\": [";
    int si = 0;
    for (double u : params) {
      gp_Pnt p;
      gp_Vec d1, d2;
      c->D2(u, p, d1, d2);
      p.Transform(t);
      d1.Transform(t);
      d2.Transform(t);
      int m = mult_at(km, u);
      bool interior = u > f && u < l;
      bool no_tangent = supported && interior && degree > 0 && m >= degree;
      bool no_curv = supported && interior && degree > 0 && m >= degree - 1 && m > 0;
      double speed = d1.Magnitude();
      std::string tang = "null", curv = "null", why = "null";
      if (no_tangent || no_curv) {
        why = no_tangent ? "\"C0_KNOT\"" : "\"C1_KNOT\"";
        if (no_tangent) excl.push_back({u, "C0_KNOT"});
      }
      if (!no_tangent && speed != 0.0) {
        gp_Vec tv = d1 / speed;
        tang = vec3(tv.X(), tv.Y(), tv.Z());
        if (!no_curv) curv = scalar(d1.Crossed(d2).Magnitude() / (speed * speed * speed));
      } else if (!no_tangent) {
        why = "\"ZERO_SPEED\"";
      }
      os << (si++ ? ",\n        " : "\n        ") << "{\"parameter\": " << scalar(u) << ", \"point\": " << pnt(p) << ", \"tangent\": " << tang
         << ", \"curvature\": " << curv << ", \"derivative_exclusion\": " << why << "}";
    }
    os << "\n      ]";
    if (!excl.empty()) {
      os << ",\n      \"derivative_exclusions\": [";
      for (size_t i = 0; i < excl.size(); ++i) os << (i ? ", " : "") << "{\"parameter\": " << scalar(excl[i].first) << ", \"reason\": \"C0_KNOT\"}";
      os << "]";
    }
    os << "\n    }";
  }
  os << "\n  ]\n}\n";
  std::ofstream of(out, std::ios::binary);
  of << os.str();
  return of.good() ? 0 : 6;
}
