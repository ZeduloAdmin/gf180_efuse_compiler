import os
import random
import logging
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer
from cocotb_tools.runner import get_runner
from cocotbext.wishbone.driver import WishboneMaster, WBOp

sim = os.getenv("SIM", "icarus")
pdk_root = os.getenv("PDK_ROOT", Path("~/.ciel").expanduser())
pdk = os.getenv("PDK", "gf180mcuD")
scl = os.getenv("SCL", "gf180mcu_fd_sc_mcu7t5v0")
# gl = os.getenv("GL", False)

hdl_toplevel = "efuse_wb_mem"

FILL_RATIO              = 0.4
READ_PROB               = 0.45
UNWRITTEN_READS_RATIO   = 0.1
SLEEP_PERIODS           = 10

WBM_SIGNALS_DICT ={ "cyc"   : "cyc_i",
                    "stb"   : "stb_i",
                    "we"    : "we_i",
                    "adr"   : "adr_i",
                    "datwr" : "dat_i",
                    "datrd" : "dat_o",
                    "ack"   : "ack_o" }

class EfuseWishboneTest:

    def __init__(self, dut, freq=50):
        self.dut = dut
        self.clk = Clock(dut.wb_clk_i, 1 / freq * 1000, "ns")
        cocotb.start_soon(self.clk.start())

        self.wb = WishboneMaster(self.dut, "wb", dut.wb_clk_i, width = 32, timeout = 10000, signals_dict = WBM_SIGNALS_DICT)

        self.word_width = int(dut.EFUSE_WORD_WIDTH.value)
        self.nwords = int(dut.EFUSE_NWORDS.value)
        self.period = 1000 / freq

    async def reset(self, time_ns=1000):
        """
        Reset dut
        """
        cocotb.log.info("Reset asserted...")

        self.dut.write_disable_i.value = 1
        
        self.dut.wb_rst_i.value = 1
        await Timer(100, "ns")
        self.dut.write_disable_i.value = 0
        await Timer(time_ns, "ns")
        self.dut.wb_rst_i.value = 0

        cocotb.log.info("Reset deasserted.")

    async def sleep(self):
        """
        Sleep for some time
        """
        t = random.randrange(SLEEP_PERIODS)
        if t:
            await Timer(self.period * t)

    async def wb_read_write_test(self):
        """
        Write to and read some data from eFuse
        """

        # mix writes and reads
        writes = 0
        writes_done = False
        written = []
        to_read = []
        while (not writes_done) or to_read:
            r = random.random()
            if (not writes_done) and ((not to_read) or (r > READ_PROB)):
                # write to random address
                addr = random.randrange(self.nwords)
                while addr in written:
                    addr = random.randrange(self.nwords)
                dat = random.randrange(2**self.word_width)
                to_read.append((addr, dat))
                written.append(addr)
                await self.wb_slv_write(addr, dat)
                cocotb.log.info(f"Write: 0x{addr:0{8}x} - 0x{dat:0{8}x}")
                writes += 1
                writes_done = (writes >= self.nwords * FILL_RATIO)
            else:
                # read random address already written & verify
                i = random.randrange(len(to_read))
                addr = to_read[i][0]
                dat = (await self.wb_slv_read(addr)).to_unsigned()
                cocotb.log.info(f"Read:  0x{addr:0{8}x} - 0x{dat:0{8}x}")
                assert(dat == to_read[i][1])
                to_read.pop(i)
            await self.sleep()

        # read several unwritten addresses
        for i in range(int(self.nwords * UNWRITTEN_READS_RATIO)):
            addr = random.randrange(self.nwords)
            while addr in written:
                addr = random.randrange(self.nwords)
            dat = (await self.wb_slv_read(addr)).to_unsigned()
            cocotb.log.info(f"Read:  0x{addr:0{8}x} - 0x{dat:0{8}x}")
            assert(dat == 0)
            await self.sleep()

    async def wb_slv_read(self, addr):
        """
        Read Wishbone bus
        """
        wbres = await self.wb.send_cycle([WBOp(adr=addr)]) 
        return wbres[0].datrd
        
    async def wb_slv_write(self, addr, dat):
        """
        Write Wishbone bus
        """
        await self.wb.send_cycle([WBOp(adr=addr, dat=dat)]) 


@cocotb.test()
async def test_wb_memory(dut):
    """Run Wishbone eFuse test"""

    # Create a logger for this testbench
    logger = logging.getLogger("test_wb_memory")

    logger.info("Startup sequence...")

    # Start up
    test = EfuseWishboneTest(dut)
    await test.reset()

    logger.info("Running the test...")

    await test.wb_read_write_test()

    logger.info("Done!")


def cocotb_runner():

    proj_path = Path(__file__).resolve().parent

    sources = []
    defines = {"FUNCTIONAL" : 1}
    includes = []

    sources.append(proj_path / "efuse_array.v")
    sources.append(proj_path / "../efuse_wb_mem.v")

    # standard cell models
    sources.append(Path(pdk_root) / pdk / "libs.ref" / scl / "verilog" / f"{scl}.v")
    sources.append(Path(pdk_root) / pdk / "libs.ref" / scl / "verilog" / "primitives.v")

    build_args = []

    if sim == "icarus":
        # For debugging
        # build_args = ["-Winfloop", "-pfileline=1"]
        pass

    if sim == "verilator":
        build_args = ["--timing", "--trace", "--trace-structs", "-Wno-fatal"]

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel=hdl_toplevel,
        defines=defines,
        always=True,
        includes=includes,
        build_args=build_args,
        waves=True,
        parameters={"EFUSE_WORD_WIDTH" : 8, "EFUSE_NWORDS" : 64},
        timescale=("1ns", "1ps")
    )

    plusargs = []

    runner.test(
        hdl_toplevel=hdl_toplevel,
        test_module="efuse_wb_cocotb",
        plusargs=plusargs,
        waves=True,
    )


if __name__ == "__main__":
    cocotb_runner()
