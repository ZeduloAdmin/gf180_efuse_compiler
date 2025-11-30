#!/usr/bin/env python3
#
# Small script to generate eFuse array SPICE netlists for LVS & simulation
#

import os
import sys
import json
from pathlib import Path

def write_magic_ports(filename : str, ports : str):
    port_list = ports.split(" ")
    with open(filename, "w") as f:
        for i,p in enumerate(port_list):
            if p.strip():
                print(f"""port {{{p}}} index {1000+i}""", file=f)
            
def subcircuit(name : str, ports : str, body : str, params : str = "") -> str:
    if params:
        params = "PARAMS: " + params
    return f"""
.subckt {name} {ports} {params}
{body}
.ends
    """

def efuse_bitline(n_fuses : int, device_naming : list) -> str:
    bitline_ports = "VSS VDD SENSE PRESET_N "
    for i in range(n_fuses):
        bitline_ports += f"BIT_SEL[{i}] "
    bitline_ports += "COL_PROG_N OUT"
    write_magic_ports("efuse_bitline_ports.tcl", bitline_ports)
    body = ""
    for i in range(n_fuses):
        body += f"X{i} VSS VDD BIT_SEL[{i}] bitline efuse_bitcell NUM={{LNUM*1000+{i}}}\n"
        
    # add programming PMOS
    # ! actually currently it's 4 fingers W=38.25 PMOS, not 2x W=76.5, but there is no such model and LVS is bad with fingers in SPICE !
    body += f"""{device_naming[0]}0 bitline COL_PROG_N VDD VDD p{device_naming[1]} L=0.50u W=76.5u nf=2"""
    body += "\n"
    body += f"""{device_naming[0]}1 bitline COL_PROG_N VDD VDD p{device_naming[1]} L=0.50u W=76.5u nf=2"""
    body += "\n"
    # add sensamp
    body += "Xsense VSS VSS VDD PRESET_N OUT SENSE bitline efuse_senseamp"
    
    return subcircuit("efuse_bitline", bitline_ports, body, "LNUM=0")

def efuse_array(cellname : str, word_width : int, n_fuses : int, add_cells : str = "") -> str:
    common_ports = "VSS VDD SENSE PRESET_N " + "".join([f'BIT_SEL[{j}] ' for j in range(n_fuses)])
    array_ports = common_ports
    sel_ports = ""

    body = add_cells

    for i in range(word_width):
        bitline_ports = f"COL_PROG_N[{i}] OUT[{i}] "
        body += f"X{i} {common_ports} {sel_ports} {bitline_ports} efuse_bitline LNUM={i}\n"
        array_ports += bitline_ports

    write_magic_ports("efuse_array_ports.tcl", array_ports)
    
    return subcircuit(cellname, array_ports, body), array_ports

