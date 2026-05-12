#!/usr/bin/env python3
"""
socket_layout.py  —  gridfinity socket holder layout optimizer

Usage:
    python3 socket_layout.py                  # uses sockets.csv, writes sockets.scad
    python3 socket_layout.py my_sockets.csv   # specify file
    python3 socket_layout.py --preview        # generate SVG preview (opens in browser)
    python3 socket_layout.py --help
"""

import csv
import math
import subprocess
import sys
from itertools import permutations
from collections import OrderedDict
from pathlib import Path

# ─── Layout parameters ─────────────────────────────────────────────────────────
GRID_UNIT       = 42.0  # mm per gridfinity unit
WALL            = 3.0   # clearance: bin inner edge → first/last circle centre
CYL_GAP         = 2.0   # min wall between cylinders in the same group
INTER_GROUP_GAP = 5.0   # wider gap between groups when sharing a row
ROW_GAP         = 1.0   # vertical gap: label bottom → next row's cylinder top
LABEL_BELOW     = 0.5   # gap: cylinder bottom → label top
MIN_LABEL       = 1.5   # minimum acceptable label font size (mm)
MIN_PRINTABLE   = 3.0   # labels below this get a unit penalty (not 3D-printable)
CHAR_WIDTH_RATIO = 0.62 # approx char_width / font_size for Liberation Sans Bold
ROTATE_LABELS    = False  # set True to rotate labels 90° clockwise

SOCKET_DEPTH = 12
CHAMFER      = 0.5
MAX_GX       = 8
MAX_GY       = 8

# ─── Load CSV ──────────────────────────────────────────────────────────────────

def load_sockets(path):
    """Returns OrderedDict {group: [(label, r), ...]} in file order."""
    groups = OrderedDict()
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            g = row["group"].strip()
            groups.setdefault(g, []).append(
                (row["label"].strip(), float(row["radius_mm"]))
            )
    return groups

def flatten(groups):
    """Flatten ordered groups → [(group, label, r), ...] preserving order."""
    return [(g, lbl, r) for g, sockets in groups.items() for lbl, r in sockets]

# ─── Row geometry (flat rows may span group boundaries) ────────────────────────

def row_width(flat_row):
    """Min width for a flat row, using INTER_GROUP_GAP at group boundaries."""
    w, prev_g = 2*WALL, None
    for i, (g, _, r) in enumerate(flat_row):
        if i > 0:
            w += INTER_GROUP_GAP if g != prev_g else CYL_GAP
        w += 2*r
        prev_g = g
    return w

def row_cyl_height(flat_row):
    return 2 * max(r for _, _, r in flat_row)

def label_v_space(flat_row, label_size):
    """Vertical space the label occupies below its row."""
    if ROTATE_LABELS:
        max_chars = max(len(lbl) for _, lbl, _ in flat_row)
        return max_chars * CHAR_WIDTH_RATIO * label_size
    return label_size

def row_total_height(flat_row, label_size):
    return row_cyl_height(flat_row) + LABEL_BELOW + label_v_space(flat_row, label_size)

# ─── DP: optimal row splits on the full flat socket list ──────────────────────

def best_splits(flat, W, label_size):
    """
    Minimise total height for the flat socket list at usable width W.
    Returns (height, [row, ...]) where each row is a flat slice.
    """
    n = len(flat)
    INF = float('inf')
    dp_h   = [INF] * (n + 1)
    dp_cut = [None] * (n + 1)
    dp_h[0] = 0.0

    for i in range(1, n + 1):
        for j in range(i):
            row = flat[j:i]
            if row_width(row) > W:
                continue
            gap = ROW_GAP if dp_h[j] > 0 else 0
            h = dp_h[j] + gap + row_total_height(row, label_size)
            if h < dp_h[i]:
                dp_h[i] = h
                dp_cut[i] = j

    if dp_h[n] == INF:
        # Find the offending socket
        for g, lbl, r in flat:
            if 2*WALL + 2*r > W:
                raise ValueError(
                    f"Socket '{lbl}' (r={r}mm) needs {2*WALL+2*r:.1f}mm "
                    f"but usable width is {W:.1f}mm"
                )
        raise ValueError(f"Cannot fit all sockets in width {W:.1f}mm")

    rows, i = [], n
    while i > 0:
        j = dp_cut[i]
        rows.append(flat[j:i])
        i = j
    rows.reverse()
    return dp_h[n], rows

def content_height(flat, W, label_size):
    h, _ = best_splits(flat, W, label_size)
    return h

# ─── Maximise label size for a fixed bin ──────────────────────────────────────

def _h_limit_for_rows(rows):
    """Horizontal font-size limit: largest label must fit in its available gap."""
    h_limit = float('inf')
    for row in rows:
        xs, x = [], WALL
        for i, (g, _, r) in enumerate(row):
            if i > 0:
                x += INTER_GROUP_GAP if g != row[i-1][0] else CYL_GAP
            x += r; xs.append(x); x += r
        for idx, ((g, lbl, r), cx) in enumerate(zip(row, xs)):
            left  = cx - r - ((INTER_GROUP_GAP if row[idx][0] != row[idx-1][0]
                               else CYL_GAP) / 2 if idx > 0 else 0)
            right = cx + r + ((INTER_GROUP_GAP if idx < len(row)-1 and
                               row[idx][0] != row[idx+1][0]
                               else CYL_GAP) / 2 if idx < len(row)-1 else 0)
            h_limit = min(h_limit, (right - left) / (max(len(lbl), 1) * CHAR_WIDTH_RATIO))
    return h_limit

def compute_label_size(flat, gx, gy, W):
    """
    Iterates until the row structure is stable at the computed label size.
    Bug without iteration: rows from MIN_LABEL may differ from rows at the
    computed label_size, leaving slack unused.
    """
    usable_h = gy * GRID_UNIT - 2*WALL
    ls = MIN_LABEL
    v_limit = h_limit = MIN_LABEL

    for _ in range(20):  # converges in 2–3 iterations in practice
        _, rows = best_splits(flat, W, ls)
        n_rows  = len(rows)

        fixed_h = (sum(row_cyl_height(r) for r in rows)
                   + n_rows * LABEL_BELOW
                   + (n_rows - 1) * ROW_GAP)

        if ROTATE_LABELS:
            char_factor = sum(
                max(len(lbl) for _, lbl, _ in row) * CHAR_WIDTH_RATIO
                for row in rows
            )
            v_limit = (usable_h - fixed_h) / char_factor if char_factor > 0 else MIN_LABEL
            h_limit = min(2 * r for _, _, r in flat)
        else:
            v_limit = (usable_h - fixed_h) / n_rows if n_rows > 0 else MIN_LABEL
            h_limit = _h_limit_for_rows(rows)

        ls_new = max(MIN_LABEL, min(v_limit, h_limit))
        if abs(ls_new - ls) < 0.01:
            break
        ls = ls_new

    return ls_new, v_limit, h_limit

# ─── 2D label placement ────────────────────────────────────────────────────────

LABEL_GAP = 0.4   # clearance between label rect edge and circle/other labels

def _rect_circle_overlap(rx, ry, rw, rh, cx, cy, cr):
    """True if rectangle (centred rx,ry size rw×rh) overlaps circle (cx,cy,cr)."""
    nx = max(rx - rw/2, min(cx, rx + rw/2))
    ny = max(ry - rh/2, min(cy, ry + rh/2))
    return (cx - nx)**2 + (cy - ny)**2 < cr**2

def _rects_overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return (abs(ax - bx) < (aw + bw)/2 + LABEL_GAP and
            abs(ay - by) < (ah + bh)/2 + LABEL_GAP)

def _label_candidates(cx, cy, r, lw, lh):
    """
    Candidate label-centre positions: always below the circle, never above.
    Horizontal nudge capped at ±r so the label stays visually under its hole.
    """
    g = LABEL_GAP
    below_y = cy - r - g - lh/2
    max_dx = r  # keep label within the hole's horizontal footprint

    cands = []
    # Step outward in 1mm increments alternating left/right, up to ±max_dx
    dx_steps = [0]
    d = 1.0
    while d <= max_dx + 0.01:
        dx_steps += [d, -d]
        d += 1.0

    # Primary: natural below_y
    for dx in dx_steps:
        cands.append((cx + dx, below_y))

    # Secondary: push the label down slightly into the row gap
    for dy_extra in [lh * 0.5, lh]:
        for dx in dx_steps:
            cands.append((cx + dx, below_y - dy_extra))

    return cands

def _place_labels_2d(circles, W, H_usable, label_size):
    """
    Greedy 2D placement for labels of all circles.
    circles: [(g, lbl, r, cx, cy), ...] in OpenSCAD centred coords.
    Returns [(lx, ly), ...] or None if any label cannot be placed.
    """
    lh = label_size
    placed = []   # (lx, ly, lw, lh) of already-placed labels
    result  = [None] * len(circles)

    for i in range(len(circles)):
        g, lbl, r, cx, cy = circles[i]
        lw = max(len(lbl), 1) * CHAR_WIDTH_RATIO * lh
        for lx, ly in _label_candidates(cx, cy, r, lw, lh):
            # Bin bounds
            if lx - lw/2 < -W/2 or lx + lw/2 > W/2:
                continue
            if ly - lh/2 < -H_usable/2 or ly + lh/2 > H_usable/2:
                continue
            # Clear of every circle
            if any(_rect_circle_overlap(lx, ly, lw, lh, cx2, cy2, r2 + LABEL_GAP)
                   for _, _, r2, cx2, cy2 in circles):
                continue
            # Clear of already-placed labels
            if any(_rects_overlap(lx, ly, lw, lh, plx, ply, plw, plh)
                   for plx, ply, plw, plh in placed):
                continue
            placed.append((lx, ly, lw, lh))
            result[i] = (lx, ly)
            break

        if result[i] is None:
            return None

    return result

def find_max_label_size_2d(circles, W, H_usable):
    """
    Binary-search for the largest label_size where 2D placement succeeds.
    Returns (label_size, [(lx, ly), ...]).
    """
    lo, hi = MIN_LABEL, min(W, H_usable) / 2
    best_size = lo
    best_pos  = _place_labels_2d(circles, W, H_usable, lo)

    for _ in range(25):
        mid = (lo + hi) / 2
        pos = _place_labels_2d(circles, W, H_usable, mid)
        if pos is not None:
            best_size, best_pos, lo = mid, pos, mid
        else:
            hi = mid
        if hi - lo < 0.02:
            break

    return best_size, best_pos

# ─── Find optimal gridfinity bin ──────────────────────────────────────────────

def adjacency_score(perm, prefer_adjacent):
    names = list(perm)
    return sum(
        1 for a, b in prefer_adjacent
        if a in names and b in names and abs(names.index(a) - names.index(b)) != 1
    )

def find_optimal_bin(groups, prefer_adjacent=None):
    if prefer_adjacent is None:
        prefer_adjacent = []

    usable_w = lambda gx: gx * GRID_UNIT - 2*WALL
    usable_h = lambda gy: gy * GRID_UNIT - 2*WALL

    group_names = list(groups.keys())
    best = None  # (units, adj, -label_size, gx, gy, W, perm)

    for perm in permutations(group_names):
        ordered = OrderedDict((k, groups[k]) for k in perm)
        flat    = flatten(ordered)
        for gx in range(1, MAX_GX + 1):
            W = usable_w(gx)
            try:
                H = content_height(flat, W, MIN_LABEL)
            except ValueError:
                continue
            for gy in range(1, MAX_GY + 1):
                if H <= usable_h(gy):
                    units = gx * gy
                    adj   = adjacency_score(perm, prefer_adjacent)
                    ls, _, _ = compute_label_size(flat, gx, gy, W)
                    # primary: printable? (penalty if below MIN_PRINTABLE)
                    # secondary: fewer units; tertiary: bigger labels
                    # quaternary: squareness (prefer square over long/thin); quinary: adjacency
                    penalty = 1000 if ls < MIN_PRINTABLE else 0
                    squareness = max(gx / gy, gy / gx)
                    cand = (penalty + units, -ls, squareness, adj, gx, gy, W, perm)
                    if best is None or cand[:4] < best[:4]:
                        best = cand
                    break

    if best is None:
        raise ValueError(f"No valid bin found within {MAX_GX}×{MAX_GY}.")

    units, _, _sq, adj, gx, gy, W, perm = best
    ordered_groups = OrderedDict((k, groups[k]) for k in perm)
    flat = flatten(ordered_groups)
    label_size, v_lim, h_lim = compute_label_size(flat, gx, gy, W)

    # Print candidate table (deduplicated by bin size)
    size_seen = set()
    print("// ── Gridfinity size candidates ──────────────────────────────────")
    for p in permutations(group_names):
        od   = OrderedDict((k, groups[k]) for k in p)
        fl   = flatten(od)
        for gx2 in range(1, MAX_GX + 1):
            W2 = usable_w(gx2)
            try:
                H2 = content_height(fl, W2, MIN_LABEL)
            except ValueError:
                continue
            for gy2 in range(1, MAX_GY + 1):
                if H2 <= usable_h(gy2):
                    key = (gx2, gy2)
                    if key not in size_seen:
                        size_seen.add(key)
                        u   = gx2 * gy2
                        ls2, _, _ = compute_label_size(fl, gx2, gy2, W2)
                        mark = " ◄ optimal" if u == units else ""
                        print(f"//   {gx2}×{gy2} = {u:2d} units  "
                              f"({gx2*GRID_UNIT:.0f}×{gy2*GRID_UNIT:.0f}mm, "
                              f"content {W2:.1f}×{H2:.1f}mm, "
                              f"label {ls2:.2f}mm){mark}")
                    break

    print(f"// Group order: {' → '.join(perm)}")
    print(f"// Label size: {label_size:.2f}mm  "
          f"(v-limit {v_lim:.2f}mm, h-limit {h_lim:.2f}mm)")
    print("//")
    return ordered_groups, gx, gy, W, label_size

