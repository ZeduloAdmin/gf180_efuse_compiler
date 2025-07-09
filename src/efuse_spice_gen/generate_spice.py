#!/usr/bin/env python3
#
# Small script to generate eFuse array SPICE netlists for LVS & simulation
#

import os
import sys

def write_magic_ports(filename : str, ports : str):
    port_list = ports.split(" ")
    with open(filename, "w") as f:
        for i,p in enumerate(port_list):
            if p.strip():
                print(f"""port {{{p}}} index {i}""", file=f)
            
def subcircuit(name : str, ports : str, body : str) -> str:
    return f"""
.subckt {name} {ports}
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
        body += f"X{i} VSS BIT_SEL[{i}] bitline efuse_bitcell\n"
        
    # add programming PMOS
    # !actually currently it's 4 fingers, not 2 fingers x2, but there is no such model
    body += f"""{device_naming[0]}0 bitline COL_PROG_N VDD VDD p{device_naming[1]} L=0.50u W=76.5u nf=2"""
    body += "\n"
    body += f"""{device_naming[0]}1 bitline COL_PROG_N VDD VDD p{device_naming[1]} L=0.50u W=76.5u nf=2"""
    body += "\n"
    # add sensamp
    body += "Xsense VDD PRESET_N OUT SENSE VSS bitline efuse_senseamp"
    
    return subcircuit("efuse_bitline", bitline_ports, body)

def efuse_array(cellname : str, word_width : int, n_fuses : int) -> str:
    common_ports = "VSS VDD SENSE PRESET_N " + "".join([f'BIT_SEL[{j}] ' for j in range(n_fuses)])
    array_ports = common_ports

    body = ""
    for i in range(word_width):
        bitline_ports = f"COL_PROG_N[{i}] OUT[{i}] "
        body += f"X0_{i} {common_ports} {bitline_ports} efuse_bitline\n"
        array_ports += bitline_ports

    write_magic_ports("efuse_array_ports.tcl", array_ports)
    
    return subcircuit(cellname, array_ports, body), array_ports

def generate_netlist(cellname : str, filename : str, nwords : int, word_width : int, klayout_lvs : bool = False):

    device_naming = ["X", "fet_06v0"]
        
    if klayout_lvs:
        device_naming[0] = "M"
        device_naming[1] = "mos_5p0"
        
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

.subckt efuse_bitcell VSS SELECT ANODE
X0 ANODE CATHODE efuse
{device_naming[0]}1 CATHODE SELECT VSS VSS n{device_naming[1]} L=0.60u W=30.5u
.ends

.subckt efuse_senseamp  VDD PRESET_N OUT SENSE VSS FUSE
{device_naming[0]}2 net1 PRESET_N VDD VDD p{device_naming[1]} L=0.5u W=2.44u nf=2
x1 net2 OUT VDD VDD VSS VSS gf180mcu_fd_sc_mcu7t5v0__inv_1
x2 net1 net2 VDD VDD VSS VSS gf180mcu_fd_sc_mcu7t5v0__inv_1
x3 net2 net1 VDD VDD VSS VSS gf180mcu_fd_sc_mcu7t5v0__inv_1
{device_naming[0]}1 net1 SENSE FUSE VSS n{device_naming[1]} L=0.60u W=0.82u
.ends

{efuse_bitline(nwords, device_naming)}
{efuse_array(cellname, word_width, nwords)[0]}
.end
    """
    with open(filename, "w") as f:
        f.write(netlist)

def pwl_from_file(name : str):
    return f"V{name} {name} 0 PWL FILE \"{name}.pwl\"\n"
    
def constant_driver(name : str, value : float):
    return f"""V{name} {name} 0 {value}\n"""

def gen_pwl_bus(name : str, size : int):
    return "".join([pwl_from_file(f'{name}[{i}]') for i in range(0, size)])

def generate_xyce_test(cellname : str, filename : str, spice_name : str, xyce_models_path : str, nwords : int, word_width : int, time : float = 100, vdd : float = 5.0):
    array_ports = efuse_array(cellname, word_width, nwords)[1]
    netlist = f"""* Xyce testbench for {cellname}
.option TEMP=25.0

{constant_driver("VSS", 0)}
{constant_driver("VDD", vdd)}

.lib "{xyce_models_path}/design.xyce" typical
.lib "{xyce_models_path}/sm141064.xyce" typical

.SUBCKT efuse ANODE CATHODE PARAMS: PBLOW=0
Rfuse ANODE CATHODE R='200*(1-PBLOW) + 10000*PBLOW'
.ENDS efuse

.include {spice_name}

Xefuse_array {array_ports} {cellname}

{gen_pwl_bus("COL_PROG_N", word_width)}
{gen_pwl_bus("BIT_SEL", nwords)}

{pwl_from_file("SENSE")}
{pwl_from_file("PRESET_N")}

.tran 10ps {time}

.print tran format=csv file={filename}.csv V(PRESET_N) V(SENSE) V(OUT*) V(COL_PROG_N*) V(BIT_SEL*) I(Xefuse_array:X*:RFUSE)
* I(VVDD) V(BIT_SEL*)
    """
    
    with open(filename, "w") as f:
        f.write(netlist)

def generate_spices(base_name : str, pdk_path : str, nwords : int, word_width : int, time : float = 100e-9):
    """
    Generate a basic set of SPICE files - simulation & LVS netlists and Xyce test wrapper.
    """
    xyce_models_path = f"{pdk_path}/libs.tech/xyce/"

    spice_name = base_name + ".spice"
    lvs_name = base_name + ".klvs.spice"
    tb_name = base_name + "_test.xyce"

    generate_netlist(base_name, spice_name, nwords, word_width, False)
    generate_netlist(base_name, lvs_name, nwords, word_width, True)
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