def generate_netlist(cellname : str, filename : str, nwords : int, word_width : int, klayout_lvs : bool = False, add_cells_dict : dict = {}):

    device_naming = ["X", "fet_06v0", "X0 ANODE CATHODE efuse NUM={NUM}"]
        
    if klayout_lvs:
        device_naming[0] = "M"
        device_naming[1] = "fet_05v0"
        device_naming[2] = "Rfuse ANODE CATHODE efuse R=200"

    # generate additional filler, cap & cap cells
    add_cells = ""
    acnt = 0
    for c in add_cells_dict:
        if all(x not in c for x in ["filltie", "endcap"]):
            for i in range(add_cells_dict[c]):
                add_cells += f"Xfill{acnt} VDD VDD VSS VSS {c}\n"
                acnt += 1
                
    netlist = f"""* eFuse array netlist with word_width={word_width}, nwords={nwords}

.SUBCKT gf180mcu_fd_sc_mcu7t5v0__inv_1 I ZN VDD VNW VPW VSS
{device_naming[0]}0 ZN I VSS VPW n{device_naming[1]} W=8.2e-07 L=6e-07  
{device_naming[0]}1 ZN I VDD VNW p{device_naming[1]} W=1.22e-06 L=5e-07
.ENDS

.SUBCKT gf180mcu_fd_sc_mcu7t5v0__inv_2 I ZN VDD VNW VPW VSS
{device_naming[0]}00 ZN I VSS VPW n{device_naming[1]} W=8.2e-07 L=6e-07
{device_naming[0]}01 VSS I ZN VPW n{device_naming[1]} W=8.2e-07 L=6e-07
{device_naming[0]}10 ZN I VDD VNW p{device_naming[1]} W=1.22e-06 L=5e-07
{device_naming[0]}11 VDD I ZN VNW p{device_naming[1]} W=1.22e-06 L=5e-07
.ENDS

.SUBCKT gf180mcu_fd_sc_mcu7t5v0__fillcap_4 VDD VNW VPW VSS
{device_naming[0]}17 net_1 net_0 VSS VPW n{device_naming[1]} W=8.2e-07 L=1e-06
{device_naming[0]}19 VDD net_1 net_0 VNW p{device_naming[1]} W=1.22e-06 L=1e-06
.ENDS

.subckt efuse_bitcell VSS VDD SELECT ANODE PARAMS: NUM=-1
{device_naming[2]}
{device_naming[0]}1 CATHODE SELECT VSS VSS n{device_naming[1]} L=0.60u W=30.5u
.ends

.subckt efuse_senseamp VSS VPW VDD PRESET_N OUT SENSE FUSE
{device_naming[0]}2 net1 PRESET_N VDD VDD p{device_naming[1]} L=0.5u W=3.66u nf=3
X1 net2 OUT VDD VDD VPW VSS  gf180mcu_fd_sc_mcu7t5v0__inv_1
X2 net1 net2 VDD VDD VPW VSS gf180mcu_fd_sc_mcu7t5v0__inv_1
X3 net2 net1 VDD VDD VPW VSS gf180mcu_fd_sc_mcu7t5v0__inv_1
{device_naming[0]}1 net1 SENSE FUSE VPW n{device_naming[1]} L=0.60u W=0.82u
.ends

{efuse_bitline(nwords, device_naming)}
{efuse_array(cellname, word_width, nwords, add_cells)[0]}
.end
    """

    with open(filename, "w") as f:
        f.write(netlist)

def pwl_from_file(name : str, buf : int):
    return f"""V{name} {name}_prebuf 0 PWL FILE "{name}.pwl"
X{name}_buf {name}_prebuf {name} VDD VDD VSS VSS gf180mcu_fd_sc_mcu7t5v0__buf_{buf}
"""
    
def constant_driver(name : str, value : float):
    return f"""V{name} {name} 0 {value}\n"""

def gen_pwl_bus(name : str, size : int, buf : int):
    return "".join([pwl_from_file(f'{name}[{i}]', buf) for i in range(0, size)])

