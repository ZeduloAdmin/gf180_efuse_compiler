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

        self.config["VDD_NETS"] = ["VDD"]
        self.config["GND_NETS"] = ["VSS"]

    def substitute_step(self, step : str, sub : str = "null"):
        self.config["meta"]["substituting_steps"] = {step : sub}

    def add_macro(self, name : str, gds : str, lef : str, nl : str, instances : list):
        
        self.config["MACROS"][name] = macro = dict()
        macro["gds"] = [ gds ]
        macro["lef"] = [ lef ]
        # macro["nl"] = [ nl ]

        for i in instances:
            macro["instances"][i] = inst = dict()
            inst["localtion"] = [ instances[i][0], instances[i][1] ]
            inst["orientation"] = [ instances[i][2] ]

    def run_librelane(config : dict):
        """
        Create necessary files and run Librelane with config from dict
        """
        orig_wd = os.getcwd()
        os.makedirs("librelane", exist_ok=True)
        os.chdir("librelane")

        with open("config.json", "w") as f:
            json.dump(config, f)
        
        try:
            sp.run(["librelane", "config.json", "--pdk", os.environ["PDK"], "--pdk-root", os.environ["PDK_ROOT"], "--manual-pdk"],
                stdout = sp.PIPE, stderr = sp.STDOUT, check = True)
        except sp.CalledProcessError as e:
            logging.error("Librelane run failed! " + e.stdout.decode("utf-8"))

        os.chdir(orig_wd)


class EfuseLibrelaneWb(LibrelaneRunner):
    """
    eFuse memory Wishbone wrapper implementation in Librelane
    """
    def __init__(self, macro : str, gds : str, lef : str, nwords : int, word_width : int):

        super.__init__()

        cd = Path(__file__).parent.absolute()

        # skip some steps
        self.substitute_step("Verilator.Lint")
        self.substitute_step("Magic.StreamOut")
        self.substitute_step("KLayout.XOR")

        # set basic vars
        self.config["DESIGN_NAME"] = f"efuse_wb_mem_{nwords}x{word_width}"
        self.config["VERILOG_FILES"] = [ str(cd / "efuse_wb_mem.v") ]
        self.config["PNR_SDC_FILE"] = [ str(cd / "constraints.sdc") ]
        self.config["CLOCK_PORT"] = "wb_clk_i"
        self.config["CLOCK_PERIOD"] = 50

        # floorplan & PDN
        self.config["FP_SIZING"] = "absolute"
        self.config["DIE_AREA"] = [0, 0, 220, 325]
        self.config["CORE_AREA"] = [2, 2, 218, 323]
        self.config["FP_PIN_ORDER_CFG"] = str(cd / "pin.cfg")

        self.config["PDN_SKIPTRIM"] = "true"
        self.config["PDN_MULTILAYER"] = "false"
        self.config["PDN_HPITCH"] = 50
        self.config["PDN_HOFFSET"] = 5
        self.config["PDN_VPITCH"] = 50
        self.config["PDN_VOFFSET"] = 5
        self.config["FP_MACRO_HORIZONTAL_HALO"] = 5
        self.config["ERROR_ON_PDN_VIOLATIONS"] = "false"
        self.config["PDN_CFG"] = str(cd / "pdn_cfg.tcl")

        # PnR
        self.config["PL_MAX_DISPLACEMENT_Y"] = 500
        self.config["RT_MAX_LAYER"] = "Metal4"

        # efuse macro
        self.add_macro(macro, gds, lef, {"efuse_rom_inst" : [65, 5, "N"]})