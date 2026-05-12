// ===== TEST SLICE =====
// Thin top slice for verifying hole sizes before printing the full bin.
// Slice thickness controlled by `slice_mm` below.

include <src/core/standard.scad>
use <src/core/gridfinity-rebuilt-utility.scad>
use <src/core/gridfinity-rebuilt-holes.scad>
use <src/core/bin.scad>
use <src/core/cutouts.scad>
use <src/helpers/generic-helpers.scad>
use <src/helpers/grid.scad>
use <src/helpers/grid_element.scad>

$fa = 4;
$fs = 0.25;

gridx = 3;
gridy = 2;
gridz = 6;
half_grid = false;

gridz_define = 0;
height_internal = 0;
enable_zsnap = false;
include_lip = false;

only_corners = false;
refined_holes = false;
magnet_holes = false;
screw_holes = false;
crush_ribs = true;
chamfer_holes = true;
printable_hole_top = true;
enable_thumbscrew = false;

c_chamfer    = 0.5;
label_height = 0.6;
label_size   = 2.5;
label_font   = "Liberation Sans:style=Bold";

hole_options = bundle_hole_options(refined_holes, magnet_holes, screw_holes, crush_ribs, chamfer_holes, printable_hole_top);

slice_mm = 3;

bin1 = new_bin(
    grid_size = [gridx, gridy],
    height_mm = height(gridz, gridz_define, enable_zsnap),
    fill_height = height_internal,
    include_lip = include_lip,
    hole_options = hole_options,
    only_corners = only_corners || half_grid,
    thumbscrew = enable_thumbscrew,
    grid_dimensions = GRID_DIMENSIONS_MM / (half_grid ? 2 : 1)
);

socket_depth = 12;
label_z = BASE_HEIGHT + bin_get_infill_size_mm(bin1).z + TOLLERANCE;

