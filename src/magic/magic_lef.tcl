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

set tolerance 1
lef write ${cell}.lef -toplayer -nomaster
exit
