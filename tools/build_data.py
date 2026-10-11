#!/usr/bin/env python3
"""Build the inline coastline data for Antipode's index.html.

Pipeline: Natural Earth 110m land polygons -> polylines -> seam splitting ->
Douglas-Peucker 0.25 deg -> quantize 0.1 deg -> delta/zigzag/base-41 varint.

Also numerically verifies the projection geometry against the spec's
acceptance table (Test 3) so the encoded constants in index.html are trusted.

Usage: python3 build_data.py <ne_110m_land.geojson> <outdir>
Writes: <outdir>/coast_encoded.txt, <outdir>/coast_reference.json
"""
import json, math, sys, urllib.request, os

TOL = 0.1           # Douglas-Peucker tolerance, degrees
Q = 10              # quantization: 0.1 degree units

# ---------------------------------------------------------------- charset ---
# printable ASCII 40..126 minus < > \ ` : 83 chars.
# [0..40] final digit, [41..81] continuation digit (+41), [82] separator.
CHARSET = ''.join(chr(c) for c in range(40, 127) if c not in (60, 62, 92, 96))
assert len(CHARSET) == 83, len(CHARSET)
SEP = CHARSET[82]


def encode_value(v, out):
    """zigzagged non-negative int -> base-41 varint, most significant first."""
    digits = []
    while True:
        digits.append(v % 41)
        v //= 41
        if v == 0:
            break
    digits.reverse()
    for d in digits[:-1]:
        out.append(CHARSET[41 + d])
    out.append(CHARSET[digits[-1]])


def zigzag(v):
    return 2 * v if v >= 0 else -2 * v - 1


def encode(lines):
    out = []
    for i, line in enumerate(lines):
        if i:
            out.append(SEP)
        px, py = 0, 0
        for (x, y) in line:
            encode_value(zigzag(x - px), out)
            encode_value(zigzag(y - py), out)
            px, py = x, y
    return ''.join(out)


def decode(s):
    """Reference decoder; index.html carries the JS twin of this."""
    lines, cur = [], []
    px, py, acc, vals = 0, 0, 0, []
    for ch in s:
        c = CHARSET.index(ch)
        if c == 82:
            lines.append(cur); cur = []; px = py = 0
        elif c >= 41:
            acc = acc * 41 + (c - 41)
        else:
            acc = acc * 41 + c
            v = (acc >> 1) if not (acc & 1) else -((acc + 1) >> 1)
            vals.append(v); acc = 0
            if len(vals) == 2:
                px += vals[0]; py += vals[1]
                cur.append((px, py)); vals = []
    if cur:
        lines.append(cur)
    return lines


# --------------------------------------------------------------- geometry ---
def dp_simplify(pts, tol):
    """Iterative Douglas-Peucker in degree space."""
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        ax, ay = pts[a]; bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        best, bi = -1.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            if L2 == 0:
                d2 = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / L2
                t = max(0.0, min(1.0, t))
                d2 = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if d2 > best:
                best, bi = d2, i
        if best > tol * tol:
            keep[bi] = True
            stack.append((a, bi)); stack.append((bi, b))
    return [p for p, k in zip(pts, keep) if k]


def split_seams(pts):
    """Break polylines at polygon-closure artifacts (poles / antimeridian)."""
    pieces, cur = [], [pts[0]]
    for i in range(1, len(pts)):
        (x1, y1), (x2, y2) = pts[i - 1], pts[i]
        seam = ((abs(y1) > 89.9 and abs(y2) > 89.9) or
                (abs(x1) > 179.9 and abs(x2) > 179.9) or
                abs(x2 - x1) > 180.0)
        if seam:
            if len(cur) >= 2:
                pieces.append(cur)
            cur = [pts[i]]
        else:
            cur.append(pts[i])
    if len(cur) >= 2:
        pieces.append(cur)
    return pieces


