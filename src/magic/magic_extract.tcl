gds read $::env(GDS)
set cell $::env(CELL)
if {[info exists ::env(PEX)]} {
    set do_pex 1
} else {
    set do_pex 0
}

load $cell
select top cell

# flatten, cause PEX works incorrectly for hierarchical gds 
# and it's simplier to run tests on flat netlists
set flat_cell ${cell}_flat
flatten $flat_cell
load $flat_cell
cellname delete $cell
cellname rename $flat_cell $cell
load $cell
select top cell

# set port order consistent with SPICE test
source efuse_array_ports.tcl

# perform PEX or LVS style extraction
if {$do_pex == 1} {
    extract do all
    extract warn all
    extract do length
    extract all

    ext2sim labels on
    ext2sim
    extresist simplify off
    extresist all

    ext2spice cthresh 0.01fF
    ext2spice rthresh 1
    ext2spice subcircuit on
    ext2spice scale off
    ext2spice hierarchy on
    ext2spice resistor tee on
    ext2spice subcircuit descend on

    ext2spice extresist on
} else {
    extract all
    ext2spice lvs
    ext2spice subcircuit on
    ext2spice subcircuit top on
}

ext2spice -F -f ngspice -o $::env(SPICE_NAME)

# file rename -force "${cell}.spice" $::env(SPICE_NAME)
exit