difference() {
    union() {
        bin_render(bin1) {
            // row_bottom: r1=25.85  r2=4.60  r3=-13.20  r4=-35.70
            translate([-53.05,  32.05]) cut_chamfered_cylinder(6.2,   socket_depth, c_chamfer);
            translate([-38.65,  32.05]) cut_chamfered_cylinder(6.2,   socket_depth, c_chamfer);
            translate([-24.25,  32.05]) cut_chamfered_cylinder(6.2,   socket_depth, c_chamfer);
            translate([ -9.85,  32.05]) cut_chamfered_cylinder(6.2,   socket_depth, c_chamfer);
            translate([  4.55,  32.05]) cut_chamfered_cylinder(6.2,   socket_depth, c_chamfer);
            translate([ 16.75,  29.85]) cut_chamfered_cylinder(4.0,   socket_depth, c_chamfer);
            translate([ 28.95,  32.05]) cut_chamfered_cylinder(6.2,   socket_depth, c_chamfer);
            translate([ 43.35,  32.05]) cut_chamfered_cylinder(6.2,   socket_depth, c_chamfer);
            translate([-52.35,  10.75]) cut_chamfered_cylinder(6.15,  socket_depth, c_chamfer);
            translate([-36.55,  11.50]) cut_chamfered_cylinder(6.9,   socket_depth, c_chamfer);
            translate([-20.20,  12.05]) cut_chamfered_cylinder(7.45,  socket_depth, c_chamfer);
            translate([ -2.45,  12.90]) cut_chamfered_cylinder(8.3,   socket_depth, c_chamfer);
            translate([ 17.30,  13.73]) cut_chamfered_cylinder(9.125, socket_depth, c_chamfer);
            translate([ 37.38,  13.55]) cut_chamfered_cylinder(8.95,  socket_depth, c_chamfer);
            translate([ 53.79,  10.06]) cut_chamfered_cylinder(5.46,  socket_depth, c_chamfer);
            translate([ 53.75,  23.05]) cut_chamfered_cylinder(5.5,   socket_depth, c_chamfer);
            translate([-53.05,  -7.00]) cut_chamfered_cylinder(6.2,   socket_depth, c_chamfer);
            translate([-38.65,  -7.00]) cut_chamfered_cylinder(6.2,   socket_depth, c_chamfer);
            translate([-24.25,  -7.00]) cut_chamfered_cylinder(6.2,   socket_depth, c_chamfer);
            translate([ -9.60,  -6.95]) cut_chamfered_cylinder(6.25,  socket_depth, c_chamfer);
            translate([  4.85,  -6.45]) cut_chamfered_cylinder(6.75,  socket_depth, c_chamfer);
            translate([ 20.10,  -6.35]) cut_chamfered_cylinder(6.85,  socket_depth, c_chamfer);
            translate([ 36.35,  -5.80]) cut_chamfered_cylinder(7.4,   socket_depth, c_chamfer);
            translate([ 52.50,  -6.45]) cut_chamfered_cylinder(6.75,  socket_depth, c_chamfer);
            translate([-51.80, -28.25]) cut_chamfered_cylinder(7.45,  socket_depth, c_chamfer);
            translate([-34.00, -27.35]) cut_chamfered_cylinder(8.35,  socket_depth, c_chamfer);
            translate([-14.50, -26.55]) cut_chamfered_cylinder(9.15,  socket_depth, c_chamfer);
            translate([  6.40, -26.60]) cut_chamfered_cylinder(9.1,   socket_depth, c_chamfer);
            translate([ 28.90, -26.60]) cut_chamfered_cylinder(9.1,   socket_depth, c_chamfer);
            translate([ 49.65, -26.70]) cut_chamfered_cylinder(9.0,   socket_depth, c_chamfer);
        }

        translate([0, 0, label_z]) {
            translate([-53.05,  24.85]) linear_extrude(label_height) text("5/32",   size=label_size, font=label_font, halign="center", valign="top");
            translate([-38.65,  24.85]) linear_extrude(label_height) text("3/16",   size=label_size, font=label_font, halign="center", valign="top");
            translate([-24.25,  24.85]) linear_extrude(label_height) text("7/32",   size=label_size, font=label_font, halign="center", valign="top");
            translate([ -9.85,  24.85]) linear_extrude(label_height) text("1/4",    size=label_size, font=label_font, halign="center", valign="top");
            translate([  4.55,  24.85]) linear_extrude(label_height) text("9/32",   size=label_size, font=label_font, halign="center", valign="top");
            translate([ 16.75,  38.00]) linear_extrude(label_height) text("hex",    size=label_size, font=label_font, halign="center", valign="top");
            translate([-52.35,   3.60]) linear_extrude(label_height) text("5/16",   size=label_size, font=label_font, halign="center", valign="top");
            translate([-36.55,   3.60]) linear_extrude(label_height) text("11/32",  size=label_size, font=label_font, halign="center", valign="top");
            translate([-20.20,   3.60]) linear_extrude(label_height) text("3/8",    size=label_size, font=label_font, halign="center", valign="top");
            translate([ -2.45,   3.60]) linear_extrude(label_height) text("7/16",   size=label_size, font=label_font, halign="center", valign="top");
            translate([ 17.30,   3.60]) linear_extrude(label_height) text("1/2",    size=label_size, font=label_font, halign="center", valign="top");
            translate([ 37.38,  26.50]) linear_extrude(label_height) text("3/8\"",  size=label_size, font=label_font, halign="center", valign="top");
            translate([-53.05, -14.20]) linear_extrude(label_height) text("4",      size=label_size, font=label_font, halign="center", valign="top");
            translate([-38.65, -14.20]) linear_extrude(label_height) text("5",      size=label_size, font=label_font, halign="center", valign="top");
            translate([-24.25, -14.20]) linear_extrude(label_height) text("6",      size=label_size, font=label_font, halign="center", valign="top");
            translate([ -9.60, -14.20]) linear_extrude(label_height) text("7",      size=label_size, font=label_font, halign="center", valign="top");
            translate([  4.85, -14.20]) linear_extrude(label_height) text("8",      size=label_size, font=label_font, halign="center", valign="top");
            translate([ 20.10, -14.20]) linear_extrude(label_height) text("9",      size=label_size, font=label_font, halign="center", valign="top");
            translate([ 36.35, -14.20]) linear_extrude(label_height) text("u-jt",   size=label_size, font=label_font, halign="center", valign="top");
            translate([-51.80, -36.70]) linear_extrude(label_height) text("10",     size=label_size, font=label_font, halign="center", valign="top");
            translate([-34.00, -36.70]) linear_extrude(label_height) text("11",     size=label_size, font=label_font, halign="center", valign="top");
            translate([-14.50, -36.70]) linear_extrude(label_height) text("12",     size=label_size, font=label_font, halign="center", valign="top");
            translate([  6.40, -36.70]) linear_extrude(label_height) text("13",     size=label_size, font=label_font, halign="center", valign="top");
            translate([ 28.90, -36.70]) linear_extrude(label_height) text("14",     size=label_size, font=label_font, halign="center", valign="top");
            translate([ 49.65, -36.70]) linear_extrude(label_height) text("3/8\"",  size=label_size, font=label_font, halign="center", valign="top");
        }
    }

    // Remove everything below the top slice
    translate([-200, -200, -1])
        cube([400, 400, label_z - slice_mm + 1]);
}