# --------------------------------------------- spec Test 3 geometry check ---
def enu_dir(lat, lon, lat0, lon0):
    """d_ENU per the spec, all args degrees."""
    p, l = math.radians(lat), math.radians(lon)
    p0, l0 = math.radians(lat0), math.radians(lon0)
    f = (math.cos(p) * math.cos(l), math.cos(p) * math.sin(l), math.sin(p))
    up = (math.cos(p0) * math.cos(l0), math.cos(p0) * math.sin(l0), math.sin(p0))
    east = (-math.sin(l0), math.cos(l0), 0.0)
    north = (-math.sin(p0) * math.cos(l0), -math.sin(p0) * math.sin(l0), math.cos(p0))
    e = sum(a * b for a, b in zip(f, east))
    n = sum(a * b for a, b in zip(f, north))
    u = sum(a * b for a, b in zip(f, up))
    theta = math.acos(max(-1.0, min(1.0, -u)))
    nu = theta / 2
    hyp = max(math.hypot(e, n), 1e-15)
    return (math.sin(nu) * e / hyp, math.sin(nu) * n / hyp, -math.cos(nu)), theta


def check_test3():
    NY = (40.7128, -74.0060)
    targets = [
        ("antipode",  -40.7128, 105.9940,   0.0,  None,  0.000,  0.000),
        ("Perth",     -31.9523, 115.8613,  11.8, 314.8, -0.073,  0.073),
        ("Sydney",    -33.8688, 151.2093,  36.2, 266.0, -0.326, -0.023),
        ("SouthPole", -90.0,      0.0,     49.3, 180.0,  0.000, -0.459),
        ("Jakarta",    -6.2088, 106.8456,  34.5, 358.5, -0.008,  0.311),
        ("CapeTown",  -33.9249,  18.4241,  67.0, 115.8,  0.596, -0.288),
        ("Mumbai",     19.0760,  72.8777,  67.2,  34.0,  0.372,  0.551),
        ("Reykjavik",  64.1466, -21.9426, 142.2,  34.1,  1.639,  2.418),
    ]
    print("\nTest 3 verification (phone flat, top north: x = d.x/-d.z, y = d.y/-d.z)")
    ok = True
    for name, lat, lon, t_theta, t_brg, tx, ty in targets:
        d, theta = enu_dir(lat, lon, *NY)
        x, y = d[0] / -d[2], d[1] / -d[2]
        th = math.degrees(theta)
        good = abs(x - tx) < 0.006 and abs(y - ty) < 0.006 and abs(th - t_theta) < 0.15
        ok &= good
        print(f"  {name:10s} theta={th:7.2f} (spec {t_theta:6.1f})  "
              f"x={x:+.3f} (spec {tx:+.3f})  y={y:+.3f} (spec {ty:+.3f})  "
              f"{'OK' if good else 'MISMATCH'}")
    if not ok:
        raise SystemExit("Test 3 table mismatch -- geometry or city coords wrong")
    print("  all targets match the spec table.")


# ------------------------------------------------------------------- main ---
def main():
    src, outdir = sys.argv[1], sys.argv[2]
    gj = json.load(open(src))

    raw = []
    for feat in gj["features"]:
        g = feat["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in polys:
            for ring in poly:
                raw.append([(float(x), float(y)) for x, y in ring])

    n_raw = sum(len(l) for l in raw)

    pieces = []
    for line in raw:
        pieces.extend(split_seams(line))

    simplified = [dp_simplify(p, TOL) for p in pieces]

    quantized = []
    for line in simplified:
        q, prev = [], None
        for x, y in line:
            pt = (round(x * Q), round(y * Q))
            if pt != prev:
                q.append(pt)
            prev = pt
        if len(q) >= 2:
            quantized.append(q)

    for line in quantized:
        for x, y in line:
            assert -1800 <= x <= 1800 and -900 <= y <= 900, (x, y)

    enc = encode(quantized)
    assert all(ch in CHARSET for ch in enc)
    assert decode(enc) == quantized, "round-trip failed"

    n_q = sum(len(l) for l in quantized)
    print(f"raw vertices        : {n_raw}")
    print(f"polylines after seam: {len(pieces)}")
    print(f"encoded polylines   : {len(quantized)}")
    print(f"encoded vertices    : {n_q}")
    print(f"encoded size        : {len(enc)} chars")

    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "coast_encoded.txt"), "w") as f:
        f.write(enc)
    with open(os.path.join(outdir, "coast_reference.json"), "w") as f:
        json.dump(quantized, f)

    check_test3()


if __name__ == "__main__":
    main()