def generate_xyce_test(cellname : str, filename : str, spice_name : str, xyce_models_path : str, nwords : int, word_width : int, time : float = 100, vdd : float = 5.0):
    array_ports = efuse_array(cellname, word_width, nwords)[1]
    netlist = f"""* Xyce testbench for {cellname}
.option TEMP=25.0
.include "blown.map"

{constant_driver("VSS", 0)}
{constant_driver("VDD", vdd)}

.lib "{xyce_models_path}/design.xyce" typical
.lib "{xyce_models_path}/sm141064.xyce" typical

.SUBCKT efuse ANODE CATHODE PARAMS: PBLOW=0 NUM=-1
.PARAM BLOWN='IF(NUM<0 , PBLOW, BLOWN_MAP(NUM))'
Rfuse ANODE CATHODE R='200*(1-BLOWN) + 10000*BLOWN'
.ENDS efuse

.include {spice_name}

Xefuse_array {array_ports} {cellname}

* buffers to model drive strength
.SUBCKT gf180mcu_fd_sc_mcu7t5v0__buf_1 I Z VDD VNW VPW VSS
X_i_2 VSS I Z_neg VPW nfet_06v0 W=3.6e-07 L=6e-07
X_i_0 Z Z_neg VSS VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_3 VDD I Z_neg VNW pfet_06v0 W=5.65e-07 L=5e-07
X_i_1 Z Z_neg VDD VNW pfet_06v0 W=1.22e-06 L=5e-07
.ENDS

.SUBCKT gf180mcu_fd_sc_mcu7t5v0__buf_2 I Z VDD VNW VPW VSS
X_i_2 VSS I Z_neg VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_0_0 Z Z_neg VSS VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_0_1 VSS Z_neg Z VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_3 VDD I Z_neg VNW pfet_06v0 W=1.22e-06 L=5e-07
X_i_1_0 Z Z_neg VDD VNW pfet_06v0 W=1.22e-06 L=5e-07
X_i_1_1 VDD Z_neg Z VNW pfet_06v0 W=1.22e-06 L=5e-07
.ENDS

.SUBCKT gf180mcu_fd_sc_mcu7t5v0__buf_8 I Z VDD VNW VPW VSS
X_i_2_0 Z_neg I VSS VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_2_1 VSS I Z_neg VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_2_2 Z_neg I VSS VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_2_3 VSS I Z_neg VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_0_0 Z Z_neg VSS VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_0_1 VSS Z_neg Z VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_0_2 Z Z_neg VSS VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_0_3 VSS Z_neg Z VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_0_4 Z Z_neg VSS VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_0_5 VSS Z_neg Z VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_0_6 Z Z_neg VSS VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_0_7 VSS Z_neg Z VPW nfet_06v0 W=8.2e-07 L=6e-07
X_i_3_0 Z_neg I VDD VNW pfet_06v0 W=1.22e-06 L=5e-07
X_i_3_1 VDD I Z_neg VNW pfet_06v0 W=1.22e-06 L=5e-07
X_i_3_2 Z_neg I VDD VNW pfet_06v0 W=1.22e-06 L=5e-07
X_i_3_3 VDD I Z_neg VNW pfet_06v0 W=1.22e-06 L=5e-07
X_i_1_0 Z Z_neg VDD VNW pfet_06v0 W=1.22e-06 L=5e-07
X_i_1_1 VDD Z_neg Z VNW pfet_06v0 W=1.22e-06 L=5e-07
X_i_1_2 Z Z_neg VDD VNW pfet_06v0 W=1.22e-06 L=5e-07
X_i_1_3 VDD Z_neg Z VNW pfet_06v0 W=1.22e-06 L=5e-07
X_i_1_4 Z Z_neg VDD VNW pfet_06v0 W=1.22e-06 L=5e-07
X_i_1_5 VDD Z_neg Z VNW pfet_06v0 W=1.22e-06 L=5e-07
X_i_1_6 Z Z_neg VDD VNW pfet_06v0 W=1.22e-06 L=5e-07
X_i_1_7 VDD Z_neg Z VNW pfet_06v0 W=1.22e-06 L=5e-07
.ENDS

{gen_pwl_bus("COL_PROG_N", word_width, 8)}
{gen_pwl_bus("BIT_SEL", nwords, 2)}

{pwl_from_file("SENSE", 8)}
{pwl_from_file("PRESET_N", 8)}

.tran 10ps {time}
* serial solver is more efficient even for large arrays
.OPTIONS LINSOL TYPE=KLU

.print tran format=csv file={filename}.csv V(PRESET_N) V(SENSE) V(OUT*) V(COL_PROG_N*) V(BIT_SEL*) I(Xefuse_array:X*:RFUSE)
    """
    
    with open(filename, "w") as f:
        f.write(netlist)

def generate_spices(base_name : str, pdk_path : str, nwords : int, word_width : int, time : float = 100e-9, add_cells : Path | str = ""):
    """
    Generate a basic set of SPICE files - simulation & LVS netlists and Xyce test wrapper.
    """
    xyce_models_path = f"{pdk_path}/libs.tech/xyce/"

    spice_name = base_name + ".spice"
    lvs_name = base_name + ".klvs.spice"
    tb_name = base_name + "_test.xyce"

    if add_cells:
        with open(add_cells, "r") as f:
            add_cells_dict = json.load(f)
    else:
        add_cells_dict = {}

    generate_netlist(base_name, spice_name, nwords, word_width, False)
    generate_netlist(base_name, lvs_name, nwords, word_width, True, add_cells_dict)
    generate_xyce_test(base_name, tb_name, spice_name, xyce_models_path, nwords, word_width, time)

    return spice_name, lvs_name, tb_name

########## MAIN ########## 

def usage():
    print("Usage:", sys.argv[0], "bitlines bits_per_bitline")
    print("PDK_ROOT environmental variable must point to the directory containing gf180mcu PDK")
    sys.exit(1)

def main():
    try:
        nwords = int(sys.argv[1])
        word_width = int(sys.argv[2])
    except Exception:
        usage()

    base_name = f"efuse_array_{nwords}x{word_width}"

    if "PDK_ROOT" not in os.environ or "PDK" not in os.environ:
        usage()
    pdk_path = os.environ["PDK_ROOT"] + "/" + os.environ["PDK"]

    generate_spices(base_name, pdk_path, nwords, word_width, 1000)


if __name__ == '__main__':
    main()



