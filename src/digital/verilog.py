#
# Verilog generation helpers for eFuse array
#

import re
from pathlib import Path

class EfuseVerilog:
    def __init__(self, name : str, nwords : int, word_width : int, out_dir : Path = Path(".")):
        self.name = name
        self.nwords = nwords
        self.word_width = word_width
        self.odir = out_dir

    @staticmethod 
    def regexp_patch(ifile : Path, ofile : Path, regex : str, sub : str):
        with open(ifile, "r") as f:
            patched = re.sub(regex, sub, f.read(), flags = re.M | re.I)
        with open(ofile, "w") as f:
            f.write(patched)

    def patch_verilog_model(self, ifname : Path, ofname : Path):
        """
        Patch generic Verilog model with specific name & sizes
        """
        self.regexp_patch(ifname, ofname, "module efuse_array", f"module {self.name}")
        self.regexp_patch(ofname, ofname, "parameter NWORDS = 16", f"parameter NWORDS = {self.nwords}")
        self.regexp_patch(ofname, ofname, "parameter WORD_WIDTH = 1", f"parameter WORD_WIDTH = {self.word_width}")


    def gen_verilog_blackbox(self, fname : Path):
        """
        Generate array verilog blackbox
        """
        verilog = f"""
(* blackbox *)
module {self.name} #(
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

    def gen_verilog(self):
        self.bb_file = (self.odir / f"{self.name}_bb.v").absolute()
        self.gen_verilog_blackbox(self.bb_file)
        cd = Path(__file__).parent.absolute()
        self.model_file = (self.odir / f"{self.name}.v").absolute()
        self.patch_verilog_model(cd / "tb/efuse_array.v", self.model_file)