# ─── Assign coordinates ───────────────────────────────────────────────────────

def layout_coordinates(groups, W, label_size, gy=None):
    """
    Returns (placed, H, scad_zones, actual_label_size) where
    placed = [(group, label, r, cx, cy, label_cx, label_cy), ...] in OpenSCAD coords.
    Circle positions are computed from row structure; label positions are 2D-optimised.
    """
    flat = flatten(groups)
    _, rows = best_splits(flat, W, label_size)

    raw    = []   # (g, lbl, r, cx_down, cy_down)  — pre-conversion coords
    zones  = []
    y_down = 0.0

    for ri, row in enumerate(rows):
        if ri > 0:
            y_down += ROW_GAP
        max_r = max(r for _, _, r in row)

        xs, x = [], WALL
        for i, (g, _, r) in enumerate(row):
            if i > 0:
                x += INTER_GROUP_GAP if g != row[i-1][0] else CYL_GAP
            x += r
            xs.append(x)
            x += r

        row_used_w = x + WALL
        x_shift = (W - row_used_w) / 2
        xs = [xi + x_shift for xi in xs]

        for (g, lbl, r), cx in zip(row, xs):
            cy_down = y_down + (max_r - r)
            raw.append((g, lbl, r, cx, cy_down))

        lv = label_v_space(row, label_size)
        zones.append({
            "cyl_top":     y_down,
            "cyl_bot":     y_down + 2*max_r,
            "label_top":   y_down + 2*max_r + LABEL_BELOW,
            "label_bot":   y_down + 2*max_r + LABEL_BELOW + lv,
            "row_gap_bot": y_down + 2*max_r + LABEL_BELOW + lv + (ROW_GAP if ri < len(rows)-1 else 0),
        })
        y_down += 2*max_r + LABEL_BELOW + lv

    H = y_down

    # Convert circle centres to OpenSCAD centred coords
    circles_scad = [
        (g, lbl, r, cx - W/2, H/2 - (cy_down + r))
        for g, lbl, r, cx, cy_down in raw
    ]

    # 2D label placement
    H_usable = (gy * GRID_UNIT - 2*WALL) if gy is not None else H
    actual_label_size, label_positions = find_max_label_size_2d(circles_scad, W, H_usable)

    result = [
        (g, lbl, r, cx_s, cy_s, lx, ly)
        for (g, lbl, r, cx_s, cy_s), (lx, ly)
        in zip(circles_scad, label_positions)
    ]

    scad_zones = [{k: H/2 - v for k, v in z.items()} for z in zones]
    return result, H, scad_zones, actual_label_size

# ─── OpenSCAD output ──────────────────────────────────────────────────────────

def write_openscad(placed, gx, gy, W, H, label_size, out_path):
    BASE_H = 4.65   # gridfinity base height (h_base in standard.scad)
    gridz  = max(3, math.ceil((SOCKET_DEPTH + BASE_H) / 7))
    bin_w, bin_h = gx * GRID_UNIT, gy * GRID_UNIT

    L = []
    def p(s=""): L.append(s)

    p("// Generated by socket_layout.py")
    p(f"// Bin: {gx}×{gy} gridfinity units  ({bin_w:.0f}×{bin_h:.0f}mm)")
    p(f"// Content: {W:.1f}×{H:.1f}mm  "
      f"(margins: x={(bin_w-W)/2:.1f}mm, y={(bin_h-H)/2:.1f}mm)")
    p()
    p("include <src/core/standard.scad>")
    p("use <src/core/gridfinity-rebuilt-utility.scad>")
    p("use <src/core/gridfinity-rebuilt-holes.scad>")
    p("use <src/core/bin.scad>")
    p("use <src/core/cutouts.scad>")
    p("use <src/helpers/generic-helpers.scad>")
    p("use <src/helpers/grid.scad>")
    p("use <src/helpers/grid_element.scad>")
    p()
    p("$fa = $preview ? 10 : 4;")
    p("$fs = $preview ? 1.5 : 0.25;")
    p()
    p(f"gridx = {gx};")
    p(f"gridy = {gy};")
    p(f"gridz = {gridz};  // {gridz*7}mm total height; fits {SOCKET_DEPTH}mm socket depth")
    p()
    p("gridz_define = 0;")
    p("height_internal = 0;")
    p("enable_zsnap = false;")
    p("include_lip = true;")
    p("half_grid = false;")
    p()
    p("only_corners = false;")
    p("refined_holes = true;")
    p("magnet_holes = false;")
    p("screw_holes = false;")
    p("crush_ribs = true;")
    p("chamfer_holes = true;")
    p("printable_hole_top = true;")
    p("enable_thumbscrew = false;")
    p()
    p("hole_options = bundle_hole_options(refined_holes, magnet_holes, screw_holes,")
    p("                                   crush_ribs, chamfer_holes, printable_hole_top);")
    p()
    p("bin1 = new_bin(")
    p("    grid_size       = [gridx, gridy],")
    p("    height_mm       = height(gridz, gridz_define, enable_zsnap),")
    p("    fill_height     = height_internal,")
    p("    include_lip     = include_lip,")
    p("    hole_options    = hole_options,")
    p("    only_corners    = only_corners || half_grid,")
    p("    thumbscrew      = enable_thumbscrew,")
    p("    grid_dimensions = GRID_DIMENSIONS_MM / (half_grid ? 2 : 1)")
    p(");")
    p()
    p(f"socket_depth = {SOCKET_DEPTH};")
    p(f"c_chamfer    = {CHAMFER};")
    p( "label_height = 0.6;")
    p(f"label_size   = {label_size:.2f};")
    p( 'label_font   = "Liberation Sans:style=Bold";')
    p( "label_z = BASE_HEIGHT + bin_get_infill_size_mm(bin1).z + TOLLERANCE;")
    p()
    p("bin_render(bin1) {")
    cur = None
    for g, lbl, r, cx, cy, lx, ly in placed:
        if g != cur:
            p(f"\n    // === {g} ===")
            cur = g
        p(f"    translate([{cx:8.3f}, {cy:8.3f}])"
          f" cut_chamfered_cylinder({r}, socket_depth, c_chamfer);  // {lbl}")
    p("}")
    p()
    p("translate([0, 0, label_z]) {")
    cur = None
    for g, lbl, r, cx, cy, lx, ly in placed:
        if g != cur:
            p(f"\n    // === {g} ===")
            cur = g
        esc = lbl.replace('"', '\\"')
        rot = " rotate([0, 0, -90])" if ROTATE_LABELS else ""
        p(f'    translate([{lx:8.3f}, {ly:8.3f}])'
          f"{rot}"
          f" linear_extrude(label_height)"
          f' text("{esc}", size=label_size, font=label_font,'
          f' halign="center", valign="center");')
    p("}")

    out_path.write_text("\n".join(L) + "\n")
    print(f"// Written: {out_path}", file=sys.stderr)

# ─── SVG preview ──────────────────────────────────────────────────────────────

PALETTE = [
    ("#4e9af1", "#2a6fc4"),
    ("#f1a44e", "#c47020"),
    ("#4ef19a", "#20c460"),
    ("#f14e7a", "#c4204a"),
    ("#c084f1", "#8040c4"),
    ("#f1f14e", "#b0b020"),
]

def write_svg(placed, gx, gy, W, H, label_size, zones, out_path):
    bin_w, bin_h = gx * GRID_UNIT, gy * GRID_UNIT
    PAD   = 20
    SCALE = min(6.0, 900 / max(bin_w, bin_h))
    svg_w = bin_w * SCALE + 2*PAD
    svg_h = bin_h * SCALE + 2*PAD

    def sx(x): return PAD + (x + bin_w/2) * SCALE
    def sy(y): return PAD + (bin_h/2 - y) * SCALE

    group_names = list(dict.fromkeys(g for g, *_ in placed))
    color = {g: PALETTE[i % len(PALETTE)] for i, g in enumerate(group_names)}

    L = []
    L.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
             f'width="{svg_w:.0f}" height="{svg_h:.0f}">')
    L.append(f'<rect width="{svg_w:.0f}" height="{svg_h:.0f}" fill="#1e1e1e"/>')

    # Grid
    for i in range(gx + 1):
        x = PAD + i * GRID_UNIT * SCALE
        L.append(f'<line x1="{x:.1f}" y1="{PAD:.1f}" x2="{x:.1f}" '
                 f'y2="{PAD+bin_h*SCALE:.1f}" stroke="#2a2a2a" stroke-width="1"/>')
    for j in range(gy + 1):
        y = PAD + j * GRID_UNIT * SCALE
        L.append(f'<line x1="{PAD:.1f}" y1="{y:.1f}" '
                 f'x2="{PAD+bin_w*SCALE:.1f}" y2="{y:.1f}" stroke="#2a2a2a" stroke-width="1"/>')

    # Bin + content outlines
    L.append(f'<rect x="{PAD}" y="{PAD}" '
             f'width="{bin_w*SCALE:.1f}" height="{bin_h*SCALE:.1f}" '
             f'fill="none" stroke="#555" stroke-width="2"/>')
    L.append(f'<rect x="{sx(-W/2):.1f}" y="{sy(H/2):.1f}" '
             f'width="{W*SCALE:.1f}" height="{H*SCALE:.1f}" '
             f'fill="none" stroke="#383838" stroke-width="1" stroke-dasharray="4,3"/>')

    # Zone bands — full-width strips showing what each mm is used for
    zx  = sx(-W/2)
    zw  = W * SCALE
    for z in zones:
        # cylinder zone (tallest circle in row)
        cy_top = sy(z["cyl_top"])
        cy_bot = sy(z["cyl_bot"])
        L.append(f'<rect x="{zx:.1f}" y="{cy_bot:.1f}" width="{zw:.1f}" '
                 f'height="{cy_top-cy_bot:.1f}" '
                 f'fill="#3a3a5a" fill-opacity="0.4" stroke="none"/>')
        # LABEL_BELOW gap
        lb_top = sy(z["label_top"])
        lb_bot = sy(z["cyl_bot"])
        if lb_bot - lb_top > 0.5:
            L.append(f'<rect x="{zx:.1f}" y="{lb_top:.1f}" width="{zw:.1f}" '
                     f'height="{lb_bot-lb_top:.1f}" '
                     f'fill="#5a3a3a" fill-opacity="0.5" stroke="none"/>')
        # label zone
        lz_top = sy(z["label_bot"])
        lz_bot = sy(z["label_top"])
        L.append(f'<rect x="{zx:.1f}" y="{lz_top:.1f}" width="{zw:.1f}" '
                 f'height="{lz_bot-lz_top:.1f}" '
                 f'fill="#3a5a3a" fill-opacity="0.5" stroke="none"/>')
        # ROW_GAP
        rg_top = sy(z["row_gap_bot"])
        rg_bot = sy(z["label_bot"])
        if rg_bot - rg_top > 0.5:
            L.append(f'<rect x="{zx:.1f}" y="{rg_top:.1f}" width="{zw:.1f}" '
                     f'height="{rg_bot-rg_top:.1f}" '
                     f'fill="#5a4a2a" fill-opacity="0.5" stroke="none"/>')

    # Zone legend (bottom-left)
    zone_items = [
        ("#3a3a5a", "cylinder height (2×max_r)"),
        ("#5a3a3a", f"LABEL_BELOW ({LABEL_BELOW}mm)"),
        ("#3a5a3a", f"label zone ({label_size:.2f}mm)"),
        ("#5a4a2a", f"ROW_GAP ({ROW_GAP}mm)"),
    ]
    zlx = PAD + 4
    zly = svg_h - PAD - 4 - len(zone_items) * 16
    for col, desc in zone_items:
        L.append(f'<rect x="{zlx}" y="{zly-10}" width="12" height="12" '
                 f'fill="{col}" fill-opacity="0.8"/>')
        L.append(f'<text x="{zlx+16}" y="{zly}" font-family="monospace" '
                 f'font-size="11px" fill="#aaa">{desc}</text>')
        zly += 16

    # Sockets + labels
    for g, lbl, r, cx, cy, label_cx, label_cy in placed:
        fill, stroke = color[g]
        pcx, pcy, pr = sx(cx), sy(cy), r * SCALE
        L.append(f'<circle cx="{pcx:.1f}" cy="{pcy:.1f}" r="{pr:.1f}" '
                 f'fill="{fill}" fill-opacity="0.3" stroke="{stroke}" stroke-width="1.5"/>')
        L.append(f'<circle cx="{pcx:.1f}" cy="{pcy:.1f}" r="1.5" fill="{stroke}"/>')
        # connector line from circle to label if offset
        plx, ply = sx(label_cx), sy(label_cy)
        if abs(label_cx - cx) > 1 or abs(label_cy - cy) > r + 2:
            L.append(f'<line x1="{pcx:.1f}" y1="{pcy:.1f}" x2="{plx:.1f}" y2="{ply:.1f}" '
                     f'stroke="{stroke}" stroke-width="0.5" stroke-opacity="0.4"/>')
        fs = max(7, label_size * SCALE * 0.85)
        rot_attr = f' transform="rotate(90, {plx:.1f}, {ply:.1f})"' if ROTATE_LABELS else ''
        L.append(f'<text x="{plx:.1f}" y="{ply:.1f}" '
                 f'font-family="monospace" font-size="{fs:.1f}px" fill="white" '
                 f'text-anchor="middle" dominant-baseline="middle"'
                 f'{rot_attr}>{lbl}</text>')

    # Legend
    lx, ly = svg_w - PAD - 5, PAD + 14
    for g in group_names:
        fill, stroke = color[g]
        L.append(f'<rect x="{lx-90:.1f}" y="{ly-11:.1f}" width="12" height="12" '
                 f'fill="{fill}" fill-opacity="0.5" stroke="{stroke}" stroke-width="1"/>')
        L.append(f'<text x="{lx-74:.1f}" y="{ly:.1f}" '
                 f'font-family="monospace" font-size="12px" fill="#ccc">{g}</text>')
        ly += 18

    stats = (f"Bin: {gx}×{gy} gridfinity ({bin_w:.0f}×{bin_h:.0f}mm)   "
             f"content {W:.1f}×{H:.1f}mm   label {label_size:.2f}mm")
    L.append(f'<text x="{PAD}" y="{svg_h-6:.1f}" '
             f'font-family="monospace" font-size="11px" fill="#666">{stats}</text>')
    L.append('</svg>')

    out_path.write_text('\n'.join(L))
    print(f"// Preview: {out_path}", file=sys.stderr)
    subprocess.run(["open", str(out_path)], check=False)

