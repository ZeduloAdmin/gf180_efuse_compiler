gds read $::env(GDS)
set cell $::env(CELL)

load $cell
select top cell

puts "Zeroizing Origin"
set bbox [box values]
set offset_x [lindex $bbox 0]
set offset_y [lindex $bbox 1]
move origin [expr {$offset_x/2}] [expr {$offset_y/2}]
property FIXED_BBOX [box values]

# following is needed to mark efuse as obstruction on metal1&2 layers
expand
snap internal 
select visible efuse
box values {*}[select bbox]
paint metal1
paint metal2

set tolerance 1
lef write ${cell}.lef -toplayer -nomaster
exit
