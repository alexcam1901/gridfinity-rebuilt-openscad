# gridfinity-rebuilt-openscad — Socket Layout Tool

## Project Overview
This is a fork of [kennetek/gridfinity-rebuilt-openscad](https://github.com/kennetek/gridfinity-rebuilt-openscad).
On top of the upstream gridfinity library, we've added a **socket holder layout tool**:
- `socket_layout.py` — Python script that generates the HTML editor and SCAD output
- `sockets.html` — the interactive layout editor (regenerated from socket_layout.py)
- `sockets.scad` — example/working output file
- `sockets.csv` — socket data input

## Regenerating the HTML
```bash
python3 socket_layout.py --html
```
This reads `sockets.csv`, runs the optimizer, and writes `sockets.html`.

## How It Works
- `socket_layout.py` embeds a full single-file HTML app inside a Python template string (`_HTML_TEMPLATE`)
- The HTML editor is self-contained: SVG canvas, drag/drop label placement, SCAD generation, localStorage persistence
- Socket data (`D`) is injected as JSON into the HTML at generation time via `/*DATA*/` placeholder
- The generated `sockets.scad` uses **relative paths** (`src/core/...`) so the project can live anywhere

## Key Files
- `socket_layout.py` — all edits go here; `sockets.html` is always regenerated, never edit directly
- `src/core/bin.scad` — `bin_render`, `new_bin`, `bin_get_infill_size_mm`
- `src/core/cutouts.scad` — `cut_chamfered_cylinder`
- `src/core/standard.scad` — constants: `BASE_HEIGHT=7`, `TOLLERANCE`, `STACKING_LIP_SUPPORT_HEIGHT≈1.2`

## SCAD Coordinate System (inside `bin_render`)
`bin_render` translates children by `[0, 0, BASE_HEIGHT + fill_height + TOLLERANCE]` before subtracting.
So in children space:
- `z=0` = top of infill (where sockets are cut from)
- `z=-socket_depth` = bottom of socket hole
- `fill_height_real = binInternalMm - STACKING_LIP_SUPPORT_HEIGHT`
- `label_z = BASE_HEIGHT + bin_get_infill_size_mm(bin1).z + TOLLERANCE` (world space, top of infill)

`bin_render_base` is rendered **after** the inner difference, so cuts inside `bin_render{}` do NOT cut through the base. To cut through the base, use an outer `difference()` wrapping `bin_render`.

## Socket Data Model
Each socket object:
```javascript
{
  group, label, r,           // group name, label text, radius (mm)
  cx, cy,                    // center position in OpenSCAD coords (mm, origin = bin center)
  lx, ly,                    // label center position
  tilt,                      // tilt angle toward back wall (vertical sockets only)
  horiz,                     // boolean: horizontal cylinder (lay on side)
  len, angle,                // horiz only: length (mm), rotation angle (degrees)
  mag,                       // boolean: add magnet cutout
  _added                     // boolean: user-added (not from optimizer)
}
```

## Magnet Cutouts
- **Global settings**: `magnetR` (radius mm), `magnetDepth` (depth mm) — set in toolbar
- **Per-socket**: `s.mag` boolean toggle in props panel
- **Vertical sockets**: `translate([cx, cy, -socket_depth]) cylinder(h=mag_depth, r=mag_r)` — recess inside socket hole at bottom
- **Horizontal sockets**: two-part cut:
  1. Inside `bin_render`: `translate([cx, cy, -(r + mag_depth)]) cylinder(...)` — magnet seat at groove floor
  2. Outer `difference()`: `translate([cx, cy]) cylinder(h = label_z - r - mag_depth + 0.5, r = mag_r)` — bottom-access shaft through base so magnet can be inserted from below after printing

## Coordinate Conversion (SVG ↔ OpenSCAD)
```javascript
sx(x) = x + bin_w/2 + MAR      // OpenSCAD → SVG x
sy(y) = -y + bin_h/2 + MAR     // OpenSCAD → SVG y (Y-flipped)
fx(X) = X - bin_w/2 - MAR      // SVG → OpenSCAD x
fy(Y) = -(Y - bin_h/2 - MAR)   // SVG → OpenSCAD y
```

## State Persistence
- **localStorage**: key `socket-layout-v2`, saves full socket list + bin dims + magnet settings
- **SCAD round-trip**: `// SOCKET_LAYOUT_STATE: {...}` JSON comment in generated SCAD header
- Load .scad tries JSON state first, falls back to regex label-position parsing

## Known Patterns / Gotchas
- `VW` and `VH` must be module-scope `let` (not `const` inside `rebuildViewport`) — used in `drawSnapLines`
- `saveToStorage` is debounced 400ms via `_saveTimer` to avoid blocking UI on every mousemove
- `sockBounds(s)` returns `{hw, hh}` — use this everywhere for horizontal socket footprint, not `s.r`
- Snap lines use `sx(snapX)` / `sy(snapY)` for correct SVG coordinates
- Label position convention: `pos[i].lx/ly` = label CENTER in OpenSCAD coords
