#!/usr/bin/env python3
#
# Librelane helper script for eFuse digital wrappers generation
#

import os
import json
import logging
import subprocess as sp
from pathlib import Path

class LibrelaneRunner():
    """
    Helper class to run Librelane
    """
    def __init__(self):

        # create basic config for GF180MCU
        self.config = dict()

        self.config["meta"] = {"version" : 2, "flow" : "Classic"}

        self.substitute_step("KLayout.DRC")
        self.substitute_step("Checker.KLayoutDRC")

        self.config["PRIMARY_GDSII_STREAMOUT_TOOL"] = "klayout"
        self.config["PL_KEEP_RESIZE_BELOW_OVERFLOW"] = 0

        self.config["VDD_NETS"] = ["VDD"]
        self.config["GND_NETS"] = ["VSS"]

        self.config["MACROS"] = {}

    def substitute_step(self, step : str, sub : str = None):
        if "substituting_steps" not in self.config["meta"]:
            self.config["meta"]["substituting_steps"] = {}
        self.config["meta"]["substituting_steps"][step] = sub

    def add_macro(self, name : str, gds : str, lef : str, nl : str, instances : list):
        
        self.config["MACROS"][name] = macro = dict()
        macro["gds"] = [ str(gds) ]
        macro["lef"] = [ str(lef) ]
        macro["nl"] = [ str(nl) ]

        macro["instances"] = {}

        for i in instances:
            macro["instances"][i] = inst = dict()
            inst["location"] = [ instances[i][0], instances[i][1] ]
            inst["orientation"] = instances[i][2]

    def run(self):
        """
        Create necessary files and run Librelane with config from dict
        """
        orig_wd = os.getcwd()
        os.makedirs("librelane", exist_ok=True)
        os.chdir("librelane")

        with open("config.json", "w") as f:
            json.dump(self.config, f, indent = 4)
        
        log = Path("librelane.log").absolute()
        try:
            run = sp.run(["librelane", "config.json", "--pdk", os.environ["PDK"], "--pdk-root", os.environ["PDK_ROOT"], "--manual-pdk"],
                stdout = sp.PIPE, stderr = sp.STDOUT, check = True)
            with open(log, "a") as f:
                f.write(run.stdout.decode("utf-8"))
            self.final = list(Path("runs").glob("*/final"))[0].absolute()

            self.gds = self.final / "gds" / f"{self.name}.gds"
            self.lef = self.final / "lef" / f"{self.name}.lef"
            self.nl  = self.final / "nl"  / f"{self.name}.nl.v"
            self.pnl = self.final / "pnl" / f"{self.name}.pnl.v"
            self.lib = self.final / "lib"
            self.sdf = self.final / "sdf"
            
        except sp.CalledProcessError as e:
            logging.error(f"Librelane run failed! See {log} for log.")
            with open(log, "w") as f:
                f.write(e.stdout.decode("utf-8"))
            self.final = None

        os.chdir(orig_wd)
        return self.final


class EfuseLibrelaneWb(LibrelaneRunner):
    """
    eFuse memory Wishbone wrapper implementation in Librelane
    """
    def __init__(self, macro : str, gds : str, lef : str, nwords : int, word_width : int):

        super().__init__()

        cd = Path(__file__).parent.absolute()

        self.macro = macro
        self.nwords = nwords
        self.word_width = word_width
        nl = Path(f"{macro}.v").absolute()

        self.gen_verilog_blackbox(nl)

        # skip some steps
        self.substitute_step("Verilator.Lint")
        self.substitute_step("Magic.StreamOut")
        self.substitute_step("KLayout.XOR")
        self.substitute_step("OpenROAD.IRDropReport")

        # set basic vars
        self.name = f"efuse_wb_mem_{nwords}x{word_width}"
        self.config["DESIGN_NAME"] = self.name
        self.config["VERILOG_FILES"] = [ str(cd / "efuse_wb_mem.v") ]
        self.config["VERILOG_DEFINES"] = [f"EFUSE_WBMEM_NAME={self.name}", f"EFUSE_ARRAY_NAME={macro}"]
        self.config["SYNTH_PARAMETERS"] = [f"EFUSE_NWORDS={nwords}", f"EFUSE_WORD_WIDTH={word_width}"]
        self.config["PNR_SDC_FILE"] = [ str(cd / "constraints.sdc") ]
        self.config["CLOCK_PORT"] = "wb_clk_i"
        self.config["CLOCK_PERIOD"] = 20

        # floorplan & PDN
        self.config["FP_SIZING"] = "absolute"
        cm = 10
        self.config["DIE_AREA"] = da = [0, 0, 240, 350]
        self.config["CORE_AREA"] = [da[0] + cm, da[1] + cm, da[2] - cm, da[3] - cm]
        self.config["IO_PIN_ORDER_CFG"] = str(cd / "pin.cfg")

        self.config["FP_PDN_CORE_RING"] = True
        self.config["PDN_CORE_RING_VWIDTH"] = 2
        self.config["PDN_CORE_RING_HWIDTH"] = 2
        self.config["PDN_CORE_RING_VSPACING"] = 0.5
        self.config["PDN_CORE_RING_HSPACING"] = 0.5
        self.config["PDN_CORE_RING_VOFFSET"] = 4
        self.config["PDN_CORE_RING_HOFFSET"] = 7

        self.config["PDN_HPITCH"] = 50
        self.config["PDN_HOFFSET"] = 5
        self.config["PDN_VPITCH"] = 50
        self.config["PDN_VOFFSET"] = 5
        self.config["FP_MACRO_HORIZONTAL_HALO"] = 5
        self.config["PDN_CFG"] = str(cd / "pdn_cfg.tcl")

        # PnR
        self.config["PL_MAX_DISPLACEMENT_Y"] = 500
        self.config["RT_MAX_LAYER"] = "Metal4"
        self.config["RUN_ANTENNA_REPAIR"] = False
        self.config["GRT_ALLOW_CONGESTION"] = True
        self.config["RSZ_DONT_TOUCH_RX"] = ".*_keep_cell"
        self.config["ROUTING_OBSTRUCTIONS"] = [["Metal4", 0, 0, da[2], 30]]

        # efuse macro
        self.add_macro(macro, gds, lef, nl, {"efuse_array" : [70, cm + 5, "N"]})

    def gen_verilog_blackbox(self, fname : str):
        verilog = f"""
(* blackbox *)
module {self.macro} #(
    parameter NWORDS = {self.nwords},
    parameter WORD_WIDTH = {self.word_width}
) (
    input  [NWORDS-1:0]     BIT_SEL,
    input  [WORD_WIDTH-1:0] COL_PROG_N,
    input                   PRESET_N,
    input                   SENSE,
    output [WORD_WIDTH-1:0] OUT
);
endmodule
        """
        with open(fname, "w") as f:
            f.write(verilog)