# ─── Interactive HTML editor ──────────────────────────────────────────────────

def write_html(placed, gx, gy, W, H, label_size, out_path):
    import json
    BASE_H = 4.65
    gridz  = max(3, math.ceil((SOCKET_DEPTH + BASE_H) / 7))
    bin_w, bin_h = gx * GRID_UNIT, gy * GRID_UNIT

    sockets, seen_groups = [], []
    for g, lbl, r, cx, cy, lx, ly in placed:
        if g not in seen_groups:
            seen_groups.append(g)
        sockets.append(dict(group=g, label=lbl, r=r,
                            cx=round(cx, 3), cy=round(cy, 3),
                            lx=round(lx, 3), ly=round(ly, 3), tilt=0, horiz=False))

    data = dict(gx=gx, gy=gy, gridz=gridz, bin_w=bin_w, bin_h=bin_h,
                W=W, H=H, label_size=round(label_size, 3),
                socket_depth=SOCKET_DEPTH, chamfer=CHAMFER,
                groups=seen_groups, sockets=sockets)

    html = _HTML_TEMPLATE.replace('/*DATA*/', json.dumps(data))
    out_path.write_text(html)
    print(f"// HTML editor: {out_path}", file=sys.stderr)
    subprocess.run(["open", str(out_path)], check=False)

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Socket Layout Editor</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#111827;color:#e2e8f0;font-family:'Courier New',monospace;display:flex;flex-direction:column;height:100vh;overflow:hidden}
#toolbar{background:#1f2937;border-bottom:1px solid #374151;padding:8px 12px;display:flex;gap:8px;align-items:center;flex-shrink:0;flex-wrap:wrap}
button{background:#374151;color:#d1d5db;border:1px solid #4b5563;padding:5px 12px;cursor:pointer;border-radius:4px;font:inherit;font-size:12px}
button:hover{background:#4b5563}button:disabled{opacity:.4;cursor:default}
button.active{background:#1d4ed8;border-color:#3b82f6;color:#fff}
#hint{color:#6b7280;font-size:11px;margin-left:8px}
#main{display:flex;flex:1;overflow:hidden}
#canvas-wrap{flex:1;overflow:auto;background:#0d1117;padding:20px;position:relative}
svg{display:block;background:#0d1117}
svg.add-mode{cursor:crosshair}
#side{width:360px;min-width:360px;background:#1f2937;border-left:1px solid #374151;display:flex;flex-direction:column}
#side-hdr{padding:8px 12px;border-bottom:1px solid #374151;font-size:11px;color:#9ca3af;display:flex;justify-content:space-between}
#scad-out{flex:1;overflow:auto;background:#0d1117;color:#6ee7b7;font-size:10px;padding:10px;white-space:pre;line-height:1.4}
.label-g{cursor:grab;user-select:none}.label-g:active{cursor:grabbing}
.label-g.sel rect.bg,.circle-g.sel circle.main,.circle-g.sel ellipse.main,.circle-g.sel rect.main{stroke:#fbbf24 !important;stroke-width:1.2px !important}
.circle-g{cursor:grab;user-select:none}.circle-g:active{cursor:grabbing}
#add-popup{display:none;position:absolute;background:#1f2937;border:1px solid #4b5563;border-radius:6px;padding:12px;z-index:100;width:200px;box-shadow:0 4px 16px #0008}
#add-popup label{font-size:11px;color:#9ca3af;display:block;margin-bottom:2px}
#add-popup input,#add-popup select{width:100%;background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:4px 6px;font:inherit;font-size:12px;margin-bottom:8px}
#add-popup .btns{display:flex;gap:6px}
#add-popup .btns button{flex:1;font-size:11px;padding:4px}
#bulk-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:300;align-items:center;justify-content:center}
#bulk-box{background:#1f2937;border:1px solid #374151;border-radius:8px;padding:16px;width:760px;max-height:85vh;display:flex;flex-direction:column;gap:10px}
#bulk-box h3{margin:0;font-size:13px;color:#e2e8f0}
#bulk-scroll{overflow-y:auto;flex:1}
#bulk-table{width:100%;border-collapse:collapse;font-size:11px}
#bulk-table th{background:#111827;color:#9ca3af;padding:4px 6px;text-align:left;position:sticky;top:0;font-weight:normal}
#bulk-table td{padding:2px 3px;border-bottom:1px solid #1f2937}
#bulk-table input,#bulk-table select{background:#111827;color:#e2e8f0;border:1px solid #374151;border-radius:3px;padding:3px 5px;font:inherit;font-size:11px;width:100%}
#bulk-table input:focus,#bulk-table select:focus{outline:none;border-color:#6366f1}
#bulk-table td.del-col{width:24px;text-align:center}
#bulk-table td.del-col button{background:none;border:none;color:#6b7280;cursor:pointer;font-size:13px;padding:0 4px}
#bulk-table td.del-col button:hover{color:#ef4444}
#bulk-foot{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
</style></head><body>
<div id="toolbar">
  <button onclick="resetAll()">&#8635; Reset All</button>
  <button id="btn-reset" onclick="resetSel()" disabled>&#8635; Reset</button>
  <button id="btn-add" onclick="toggleAddMode()">+ Add Socket</button>
  <button onclick="openBulk()">&#9776; Bulk Add</button>
  <button id="btn-del" onclick="deleteSel()" disabled>&#128465; Delete</button>
  <button onclick="copyScad()">&#10064; Copy SCAD</button>
  <button id="btn-save" onclick="saveToFile()">&#128190; Save .scad</button>
  <button onclick="dlScad()">&#8595; Download</button>
  <label style="background:#374151;color:#d1d5db;border:1px solid #4b5563;padding:5px 12px;cursor:pointer;border-radius:4px;font-size:12px">
    &#8593; Load .scad <input type="file" accept=".scad" style="display:none" onchange="loadScad(this)">
  </label>
  <button onclick="clearSaved()" title="Clear localStorage and reset">&#128465; Clear saved</button>
  <span style="display:flex;align-items:center;gap:5px;border-left:1px solid #4b5563;padding-left:10px;font-size:11px;color:#9ca3af;flex-shrink:0">
    Socket depth:
    <input id="bin-depth" type="number" step="0.01" min="0.01" style="background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:3px 5px;font:inherit;font-size:12px;width:52px">
    <span>mm &nbsp;&nbsp; Internal depth:</span>
    <input id="bin-gridz" type="number" step="0.5" min="1" title="Internal usable depth mm; total = this + 7mm base" style="background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:3px 5px;font:inherit;font-size:12px;width:52px">
    <span id="bin-mm" style="color:#e2e8f0"></span>
    <button onclick="setMinGridz()" title="Set internal depth to match socket depth" style="padding:3px 8px;font-size:11px">&#9660; Min</button>
  </span>
  <span style="display:flex;align-items:center;gap:5px;border-left:1px solid #4b5563;padding-left:10px;font-size:11px;color:#9ca3af;flex-shrink:0">
    Bin:
    <input id="bin-gx" type="number" step="1" min="1" max="8" title="gridfinity columns (x)" style="background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:3px 5px;font:inherit;font-size:12px;width:36px">
    <span>&times;</span>
    <input id="bin-gy" type="number" step="1" min="1" max="8" title="gridfinity rows (y)" style="background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:3px 5px;font:inherit;font-size:12px;width:36px">
    <span id="bin-size-mm" style="color:#e2e8f0"></span>
  </span>
  <span style="display:flex;align-items:center;gap:5px;border-left:1px solid #4b5563;padding-left:10px;font-size:11px;color:#9ca3af;flex-shrink:0">
    Magnet &#8960;
    <input id="mag-diam" type="number" step="0.01" min="1" value="8" title="Magnet diameter (mm)" style="background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:3px 5px;font:inherit;font-size:12px;width:52px">
    mm&nbsp;depth
    <input id="mag-depth-inp" type="number" step="0.01" min="0.01" value="2.75" title="Magnet depth (mm)" style="background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:3px 5px;font:inherit;font-size:12px;width:52px">
    mm
  </span>
  <span id="hint">Drag labels &middot; Shift = no snap &middot; R = reset &middot; Del = delete &middot; auto-saved</span>
  <span id="props" style="display:none;align-items:center;gap:5px;border-left:1px solid #4b5563;padding-left:10px;margin-left:4px">
    <span style="font-size:11px;color:#9ca3af">Label:</span>
    <input id="prop-label" style="background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:3px 5px;font:inherit;font-size:12px;width:65px">
    <select id="prop-group" title="Group" style="background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:3px 5px;font:inherit;font-size:12px"></select>
    <span style="font-size:11px;color:#9ca3af">&nbsp;&#8960; mm:</span>
    <input id="prop-diam" type="number" step="0.01" min="0.01" style="background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:3px 5px;font:inherit;font-size:12px;width:62px">
    <span id="tilt-ctrl" style="display:contents">
      <span style="font-size:11px;color:#9ca3af">&nbsp;Tilt&deg;:</span>
      <input id="prop-tilt" type="number" step="5" min="0" max="80" title="Tilt angle toward back wall (0=vertical)" style="background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:3px 5px;font:inherit;font-size:12px;width:52px">
    </span>
    <button id="btn-horiz" onclick="toggleHoriz()" title="Switch to horizontal cylinder (lay on side)" style="padding:3px 8px;font-size:11px;margin-left:4px">&#8596; Horiz</button>
    <label style="display:flex;align-items:center;gap:4px;cursor:pointer;font-size:11px;color:#9ca3af;margin-left:6px;border-left:1px solid #374151;padding-left:8px">
      <input type="checkbox" id="chk-mag" onchange="setMag(this.checked)"> Magnet
    </label>
    <span id="horiz-ctrl" style="display:none;align-items:center;gap:4px;border-left:1px solid #374151;padding-left:8px;margin-left:2px">
      <span style="font-size:11px;color:#9ca3af">Len mm:</span>
      <input id="prop-len" type="number" step="1" min="1" style="background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:3px 5px;font:inherit;font-size:12px;width:58px">
      <span style="font-size:11px;color:#9ca3af">Rotate&deg;:</span>
      <button onclick="adjustHorizAngle(-45)" style="padding:3px 6px;font-size:11px" title="-45°">&#8722;45</button>
      <button onclick="adjustHorizAngle(-15)" style="padding:3px 6px;font-size:11px" title="-15°">&#8722;15</button>
      <input id="prop-angle" type="number" step="1" style="background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:3px 5px;font:inherit;font-size:12px;width:52px">
      <button onclick="adjustHorizAngle(15)" style="padding:3px 6px;font-size:11px" title="+15°">+15</button>
      <button onclick="adjustHorizAngle(45)" style="padding:3px 6px;font-size:11px" title="+45°">+45</button>
    </span>
    <span id="spacing-ctrl" style="display:none;align-items:center;gap:4px;border-left:1px solid #374151;padding-left:8px;margin-left:2px">
      <span style="font-size:11px;color:#9ca3af">Gap mm:</span>
      <button onclick="adjustSpacing(-1)" style="padding:3px 7px" title="−1mm">&#8722;1</button>
      <button onclick="adjustSpacing(-0.1)" style="padding:3px 7px" title="−0.1mm">&#8722;.1</button>
      <input id="spacing-val" type="number" step="0.01" min="0.01" title="Center-to-center spacing (mm)" style="background:#111827;color:#e2e8f0;border:1px solid #4b5563;border-radius:3px;padding:3px 5px;font:inherit;font-size:12px;width:62px">
      <button onclick="adjustSpacing(0.1)" style="padding:3px 7px" title="+0.1mm">+.1</button>
      <button onclick="adjustSpacing(1)" style="padding:3px 7px" title="+1mm">+1</button>
      <button onclick="equalizeSpacing()" style="padding:3px 8px" title="Make spacing equal">=</button>
    </span>
  </span>
  <span id="pos-info" style="margin-left:auto;color:#9ca3af;font-size:11px"></span>
</div>
<div id="main">
  <div id="canvas-wrap">
    <svg id="svg"></svg>
    <div id="add-popup">
      <label>Label</label><input id="ap-label" placeholder="e.g. 1/2">
      <label>Diameter (mm)</label><input id="ap-diam" type="number" step="0.01" min="0.01" placeholder="12.0">
      <label>Tilt angle (° toward back, 0=vertical)</label><input id="ap-tilt" type="number" step="5" min="0" max="80" placeholder="0">
      <label style="display:flex;align-items:center;gap:6px;cursor:pointer"><input id="ap-horiz" type="checkbox" onchange="document.getElementById('ap-len-row').style.display=this.checked?'block':'none'"> Horizontal (lay on side)</label>
      <div id="ap-len-row" style="display:none"><label>Length (mm)</label><input id="ap-len" type="number" step="1" min="1" placeholder="25"></div>
      <label style="display:flex;align-items:center;gap:6px;cursor:pointer"><input id="ap-mag" type="checkbox"> Magnet hole</label>
      <label>Group</label><select id="ap-group"></select>
      <div class="btns">
        <button onclick="confirmAdd()">Add</button>
        <button onclick="cancelAdd()">Cancel</button>
      </div>
    </div>
  </div>
  <!-- Bulk add modal -->
  <div id="bulk-overlay">
    <div id="bulk-box">
      <h3>&#9776; Bulk Add Sockets</h3>
      <div id="bulk-scroll">
        <table id="bulk-table">
          <thead><tr>
            <th style="width:70px">Label</th>
            <th style="width:62px">&#8960; mm</th>
            <th style="width:100px">Group</th>
            <th style="width:44px;text-align:center">Horiz</th>
            <th style="width:44px;text-align:center">Mag</th>
            <th style="width:58px">Len mm</th>
            <th style="width:52px">Angle&deg;</th>
            <th style="width:48px">Tilt&deg;</th>
            <th style="width:24px"></th>
          </tr></thead>
          <tbody id="bulk-body"></tbody>
        </table>
      </div>
      <div id="bulk-foot">
        <button onclick="addBulkRow()">+ Row</button>
        <button onclick="addBulkRows(5)" style="font-size:11px">+ 5 Rows</button>
        <button onclick="commitBulk()" style="background:#1d4ed8;border-color:#3b82f6;color:#fff">&#10003; Add All to Canvas</button>
        <button onclick="closeBulk()">Cancel</button>
        <span style="font-size:11px;color:#6b7280;margin-left:auto">Tip: paste tab-separated rows (Label ⇥ ⌀mm ⇥ Group ⇥ Horiz ⇥ Len ⇥ Angle ⇥ Tilt)</span>
      </div>
    </div>
  </div>
  <div id="side">
    <div id="side-hdr"><span>sockets.scad</span><span id="changed-count"></span></div>
    <div id="scad-out"></div>
  </div>
</div>
<script>
const D = /*DATA*/;

const MAR = 15;
let gx = D.gx, gy = D.gy;
let bin_w = gx * 42, bin_h = gy * 42;
function sx(x){ return x + bin_w/2 + MAR; }
function sy(y){ return -y + bin_h/2 + MAR; }
function fx(x){ return x - bin_w/2 - MAR; }
function fy(y){ return -(y - bin_h/2 - MAR); }
const LEG_ROWS = Math.ceil(D.groups.length / Math.ceil(D.groups.length / 2));
const LEG_H = LEG_ROWS * 7 + 6;
function getVW(){ return bin_w + 2*MAR; }
function getVH(){ return bin_h + 2*MAR + LEG_H; }
function getScale(){ return Math.min(800/getVW(), 900/getVH(), 5); }
let VW = getVW(), VH = getVH();

const COLORS = {
  'Imp Deep':    ['rgba(60,80,160,0.35)',  '#7090ee'],
  'Met Deep':    ['rgba(40,120,60,0.35)',  '#60d080'],
  'Imp Shallow': ['rgba(160,80,40,0.35)', '#e08050'],
  'Met Shallow': ['rgba(140,50,140,0.35)','#d060d0'],
};
const GROUPS = Object.keys(COLORS);
function gcol(g){ return COLORS[g] || ['rgba(80,80,80,0.3)','#aaa']; }
// Bounding half-extents for any socket (accounts for horiz angle)
function sockBounds(s){
  if(s.horiz){
    const a = (s.angle||0) * Math.PI / 180;
    const hw = Math.abs((s.len||25)/2 * Math.cos(a)) + Math.abs(s.r * Math.sin(a));
    const hh = Math.abs((s.len||25)/2 * Math.sin(a)) + Math.abs(s.r * Math.cos(a));
    return {hw, hh};
  }
  return {hw: s.r, hh: s.r};
}

// mutable state
const sockets = D.sockets.map(s => ({...s, _added:false}));
const pos = sockets.map(s => ({lx:s.lx, ly:s.ly, lx0:s.lx, ly0:s.ly, cx0:s.cx, cy0:s.cy}));
let sel = -1, selSet = new Set(), drag = null, rubberBand = null, addMode = false, pendingAdd = null;
let socketDepth = D.socket_depth;
let magnetR = 4.0, magnetDepth = 2.75;
const BASE_HEIGHT_MM = 7;    // gridfinity base
const LIP_SUPPORT_MM = 1.2;  // STACKING_LIP_SUPPORT_HEIGHT — steals from usable depth
// gridz_define=1: total = binInternalMm + BASE_HEIGHT_MM
// usable hole depth = binInternalMm - LIP_SUPPORT_MM
// minimum binInternalMm = socketDepth + LIP_SUPPORT_MM
let binInternalMm = D.gridz * 7 - BASE_HEIGHT_MM;  // convert optimizer gridz → internal mm

const NS = 'http://www.w3.org/2000/svg';
const svg = document.getElementById('svg');

function el(tag, a={}, text){
  const e = document.createElementNS(NS, tag);
  for(const[k,v] of Object.entries(a)) e.setAttribute(k,v);
  if(text !== undefined) e.textContent = text;
  return e;
}
function app(parent, ...children){ children.forEach(c => parent.appendChild(c)); }

// static layer (redrawn on bin resize)
const staticL = el('g'); app(svg, staticL);

function drawStatic(){
  while(staticL.firstChild) staticL.removeChild(staticL.firstChild);
  app(staticL, el('rect',{x:MAR,y:MAR,width:bin_w,height:bin_h,fill:'none',stroke:'#374151','stroke-width':'0.6'}));
  for(let i=0;i<=gx;i++){
    const x=MAR+i*42;
    app(staticL, el('line',{x1:x,y1:MAR,x2:x,y2:MAR+bin_h,stroke:'#1e2d1e','stroke-width':'0.3'}));
  }
  for(let j=0;j<=gy;j++){
    const y=MAR+j*42;
    app(staticL, el('line',{x1:MAR,y1:y,x2:MAR+bin_w,y2:y,stroke:'#1e2d1e','stroke-width':'0.3'}));
  }
  const cols = Math.ceil(D.groups.length / 2);
  const itemW = bin_w / cols;
  D.groups.forEach((g,i)=>{
    const[fill,stroke]=gcol(g);
    const lx = MAR + (i % cols) * itemW + 2;
    const ly = MAR + bin_h + 5 + Math.floor(i / cols) * 7;
    app(staticL,
      el('rect',{x:lx,y:ly,width:7,height:4,fill,stroke,'stroke-width':'0.5','rx':'0.5'}),
      el('text',{x:lx+10,y:ly+3.5,'font-family':'monospace','font-size':'3.5',fill:'#9ca3af'},g));
  });
}

function rebuildViewport(){
  bin_w = gx * 42; bin_h = gy * 42;
  VW=getVW(); VH=getVH(); const SC=getScale();
  svg.setAttribute('width',  VW * SC);
  svg.setAttribute('height', VH * SC);
  svg.setAttribute('viewBox', `0 0 ${VW} ${VH}`);
  document.getElementById('bin-size-mm').textContent = `= ${bin_w}×${bin_h}mm`;
  drawStatic();
}

rebuildViewport();

// dynamic layers
const connL    = el('g'); app(svg, connL);
const snapL    = el('g'); app(svg, snapL);
const circlesL = el('g'); app(svg, circlesL);
const labelsL  = el('g'); app(svg, labelsL);
// rubber-band selection layer (topmost)
const rubberL  = el('g'); app(svg, rubberL);
const rubberRect = el('rect',{fill:'rgba(99,149,255,0.08)',stroke:'#6395ff',
  'stroke-width':'0.5','stroke-dasharray':'2,2',x:0,y:0,width:0,height:0,display:'none'});
app(rubberL, rubberRect);

let lEls = [], cEls = [];

// Build/rebuild the visual children of a circle group (event listeners on g are preserved)
function buildCircleVisual(g, s){
  while(g.firstChild) g.removeChild(g.firstChild);
  const [fill, stroke] = gcol(s.group);
  const cx_svg = sx(s.cx), cy_svg = sy(s.cy);
  if(s.horiz){
    const len = s.len || 20, r = s.r;
    const angle = s.angle || 0;  // degrees CCW in OpenSCAD (= CW in SVG since Y-flip)
    const a = angle * Math.PI / 180;
    // rotated bounding box for wall-clip warning
    const bx = Math.abs(len/2 * Math.cos(a)) + Math.abs(r * Math.sin(a));
    const by = Math.abs(len/2 * Math.sin(a)) + Math.abs(r * Math.cos(a));
    const warn = s.cx + bx > bin_w/2 || s.cx - bx < -bin_w/2
              || s.cy + by > bin_h/2 || s.cy - by < -bin_h/2;
    const sc = warn ? '#ef4444' : stroke;
    app(g,
      el('rect',{class:'main', x:cx_svg-len/2, y:cy_svg-r, width:len, height:2*r,
        rx:'1', fill, 'fill-opacity':'0.35', stroke:sc, 'stroke-width':'0.8',
        transform:`rotate(${-angle},${cx_svg},${cy_svg})`}),
      el('circle',{cx:cx_svg, cy:cy_svg, r:'0.7', fill:stroke, 'pointer-events':'none'})
    );
    return;
  }
  const tilt_rad = (s.tilt || 0) * Math.PI / 180;
  if(tilt_rad > 0.001){
    const ry = s.r * Math.cos(tilt_rad);
    const cy_back = cy_svg - socketDepth * Math.sin(tilt_rad);
    // warn if cylinder clips back wall (OpenSCAD +y = back = smaller SVG y)
    const backEdge = s.cy + socketDepth * Math.sin(tilt_rad) + s.r * Math.cos(tilt_rad);
    const warn = backEdge > bin_h / 2;
    const sc = warn ? '#ef4444' : stroke;
    // stadium silhouette: front semicap → right side → back semicap → left side
    const fp = `M ${cx_svg-s.r} ${cy_svg} A ${s.r} ${ry} 0 0 1 ${cx_svg+s.r} ${cy_svg} L ${cx_svg+s.r} ${cy_back} A ${s.r} ${ry} 0 0 1 ${cx_svg-s.r} ${cy_back} Z`;
    app(g,
      el('path',{d:fp, fill, 'fill-opacity':'0.12', stroke:sc, 'stroke-width':'0.4',
        'stroke-dasharray':'1.5,1', 'pointer-events':'none'}),
      el('line',{x1:cx_svg, y1:cy_svg, x2:cx_svg, y2:cy_back,
        stroke:sc, 'stroke-width':'0.3', 'stroke-opacity':'0.5', 'pointer-events':'none'}),
      el('ellipse',{class:'main', cx:cx_svg, cy:cy_svg, rx:s.r, ry,
        fill, stroke:sc, 'stroke-width':'0.8'}),
      el('circle',{cx:cx_svg, cy:cy_svg, r:'0.7', fill:stroke, 'pointer-events':'none'})
    );
  } else {
    app(g,
      el('circle',{class:'main', cx:cx_svg, cy:cy_svg, r:s.r, fill, stroke, 'stroke-width':'0.8'}),
      el('circle',{cx:cx_svg, cy:cy_svg, r:'0.7', fill:stroke, 'pointer-events':'none'})
    );
  }
  if(s._added){
    app(g, el('circle',{cx:cx_svg, cy:cy_svg, r:s.r+0.8, fill:'none', stroke:'#fbbf24',
      'stroke-width':'0.5', 'stroke-dasharray':'2,2', 'pointer-events':'none'}));
  }
  if(s.mag){
    app(g, el('circle',{cx:cx_svg, cy:cy_svg, r:magnetR, fill:'none', stroke:'#a78bfa',
      'stroke-width':'0.6', 'stroke-dasharray':'1.5,1.5', 'pointer-events':'none'}));
  }
}

function render(){
  while(circlesL.firstChild) circlesL.removeChild(circlesL.firstChild);
  cEls = [];
  for(let i=0;i<sockets.length;i++){
    const s=sockets[i];
    const g = el('g',{class:'circle-g'});
    buildCircleVisual(g, s);
    const idx=i;
    g.addEventListener('mousedown', e=>{ if(!addMode){ e.preventDefault(); e.stopPropagation(); if(e.shiftKey){ selectItem(idx, true); } else if(!selSet.has(idx)){ selectItem(idx); } startDragCircle(e,idx); }});
    app(circlesL, g);
    cEls.push(g);
  }

  while(labelsL.firstChild) labelsL.removeChild(labelsL.firstChild);
  lEls = [];
  for(let i=0;i<sockets.length;i++){
    const s=sockets[i];
    const[,stroke]=gcol(s.group);
    const lw = Math.max(s.label.length,1) * 0.62 * D.label_size;
    const lh = D.label_size;
    const g = el('g',{class:'label-g'});
    app(g,
      el('rect',{class:'bg',x:0,y:0,width:lw,height:lh,
        fill:'#111827',stroke,'stroke-width':'0.5',rx:'0.5','fill-opacity':'0.9'}),
      el('text',{x:lw/2,y:lh*0.74,'font-family':'monospace',
        'font-size':lh*0.82,fill:'#f0f0f0','text-anchor':'middle','pointer-events':'none'},
        s.label));
    const idx=i;
    g.addEventListener('mousedown', e=>{ if(!addMode){ e.preventDefault(); e.stopPropagation(); if(e.shiftKey){ selectItem(idx, true); } else if(!selSet.has(idx)){ selectItem(idx); } startDragLabel(e,idx); }});
    app(labelsL, g);
    lEls.push(g);
  }

  for(const i of selSet){
    if(i<lEls.length){ lEls[i].classList.add('sel'); cEls[i].classList.add('sel'); }
  }
  for(let i=0;i<sockets.length;i++) placeLabel(i);
  redrawConn();
  updateScad();
  updateBtns();
  showProps();
}

function placeLabel(i){
  const s = sockets[i];
  const lw = Math.max(s.label.length,1)*0.62*D.label_size;
  const lh = D.label_size;
  const {lx,ly} = pos[i];
  lEls[i].setAttribute('transform',`translate(${sx(lx)-lw/2},${sy(ly)-lh/2})`);
}
function placeCircle(i){
  buildCircleVisual(cEls[i], sockets[i]);
  if(selSet.has(i)) cEls[i].classList.add('sel');
}
function redrawConn(){
  while(connL.firstChild) connL.removeChild(connL.firstChild);
  for(let i=0;i<sockets.length;i++){
    const s=sockets[i]; const{lx,ly}=pos[i];
    const {hh} = sockBounds(s);
    if(Math.abs(lx-s.cx)>1.5 || Math.abs(ly-s.cy)>hh+2+0.5){
      const[,stroke]=gcol(s.group);
      app(connL, el('line',{x1:sx(s.cx),y1:sy(s.cy),x2:sx(lx),y2:sy(ly),
        stroke,'stroke-width':'0.4','stroke-opacity':'0.5','stroke-dasharray':'1.5,1.5'}));
    }
  }
}

// ── snap ─────────────────────────────────────────────────────────────────────
const SNAP = 3.5;
function clearSnapLines(){ while(snapL.firstChild) snapL.removeChild(snapL.firstChild); }
function drawSnapLines(snapX, snapY){
  clearSnapLines();
  if(snapX !== null)
    app(snapL, el('line',{x1:sx(snapX),y1:0,x2:sx(snapX),y2:VH,
      stroke:'#fbbf24','stroke-width':'0.4','stroke-opacity':'0.7','stroke-dasharray':'2,2'}));
  if(snapY !== null)
    app(snapL, el('line',{x1:0,y1:sy(snapY),x2:VW,y2:sy(snapY),
      stroke:'#34d399','stroke-width':'0.4','stroke-opacity':'0.7','stroke-dasharray':'2,2'}));
}
function applySnap(rawLx, rawLy, dragIdx){
  let snapX=null, snapXD=SNAP, snapY=null, snapYD=SNAP;
  // X: snap label center to own socket's center line
  const own = sockets[dragIdx];
  const d = Math.abs(rawLx - own.cx);
  if(d < snapXD){ snapX = own.cx; snapXD = d; }
  // X + Y: align with other labels
  for(let i=0;i<pos.length;i++){
    if(i===dragIdx) continue;
    const dx=Math.abs(rawLx-pos[i].lx); if(dx<snapXD){ snapX=pos[i].lx; snapXD=dx; }
    const dy=Math.abs(rawLy-pos[i].ly); if(dy<snapYD){ snapY=pos[i].ly; snapYD=dy; }
  }
  return { lx: snapX!==null ? snapX : rawLx, ly: snapY!==null ? snapY : rawLy, snapX, snapY };
}
function applySnapCircle(rawCx, rawCy, dragIdx){
  // Simple center-to-center snapping only — edge snapping adds too many targets
  let snapX=null, snapXD=SNAP, snapY=null, snapYD=SNAP;
  for(let i=0;i<sockets.length;i++){
    if(i===dragIdx) continue;
    const dx=Math.abs(rawCx-sockets[i].cx); if(dx<snapXD){ snapX=sockets[i].cx; snapXD=dx; }
    const dy=Math.abs(rawCy-sockets[i].cy); if(dy<snapYD){ snapY=sockets[i].cy; snapYD=dy; }
  }
  return { lx: snapX!==null ? snapX : rawCx, ly: snapY!==null ? snapY : rawCy, snapX, snapY };
}

// ── drag ─────────────────────────────────────────────────────────────────────
function svgPt(e){
  const p=svg.createSVGPoint(); p.x=e.clientX; p.y=e.clientY;
  return p.matrixTransform(svg.getScreenCTM().inverse());
}
function startDragLabel(e,i){
  const p=svgPt(e);
  if(selSet.size > 1)
    drag={type:'group', i, ox:p.x-sx(sockets[i].cx), oy:p.y-sy(sockets[i].cy)};
  else
    drag={type:'label', i, ox:p.x-sx(pos[i].lx), oy:p.y-sy(pos[i].ly)};
}
function startDragCircle(e,i){
  const p=svgPt(e);
  drag={type: selSet.size>1 ? 'group' : 'circle', i,
        ox:p.x-sx(sockets[i].cx), oy:p.y-sy(sockets[i].cy)};
}

svg.addEventListener('mousedown', e=>{
  if(addMode || drag) return;
  if(e.target.closest('.circle-g') || e.target.closest('.label-g')) return;
  const p=svgPt(e);
  rubberBand={sx:p.x, sy:p.y, ex:p.x, ey:p.y};
  rubberRect.removeAttribute('display');
  rubberRect.setAttribute('x', p.x); rubberRect.setAttribute('y', p.y);
  rubberRect.setAttribute('width', 0); rubberRect.setAttribute('height', 0);
});

svg.addEventListener('mousemove', e=>{
  const p=svgPt(e);
  if(rubberBand){
    rubberBand.ex=p.x; rubberBand.ey=p.y;
    const rx=Math.min(rubberBand.sx,p.x), ry=Math.min(rubberBand.sy,p.y);
    rubberRect.setAttribute('x',rx); rubberRect.setAttribute('y',ry);
    rubberRect.setAttribute('width', Math.abs(p.x-rubberBand.sx));
    rubberRect.setAttribute('height',Math.abs(p.y-rubberBand.sy));
    return;
  }
  if(!drag) return;
  const i=drag.i;
  if(drag.type==='group'){
    const rawCx=fx(p.x-drag.ox), rawCy=fy(p.y-drag.oy);
    const {lx:cx, ly:cy, snapX, snapY} = e.shiftKey
      ? {lx:rawCx, ly:rawCy, snapX:null, snapY:null}
      : applySnapCircle(rawCx, rawCy, i);
    const dcx=cx-sockets[i].cx, dcy=cy-sockets[i].cy;
    for(const j of selSet){
      sockets[j].cx+=dcx; sockets[j].cy+=dcy;
      pos[j].lx+=dcx; pos[j].ly+=dcy;
      placeCircle(j); placeLabel(j);
    }
    drawSnapLines(snapX, snapY);
    redrawConn(); updateScad(); updateInfo();
  } else if(drag.type==='circle'){
    const rawCx=fx(p.x-drag.ox), rawCy=fy(p.y-drag.oy);
    const {lx:cx, ly:cy, snapX, snapY} = e.shiftKey
      ? {lx:rawCx, ly:rawCy, snapX:null, snapY:null}
      : applySnapCircle(rawCx, rawCy, i);
    const dcx=cx-sockets[i].cx, dcy=cy-sockets[i].cy;
    sockets[i].cx=cx; sockets[i].cy=cy;
    pos[i].lx+=dcx; pos[i].ly+=dcy;
    drawSnapLines(snapX, snapY);
    placeCircle(i); placeLabel(i); redrawConn(); updateScad(); updateInfo();
  } else {
    const raw={lx:fx(p.x-drag.ox), ly:fy(p.y-drag.oy)};
    const {lx,ly,snapX,snapY} = e.shiftKey
      ? {lx:raw.lx, ly:raw.ly, snapX:null, snapY:null}
      : applySnap(raw.lx, raw.ly, i);
    pos[i].lx=lx; pos[i].ly=ly;
    drawSnapLines(snapX, snapY);
    placeLabel(i); redrawConn(); updateScad(); updateInfo();
  }
});

let _rbMoved = false;
svg.addEventListener('mouseup', e=>{
  if(rubberBand){
    const moved = Math.hypot(rubberBand.ex-rubberBand.sx, rubberBand.ey-rubberBand.sy);
    rubberRect.setAttribute('display','none');
    if(moved > 4){
      // Select all sockets whose centre is inside the rubber-band rect
      const minSX=Math.min(rubberBand.sx,rubberBand.ex), maxSX=Math.max(rubberBand.sx,rubberBand.ex);
      const minSY=Math.min(rubberBand.sy,rubberBand.ey), maxSY=Math.max(rubberBand.sy,rubberBand.ey);
      const enclosed = sockets.reduce((a,s,idx)=>{
        const px=sx(s.cx), py=sy(s.cy);
        if(px>=minSX&&px<=maxSX&&py>=minSY&&py<=maxSY) a.push(idx);
        return a;
      },[]);
      if(enclosed.length) selectSet(enclosed);
      _rbMoved = true;
    }
    rubberBand = null;
  }
  drag=null; clearSnapLines();
});
svg.addEventListener('mouseleave',()=>{ drag=null; rubberBand=null; rubberRect.setAttribute('display','none'); clearSnapLines(); });
svg.addEventListener('click', e=>{
  if(_rbMoved){ _rbMoved=false; return; }
  if(addMode){
    const p=svgPt(e);
    if(p.x>=MAR && p.x<=MAR+D.bin_w && p.y>=MAR && p.y<=MAR+D.bin_h) handleAddClick(e);
    return;
  }
  if(!e.target.closest('.label-g') && !e.target.closest('.circle-g')) selectItem(-1);
});

// ── selection ─────────────────────────────────────────────────────────────────
function _highlightSel(i, on){
  if(i>=0 && i<lEls.length){
    lEls[i].classList.toggle('sel', on);
    cEls[i].classList.toggle('sel', on);
  }
}
function selectItem(i, toggle=false){
  if(i < 0){
    selSet.forEach(j=>_highlightSel(j,false));
    selSet.clear(); sel=-1;
  } else if(toggle){
    if(selSet.has(i)){
      selSet.delete(i); _highlightSel(i,false);
      sel = selSet.size>0 ? [...selSet][selSet.size-1] : -1;
    } else {
      selSet.add(i); _highlightSel(i,true); sel=i;
    }
  } else {
    selSet.forEach(j=>_highlightSel(j,false));
    selSet.clear(); selSet.add(i); _highlightSel(i,true); sel=i;
  }
  updateBtns(); updateInfo(); showProps();
}
function selectSet(indices){
  selSet.forEach(j=>_highlightSel(j,false));
  selSet.clear(); sel=-1;
  for(const i of indices){ selSet.add(i); _highlightSel(i,true); sel=i; }
  updateBtns(); updateInfo(); showProps();
}
function updateBtns(){
  document.getElementById('btn-reset').disabled = selSet.size===0;
  document.getElementById('btn-del').disabled   = selSet.size===0;
}
document.addEventListener('keydown', e=>{
  if((e.key==='r'||e.key==='R')&&!e.ctrlKey&&!e.metaKey) resetSel();
  if(e.key==='Escape'){ selectItem(-1); if(addMode) toggleAddMode(); }
  if((e.key==='Delete'||e.key==='Backspace')&&!e.ctrlKey&&!e.metaKey&&
     !['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName)) deleteSel();
});

// ── bulk add ──────────────────────────────────────────────────────────────────
function openBulk(){
  document.getElementById('bulk-overlay').style.display='flex';
  const tbody = document.getElementById('bulk-body');
  if(tbody.rows.length === 0) addBulkRows(5);
}
function closeBulk(){
  document.getElementById('bulk-overlay').style.display='none';
}
function makeBulkRow(data){
  const tr = document.createElement('tr');
  const d = data || {};
  const groupOpts = GROUPS.map(g=>`<option value="${g}" ${g===(d.group||GROUPS[0])?'selected':''}>${g}</option>`).join('');
  tr.innerHTML = `
    <td><input type="text" value="${d.label||''}" placeholder="label" style="width:70px"></td>
    <td><input type="number" value="${d.diam||12}" min="0.01" max="60" step="0.01" style="width:55px"></td>
    <td><select style="width:100px">${groupOpts}</select></td>
    <td><input type="checkbox" ${d.horiz?'checked':''}></td>
    <td style="text-align:center"><input type="checkbox" ${d.mag?'checked':''}></td>
    <td><input type="number" value="${d.len||25}" min="1" max="200" step="0.5" style="width:50px"></td>
    <td><input type="number" value="${d.angle||0}" min="0" max="179" step="1" style="width:45px"></td>
    <td><input type="number" value="${d.tilt||0}" min="0" max="89" step="1" style="width:45px"></td>
    <td><button onclick="this.closest('tr').remove()" style="padding:2px 6px;font-size:10px">✕</button></td>`;
  return tr;
}
function addBulkRow(data){
  document.getElementById('bulk-body').appendChild(makeBulkRow(data));
}
function addBulkRows(n){
  for(let i=0;i<n;i++) addBulkRow();
}
function autoLayout(newSocks){
  const gap = 4;
  // Start below the lowest existing socket so new batch doesn't overlap
  let startY = bin_h/2 - gap;
  for(const s of sockets){
    const {hh} = sockBounds(s);
    startY = Math.min(startY, s.cy - hh - gap);
  }
  let x = -bin_w/2 + gap;
  let y = startY;
  let rowH = 0;
  for(const s of newSocks){
    const {hw, hh} = sockBounds(s);
    // wrap to next row if this socket would overflow the right edge
    if(x > -bin_w/2 + gap && x + hw > bin_w/2 - gap){
      x = -bin_w/2 + gap;
      y -= rowH + gap;
      rowH = 0;
    }
    s.cx = parseFloat((x + hw).toFixed(3));
    s.cy = parseFloat((y - hh).toFixed(3));
    x += hw*2 + gap;
    rowH = Math.max(rowH, hh*2);
  }
}
function commitBulk(){
  const tbody = document.getElementById('bulk-body');
  const newSocks = [];
  for(const tr of tbody.rows){
    const cells = tr.cells;
    const label = cells[0].querySelector('input').value.trim();
    const diam  = parseFloat(cells[1].querySelector('input').value) || 12;
    const group = cells[2].querySelector('select').value;
    const horiz = cells[3].querySelector('input').checked;
    const mag   = cells[4].querySelector('input').checked;
    const len   = parseFloat(cells[5].querySelector('input').value) || 25;
    const angle = parseFloat(cells[6].querySelector('input').value) || 0;
    const tilt  = parseFloat(cells[7].querySelector('input').value) || 0;
    if(!label) continue;
    newSocks.push({label, r: diam/2, group, horiz, mag, len, angle, tilt,
                   cx:0, cy:0, lx:0, ly:0, _added:true});
  }
  if(!newSocks.length){ closeBulk(); return; }
  autoLayout(newSocks);
  for(const s of newSocks){
    const {hh} = sockBounds(s);
    s.lx = s.cx;
    s.ly = s.cy - hh - 2;
    sockets.push(s);
    pos.push({cx0:s.cx, cy0:s.cy, lx0:s.lx, ly0:s.ly,
              lx:s.lx, ly:s.ly});
  }
  closeBulk();
  render();
  updateScad();
}
// paste support: tab+newline separated data into bulk table
document.addEventListener('paste', function(e){
  if(document.getElementById('bulk-overlay').style.display !== 'flex') return;
  const text = (e.clipboardData || window.clipboardData).getData('text');
  if(!text) return;
  const lines = text.trim().split(/\r?\n/);
  if(lines.length < 1) return;
  e.preventDefault();
  for(const line of lines){
    const cols = line.split('\t');
    const data = {
      label: cols[0]||'',
      diam:  parseFloat(cols[1])||12,
      group: GROUPS.includes(cols[2]) ? cols[2] : GROUPS[0],
      horiz: (cols[3]||'').toLowerCase()==='true'||cols[3]==='1',
      len:   parseFloat(cols[4])||25,
      angle: parseFloat(cols[5])||0,
      tilt:  parseFloat(cols[6])||0,
    };
    addBulkRow(data);
  }
});

// ── reset ─────────────────────────────────────────────────────────────────────
function resetAll(){
  sockets.length = 0; pos.length = 0;
  sel=-1; selSet.clear();
  render();
}
function resetSel(){
  if(selSet.size===0) return;
  for(const i of selSet){
    pos[i].lx=pos[i].lx0; pos[i].ly=pos[i].ly0;
    sockets[i].cx=pos[i].cx0; sockets[i].cy=pos[i].cy0;
    placeCircle(i); placeLabel(i);
  }
  redrawConn(); updateScad();
}

// ── add socket ────────────────────────────────────────────────────────────────
function toggleAddMode(){
  addMode = !addMode;
  document.getElementById('btn-add').classList.toggle('active', addMode);
  svg.classList.toggle('add-mode', addMode);
  if(!addMode) cancelAdd();
  document.getElementById('hint').textContent = addMode
    ? 'Click in the bin to place a new socket  \u00b7  Esc = cancel'
    : 'Drag labels \u00b7 Shift = no snap \u00b7 R = reset \u00b7 Del = delete \u00b7 auto-saved';
}
function handleAddClick(e){
  const p=svgPt(e);
  const cx=fx(p.x), cy=fy(p.y);
  const sel_ap = document.getElementById('ap-group');
  sel_ap.innerHTML = '';
  D.groups.forEach(g=>{ const o=document.createElement('option'); o.value=g; o.textContent=g; sel_ap.appendChild(o); });
  pendingAdd = {cx, cy};
  const popup = document.getElementById('add-popup');
  popup.style.display = 'block';
  const wrap = document.getElementById('canvas-wrap');
  const wr = wrap.getBoundingClientRect();
  let px = e.clientX - wr.left + 10;
  let py = e.clientY - wr.top  + 10;
  if(px + 210 > wrap.clientWidth)  px = e.clientX - wr.left - 220;
  if(py + 180 > wrap.clientHeight) py = e.clientY - wr.top  - 180;
  popup.style.left = px + 'px';
  popup.style.top  = py + 'px';
  document.getElementById('ap-label').value = '';
  document.getElementById('ap-diam').value  = '12';
  document.getElementById('ap-label').focus();
}
function confirmAdd(){
  if(!pendingAdd) return;
  const lbl  = document.getElementById('ap-label').value.trim();
  const diam = parseFloat(document.getElementById('ap-diam').value);
  const grp  = document.getElementById('ap-group').value;
  if(!lbl || isNaN(diam) || diam<=0){ alert('Label and diameter required'); return; }
  const r = diam / 2;
  const tilt = parseFloat(document.getElementById('ap-tilt').value) || 0;
  const horiz = document.getElementById('ap-horiz').checked;
  const mag   = document.getElementById('ap-mag').checked;
  const len = horiz ? (parseFloat(document.getElementById('ap-len').value) || 25) : 0;
  const newSock = {group:grp, label:lbl, r, cx:pendingAdd.cx, cy:pendingAdd.cy,
                   lx:pendingAdd.cx, ly:0,
                   tilt, horiz, mag, len, angle:0, _added:true};
  newSock.ly = pendingAdd.cy - sockBounds(newSock).hh - 2;
  sockets.push(newSock);
  pos.push({lx:newSock.lx, ly:newSock.ly, lx0:newSock.lx, ly0:newSock.ly});
  cancelAdd();
  toggleAddMode();
  render();
  selectItem(sockets.length-1);
}
function cancelAdd(){
  pendingAdd = null;
  document.getElementById('add-popup').style.display = 'none';
}
document.getElementById('ap-label').addEventListener('keydown', e=>{
  if(e.key==='Enter') confirmAdd();
  if(e.key==='Escape') cancelAdd();
});

// ── delete socket ──────────────────────────────────────────────────────────────
function deleteSel(){
  if(selSet.size===0) return;
  const toDelete = [...selSet].sort((a,b)=>b-a);
  for(const i of toDelete){ sockets.splice(i,1); pos.splice(i,1); }
  sel=-1; selSet.clear();
  render();
}

// ── SCAD generation ───────────────────────────────────────────────────────────
function f3(n){ return n.toFixed(3); }
function generateScad(){
  const L=[], p=s=>L.push(s);
  // Embed full session state so Load .scad can do a complete round-trip
  const _state = {gx, gy, binInternalMm,
    magnetR, magnetDepth,
    sockets: sockets.map((s,i)=>({...s, lx:pos[i].lx, ly:pos[i].ly}))};
  p(`// SOCKET_LAYOUT_STATE: ${JSON.stringify(_state)}`);
  p('// Generated by socket layout editor');
  p(`// Bin: ${gx}\xd7${gy} gridfinity units  (${bin_w}\xd7${bin_h}mm)`);
  p('');
  p('include <src/core/standard.scad>');
  p('use <src/core/gridfinity-rebuilt-utility.scad>');
  p('use <src/core/gridfinity-rebuilt-holes.scad>');
  p('use <src/core/bin.scad>');
  p('use <src/core/cutouts.scad>');
  p('use <src/helpers/generic-helpers.scad>');
  p('use <src/helpers/grid.scad>');
  p('use <src/helpers/grid_element.scad>');
  p('');
  p('$fa = $preview ? 10 : 4;');
  p('$fs = $preview ? 1.5 : 0.25;');
  p('');
  p(`gridx = ${gx};`);
  p(`gridy = ${gy};`);
  p(`gridz = ${binInternalMm};  // internal ${binInternalMm}mm + 7mm base = ${binInternalMm+BASE_HEIGHT_MM}mm total`);
  p('');
  p('gridz_define = 1; height_internal = 0; enable_zsnap = false;');
  p('include_lip = true; half_grid = false;');
  p('only_corners = false; refined_holes = true; magnet_holes = false;');
  p('screw_holes = false; crush_ribs = true; chamfer_holes = true;');
  p('printable_hole_top = true; enable_thumbscrew = false;');
  p('');
  p('hole_options = bundle_hole_options(refined_holes, magnet_holes, screw_holes,');
  p('                                   crush_ribs, chamfer_holes, printable_hole_top);');
  p('');
  p('bin1 = new_bin(');
  p('    grid_size       = [gridx, gridy],');
  p('    height_mm       = height(gridz, gridz_define, enable_zsnap),');
  p('    fill_height     = height_internal, include_lip = include_lip,');
  p('    hole_options    = hole_options, only_corners = only_corners || half_grid,');
  p('    thumbscrew      = enable_thumbscrew,');
  p('    grid_dimensions = GRID_DIMENSIONS_MM / (half_grid ? 2 : 1));');
  p('');
  p(`socket_depth = ${socketDepth};`);
  p(`c_chamfer    = ${D.chamfer};`);
  if(sockets.some(s=>s.mag)){
    p(`mag_r        = ${magnetR};`);
    p(`mag_depth    = ${magnetDepth};`);
  }
  p('label_height = 0.6;');
  p(`label_size   = ${D.label_size};`);
  p('label_font   = "Liberation Sans:style=Bold";');
  p('label_z = BASE_HEIGHT + bin_get_infill_size_mm(bin1).z + TOLLERANCE;');
  p('');
  const hasHorizMag = sockets.some(s => s.horiz && s.mag);
  if(hasHorizMag) p('difference() {');
  p('bin_render(bin1) {');
  let cg=null;
  for(let i=0;i<sockets.length;i++){
    const s=sockets[i];
    if(s.group!==cg){ p(''); p(`    // === ${s.group} ===`); cg=s.group; }
    if(s.horiz){
      const len = s.len || 20, angle = s.angle || 0;
      const zrot = angle !== 0 ? `rotate([0, 0, ${angle}]) ` : '';
      p(`    translate([${f3(s.cx)}, ${f3(s.cy)}]) ${zrot}rotate([0, 90, 0]) cylinder(h=${f3(len)}, r=${s.r}, center=true);  // ${s.label}`);
      if(s.mag)
        p(`    translate([${f3(s.cx)}, ${f3(s.cy)}, -(${s.r} + mag_depth)]) cylinder(h=mag_depth, r=mag_r);  // magnet seat ${s.label}`);
    } else {
      const tilt = s.tilt || 0;
      const rot = tilt > 0 ? ` rotate([${tilt}, 0, 0])` : '';
      p(`    translate([${f3(s.cx)}, ${f3(s.cy)}])${rot} cut_chamfered_cylinder(${s.r}, socket_depth, c_chamfer);  // ${s.label}`);
      if(s.mag)
        p(`    translate([${f3(s.cx)}, ${f3(s.cy)}, -socket_depth]) cylinder(h=mag_depth, r=mag_r);  // magnet ${s.label}`);
    }
  }
  p('}');
  if(hasHorizMag){
    p('');
    p('    // Magnet bottom-access shafts — flip bin over, push magnet up from below');
    for(let i=0;i<sockets.length;i++){
      const s=sockets[i];
      if(s.horiz && s.mag)
        p(`    translate([${f3(s.cx)}, ${f3(s.cy)}]) cylinder(h = label_z - ${s.r} - mag_depth + 0.5, r = mag_r);  // access ${s.label}`);
    }
    p('}');
  }
  p('');
  p('translate([0, 0, label_z]) {');
  cg=null;
  for(let i=0;i<sockets.length;i++){
    const s=sockets[i];
    if(s.group!==cg){ p(''); p(`    // === ${s.group} ===`); cg=s.group; }
    p(`    translate([${f3(pos[i].lx)}, ${f3(pos[i].ly)}]) linear_extrude(label_height) text("${s.label}", size=label_size, font=label_font, halign="center", valign="center");`);
  }
  p('}');
  return L.join('\n');
}
function updateScad(){
  document.getElementById('scad-out').textContent = generateScad();
  const changed = pos.filter((p,i)=>Math.abs(p.lx-p.lx0)>0.05||Math.abs(p.ly-p.ly0)>0.05).length;
  const added   = sockets.filter(s=>s._added).length;
  const parts   = [];
  if(changed) parts.push(`${changed} moved`);
  if(added)   parts.push(`${added} added`);
  document.getElementById('changed-count').textContent = parts.join(', ');
}
function updateInfo(){
  const info = document.getElementById('pos-info');
  if(selSet.size > 1) info.textContent = `${selSet.size} selected`;
  else if(sel>=0) info.textContent = `${sockets[sel].label}  (${pos[sel].lx.toFixed(1)}, ${pos[sel].ly.toFixed(1)})`;
  else info.textContent = '';
}

// ── properties panel ──────────────────────────────────────────────────────────
function showProps(){
  const propsEl = document.getElementById('props');
  if(selSet.size===0){ propsEl.style.display='none'; return; }
  propsEl.style.display='flex';
  if(sel>=0){
    const s = sockets[sel];
    document.getElementById('prop-label').value = s.label;
    document.getElementById('prop-diam').value  = (s.r * 2).toFixed(2);
    document.getElementById('prop-group').value = s.group;
    document.getElementById('prop-tilt').value  = (s.tilt || 0).toFixed(0);
    const isH = s.horiz || false;
    document.getElementById('btn-horiz').classList.toggle('active', isH);
    document.getElementById('chk-mag').checked = s.mag || false;
    document.getElementById('tilt-ctrl').style.display = isH ? 'none' : 'contents';
    document.getElementById('horiz-ctrl').style.display = isH ? 'flex' : 'none';
    if(isH){
      document.getElementById('prop-len').value = (s.len || 20).toFixed(0);
      document.getElementById('prop-angle').value = (s.angle || 0).toFixed(0);
    }
  }
  const sc = document.getElementById('spacing-ctrl');
  if(selSet.size >= 2){ sc.style.display='flex'; updateSpacingDisplay(); }
  else                 { sc.style.display='none'; }
}

// ── spacing ────────────────────────────────────────────────────────────────────
function getSelAxis(){
  const idxs=[...selSet];
  const xs=idxs.map(i=>sockets[i].cx), ys=idxs.map(i=>sockets[i].cy);
  return (Math.max(...xs)-Math.min(...xs)) >= (Math.max(...ys)-Math.min(...ys)) ? 'x' : 'y';
}
function getCurrentSpacing(){
  // Returns mean edge-to-edge gap between adjacent circles
  if(selSet.size<2) return 0;
  const idxs=[...selSet], axis=getSelAxis(), cKey=axis==='x'?'cx':'cy';
  idxs.sort((a,b)=>sockets[a][cKey]-sockets[b][cKey]);
  let t=0;
  for(let k=1;k<idxs.length;k++)
    t += sockets[idxs[k]][cKey] - sockets[idxs[k-1]][cKey] - sockets[idxs[k-1]].r - sockets[idxs[k]].r;
  return t/(idxs.length-1);
}
function applySpacing(gap){
  // Redistribute circles so every adjacent pair has the same edge-to-edge gap,
  // keeping the centroid of circle centres fixed.
  if(selSet.size<2||gap<0) return;
  const idxs=[...selSet];
  const axis=getSelAxis(), cKey=axis==='x'?'cx':'cy', pKey=axis==='x'?'lx':'ly';
  idxs.sort((a,b)=>sockets[a][cKey]-sockets[b][cKey]);
  // Build positions relative to first circle (at 0)
  const rel=[0];
  for(let k=1;k<idxs.length;k++)
    rel.push(rel[k-1] + sockets[idxs[k-1]].r + gap + sockets[idxs[k]].r);
  // Preserve centroid of centres
  const oldCentroid = idxs.reduce((s,i)=>s+sockets[i][cKey],0)/idxs.length;
  const newCentroid  = rel.reduce((s,v)=>s+v,0)/rel.length;
  const offset = oldCentroid - newCentroid;
  for(let k=0;k<idxs.length;k++){
    const i=idxs[k], newC=rel[k]+offset, d=newC-sockets[i][cKey];
    sockets[i][cKey]=newC; pos[i][pKey]+=d;
    placeCircle(i); placeLabel(i);
  }
  redrawConn(); updateScad(); updateSpacingDisplay();
}
function adjustSpacing(delta){ applySpacing(Math.max(0, getCurrentSpacing()+delta)); }
function equalizeSpacing(){
  // Spread existing total gap evenly (keeps outer edges fixed)
  if(selSet.size<2) return;
  const idxs=[...selSet], axis=getSelAxis(), cKey=axis==='x'?'cx':'cy';
  idxs.sort((a,b)=>sockets[a][cKey]-sockets[b][cKey]);
  const spanLeft  = sockets[idxs[0]][cKey]               - sockets[idxs[0]].r;
  const spanRight = sockets[idxs[idxs.length-1]][cKey]   + sockets[idxs[idxs.length-1]].r;
  const totalR    = idxs.reduce((s,i)=>s+sockets[i].r*2, 0);
  applySpacing(Math.max(0, (spanRight-spanLeft-totalR)/(idxs.length-1)));
}
function updateSpacingDisplay(){
  document.getElementById('spacing-val').value = getCurrentSpacing().toFixed(2);
}
document.getElementById('spacing-val').addEventListener('change', e=>{
  const v=parseFloat(e.target.value); if(!isNaN(v)&&v>0) applySpacing(v);
});
document.getElementById('prop-label').addEventListener('input', e => {
  if(sel < 0) return;
  const v = e.target.value;
  sockets[sel].label = v;
  // Update label SVG element directly (avoids full re-render during typing)
  const lw = Math.max(v.length||1,1)*0.62*D.label_size;
  const lh = D.label_size;
  const g = lEls[sel];
  g.querySelector('rect').setAttribute('width', lw);
  const txt = g.querySelector('text');
  txt.setAttribute('x', lw/2); txt.textContent = v;
  placeLabel(sel); updateScad();
});
document.getElementById('prop-diam').addEventListener('change', e => {
  if(sel < 0) return;
  const d = parseFloat(e.target.value);
  if(isNaN(d) || d <= 0) return;
  sockets[sel].r = d / 2;
  placeCircle(sel); updateScad();
});
document.getElementById('prop-tilt').addEventListener('change', e => {
  if(sel < 0) return;
  const v = parseFloat(e.target.value);
  if(isNaN(v) || v < 0 || v > 80) return;
  sockets[sel].tilt = v;
  placeCircle(sel); updateScad();
});
document.getElementById('prop-len').addEventListener('change', e => {
  if(sel < 0) return;
  const v = parseFloat(e.target.value); if(isNaN(v) || v <= 0) return;
  sockets[sel].len = v; placeCircle(sel); updateScad();
});
function toggleHoriz(){
  if(sel < 0) return;
  sockets[sel].horiz = !(sockets[sel].horiz || false);
  if(sockets[sel].horiz){ sockets[sel].len = sockets[sel].len || 25; sockets[sel].angle = sockets[sel].angle || 0; }
  placeCircle(sel); showProps(); updateScad();
}
function setMag(val){
  if(sel < 0) return;
  sockets[sel].mag = val;
  buildCircleVisual(cEls[sel], sockets[sel]);
  updateScad();
}
function adjustHorizAngle(delta){
  if(sel < 0 || !sockets[sel].horiz) return;
  sockets[sel].angle = ((sockets[sel].angle || 0) + delta + 360) % 180;
  document.getElementById('prop-angle').value = sockets[sel].angle.toFixed(0);
  placeCircle(sel); updateScad();
}
document.getElementById('prop-angle').addEventListener('change', e => {
  if(sel < 0) return;
  const v = parseFloat(e.target.value);
  if(isNaN(v)) return;
  sockets[sel].angle = ((v % 180) + 180) % 180;
  document.getElementById('prop-angle').value = sockets[sel].angle.toFixed(0);
  placeCircle(sel); updateScad();
});
function copyScad(){
  navigator.clipboard.writeText(generateScad()).then(()=>{
    const b=event.target; b.textContent='\u2713 Copied!';
    setTimeout(()=>b.textContent='\u29e2 Copy SCAD',2000);
  });
}
function dlScad(){
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([generateScad()],{type:'text/plain'}));
  a.download='sockets.scad'; a.click();
}

// ── save directly to file (File System Access API) ────────────────────────────
let _fileHandle = null;
async function saveToFile(){
  const btn = document.getElementById('btn-save');
  try {
    if(!_fileHandle){
      _fileHandle = await window.showSaveFilePicker({
        suggestedName: 'sockets.scad',
        types: [{ description: 'OpenSCAD file', accept: {'text/plain': ['.scad']} }],
        startIn: 'documents'
      });
    }
    const writable = await _fileHandle.createWritable();
    await writable.write(generateScad());
    await writable.close();
    btn.textContent = '\u2713 Saved!';
    setTimeout(()=>btn.textContent='\uD83D\uDCBE Save .scad', 2000);
  } catch(e){
    if(e.name==='AbortError') return;          // user cancelled picker
    if(e.name==='SecurityError'){ dlScad(); return; }  // browser doesn't support — fallback
    _fileHandle = null;                        // stale handle — retry next click
    btn.textContent = '\u26A0 Retry save';
    setTimeout(()=>btn.textContent='\uD83D\uDCBE Save .scad', 2500);
  }
}
if(!window.showSaveFilePicker){
  // Browser doesn't support File System Access — hide Save button, keep Download
  document.getElementById('btn-save').style.display='none';
}

// ── bin dimension controls ────────────────────────────────────────────────────
function updateBinMm(){
  const total = binInternalMm + BASE_HEIGHT_MM;
  const usable = binInternalMm - LIP_SUPPORT_MM;
  const warn = usable < socketDepth ? ' ⚠' : '';
  document.getElementById('bin-mm').textContent = `= ${total.toFixed(1)}mm total  (${usable.toFixed(1)}mm usable${warn})`;
}
function setMinGridz(){
  binInternalMm = socketDepth + LIP_SUPPORT_MM;
  document.getElementById('bin-gridz').value = binInternalMm;
  updateBinMm(); updateScad();
}
document.getElementById('bin-depth').value = socketDepth;
document.getElementById('bin-gridz').value = binInternalMm;
document.getElementById('bin-gx').value = gx;
document.getElementById('bin-gy').value = gy;
// populate group dropdown
(()=>{ const sel=document.getElementById('prop-group');
  GROUPS.forEach(g=>{ const o=document.createElement('option'); o.value=o.textContent=g; sel.appendChild(o); }); })();
document.getElementById('prop-group').addEventListener('change', e=>{
  if(sel<0) return;
  sockets[sel].group = e.target.value;
  buildCircleVisual(cEls[sel], sockets[sel]); updateScad();
});
updateBinMm();
document.getElementById('bin-depth').addEventListener('change', e=>{
  const v = parseFloat(e.target.value); if(isNaN(v)||v<=0) return;
  socketDepth = v; updateScad();
});
document.getElementById('bin-gridz').addEventListener('change', e=>{
  const v = parseFloat(e.target.value); if(isNaN(v)||v<1) return;
  binInternalMm = v; updateBinMm(); updateScad();
});
document.getElementById('bin-gx').addEventListener('change', e=>{
  const v = parseInt(e.target.value); if(isNaN(v)||v<1||v>8) return;
  gx = v; rebuildViewport(); render(); updateScad();
});
document.getElementById('bin-gy').addEventListener('change', e=>{
  const v = parseInt(e.target.value); if(isNaN(v)||v<1||v>8) return;
  gy = v; rebuildViewport(); render(); updateScad();
});
document.getElementById('mag-diam').addEventListener('change', e=>{
  const v = parseFloat(e.target.value); if(isNaN(v)||v<=0) return;
  magnetR = v / 2; updateScad();
});
document.getElementById('mag-depth-inp').addEventListener('change', e=>{
  const v = parseFloat(e.target.value); if(isNaN(v)||v<=0) return;
  magnetDepth = v; updateScad();
});

// ── localStorage ──────────────────────────────────────────────────────────────
const LS_KEY = 'socket-layout-v2';
function saveToStorage(){
  localStorage.setItem(LS_KEY, JSON.stringify({
    v: 2,
    gx, gy, binInternalMm,
    magnetR, magnetDepth,
    sockets: sockets.map((s,i) => ({...s, lx:pos[i].lx, ly:pos[i].ly}))
  }));
}
function loadFromStorage(){
  const raw = localStorage.getItem(LS_KEY);
  if(!raw) return false;
  try {
    const saved = JSON.parse(raw);
    if(!saved.sockets) return false;
    // restore bin dimensions
    if(saved.gx && saved.gy){
      gx = saved.gx; gy = saved.gy;
      document.getElementById('bin-gx').value = gx;
      document.getElementById('bin-gy').value = gy;
      rebuildViewport();
    }
    if(saved.binInternalMm != null){
      binInternalMm = saved.binInternalMm;
      document.getElementById('bin-gridz').value = binInternalMm;
      updateBinMm();
    }
    if(saved.magnetR != null){ magnetR = saved.magnetR; document.getElementById('mag-diam').value = (magnetR*2).toFixed(2); }
    if(saved.magnetDepth != null){ magnetDepth = saved.magnetDepth; document.getElementById('mag-depth-inp').value = magnetDepth.toFixed(2); }
    // replace entire socket list (including empty canvas after Reset All)
    sockets.length = 0; pos.length = 0;
    for(const s of saved.sockets){
      const {lx, ly, ...sock} = s;
      sockets.push({...sock});
      pos.push({lx, ly, lx0:lx, ly0:ly, cx0:sock.cx, cy0:sock.cy});
    }
    return true;
  } catch(e){ return false; }
}
function clearSaved(){
  localStorage.removeItem(LS_KEY);
  // Reload defaults from D.sockets
  sockets.length = 0; pos.length = 0;
  D.sockets.forEach(s => {
    sockets.push({...s, _added:false});
    pos.push({lx:s.lx, ly:s.ly, lx0:s.lx, ly0:s.ly, cx0:s.cx, cy0:s.cy});
  });
  sel = -1; selSet.clear();
  render();
  document.getElementById('hint').textContent = 'Cleared \u2014 showing optimizer defaults';
  setTimeout(()=>document.getElementById('hint').textContent=
    'Drag labels \u00b7 Shift = no snap \u00b7 R = reset \u00b7 Del = delete \u00b7 auto-saved', 2500);
}
// Throttle storage saves — only persist after 400ms of no updates (not on every mousemove)
let _saveTimer = null;
const _origUpdateScad = updateScad;
updateScad = function(){
  _origUpdateScad();
  clearTimeout(_saveTimer);
  _saveTimer = setTimeout(saveToStorage, 400);
};

// ── load from .scad file ──────────────────────────────────────────────────────
function loadScad(input){
  const file=input.files[0]; if(!file) return;
  const reader=new FileReader();
  reader.onload=e=>{
    const text=e.target.result;
    const hint = s => {
      document.getElementById('hint').textContent = s;
      setTimeout(()=>document.getElementById('hint').textContent=
        'Drag labels \u00b7 Shift = no snap \u00b7 R = reset \u00b7 Del = delete \u00b7 auto-saved', 3000);
    };
    // ── Try embedded JSON state (full round-trip) ──────────────────────────
    const stateMatch = text.match(/^\/\/ SOCKET_LAYOUT_STATE: (.+)$/m);
    if(stateMatch){
      try{
        const st = JSON.parse(stateMatch[1]);
        if(st.gx && st.gy){
          gx = st.gx; gy = st.gy;
          document.getElementById('bin-gx').value = gx;
          document.getElementById('bin-gy').value = gy;
          rebuildViewport();
        }
        if(st.binInternalMm != null){
          binInternalMm = st.binInternalMm;
          document.getElementById('bin-gridz').value = binInternalMm;
          updateBinMm();
        }
        if(st.magnetR != null){ magnetR = st.magnetR; document.getElementById('mag-diam').value = (magnetR*2).toFixed(2); }
        if(st.magnetDepth != null){ magnetDepth = st.magnetDepth; document.getElementById('mag-depth-inp').value = magnetDepth.toFixed(2); }
        if(st.sockets){
          sockets.length = 0; pos.length = 0;
          for(const s of st.sockets){
            const {lx, ly, ...sock} = s;
            sockets.push({...sock, _added: sock._added || false});
            pos.push({lx, ly, lx0:lx, ly0:ly, cx0:sock.cx, cy0:sock.cy});
          }
        }
        sel = -1; selSet.clear();
        render(); updateScad();
        hint(`\u2713 Loaded ${sockets.length} sockets from ${file.name}`);
        input.value = '';
        return;
      } catch(err){ /* fall through to legacy */ }
    }
    // ── Legacy: parse label positions only ────────────────────────────────
    const re=/translate\(\[\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\]\)\s*linear_extrude[^)]+\)\s*text\("([^"]+)"/g;
    let m, found=0;
    while((m=re.exec(text))!==null){
      const lx=parseFloat(m[1]), ly=parseFloat(m[2]), lbl=m[3];
      const candidates=sockets.reduce((a,s,i)=>s.label===lbl?[...a,i]:a,[]);
      if(candidates.length===1){
        pos[candidates[0]].lx=lx; pos[candidates[0]].ly=ly; found++;
      } else if(candidates.length>1){
        let best=-1, bestD=Infinity;
        for(const i of candidates){ const d=Math.hypot(pos[i].lx-lx,pos[i].ly-ly); if(d<bestD){bestD=d;best=i;} }
        if(best>=0){ pos[best].lx=lx; pos[best].ly=ly; found++; }
      }
    }
    for(let i=0;i<pos.length;i++) placeLabel(i);
    redrawConn(); updateScad();
    hint(`Loaded ${found} label positions from ${file.name}`);
    input.value='';
  };
  reader.readAsText(file);
}

// ── init ──────────────────────────────────────────────────────────────────────
if(loadFromStorage()){
  render();
  document.getElementById('hint').textContent='Restored saved session \u2014 drag to edit';
  setTimeout(()=>document.getElementById('hint').textContent=
    'Drag labels \u00b7 Shift = no snap \u00b7 R = reset \u00b7 Del = delete \u00b7 auto-saved',3000);
} else {
  render();
}
</script></body></html>"""

# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if "--help" in args:
        print(__doc__); sys.exit(0)

    preview  = "--preview" in args
    html     = "--html"    in args
    args     = [a for a in args if a not in ("--preview", "--html")]
    csv_path = Path(args[0]) if args else Path(__file__).parent / "sockets.csv"

    if not csv_path.exists():
        print(f"Error: '{csv_path}' not found.", file=sys.stderr)
        sys.exit(1)

    groups = load_sockets(csv_path)
    print(f"// Loaded {sum(len(v) for v in groups.values())} sockets "
          f"in {len(groups)} groups: {', '.join(groups.keys())}")
    print("//")

    prefer_adjacent = [("Met Deep", "Met Shallow"), ("Imp Deep", "Imp Shallow")]
    ordered_groups, gx, gy, W, label_size = find_optimal_bin(groups, prefer_adjacent)
    placed, H, zones, actual_label_size = layout_coordinates(ordered_groups, W, label_size, gy)
    print(f"// 2D label placement: {actual_label_size:.2f}mm  (1D estimate: {label_size:.2f}mm)")
    print("//")

    if preview:
        write_svg(placed, gx, gy, W, H, actual_label_size, zones, csv_path.with_suffix(".svg"))
    elif html:
        write_html(placed, gx, gy, W, H, actual_label_size, csv_path.with_suffix(".html"))
    else:
        write_openscad(placed, gx, gy, W, H, actual_label_size, csv_path.with_suffix(".scad"))

if __name__ == "__main__":
    main()
