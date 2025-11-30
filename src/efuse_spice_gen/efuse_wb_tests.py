"""Xyce eFuse tests generators reside here."""

import random
import logging
from math import log2
from .xyce_test_runner import XyceTestRunner

TRANSITION_TIME     = 0.5e-9
SETUP_TIME          = 13e-9
HOLD_TIME           = 1e-9
EFUSE_BLOW_CURRENT  = 12e-3
EFUSE_SAFE_CURRENT  = 1.5e-3

class EfuseWbTest(XyceTestRunner):
    """
    Class based on XyceTestRunner to run the tests on eFuse with Wishbone interface netlists.
    """
    def __init__(self, nwords : int, word_width : int, clock_period : float, tb : str, netlist : str, uut_file : str, is_flat : bool, vdd : float, ncpus : int = 1):
        self.nwords = nwords
        self.word_width = word_width
        self.addr_width = int(log2(self.nwords))
        self.clock_period = clock_period
        self.max_word_val = 2**self.word_width - 1
        self.is_flat = is_flat

        super().__init__(tb, netlist, uut_file, vdd, TRANSITION_TIME, ncpus)
        logging.getLogger(__name__)

        # create test memory array and empty blown map
        self.memory = [0] * self.nwords
        self.blown_map = {0 : 0}

        # patch flat netlist with parameters
        # if is_flat:
        #     self.regexp_patch(self.netlist, r"^X(\d+)( .* efuse)", r"X\1\2 PARAMS: NUM=\1")

    def new_test_run(self, test_name : str):
        """
        Prepare new test run keeping memory contents.
        """
        # start from the begining
        super().new_test_run(test_name)

        # patch flat netlist with parameters
        if self.is_flat:
            self.regexp_patch(self.uut_file, r"^X(\d+)( .* efuse)", r"X\1\2 PARAMS: NUM=\1")

        # create tb drivers
        self.preset_n = self.create_driver("write_enable_i", True)
        self.wb_clk_i = self.create_driver("wb_clk_i", False)
        self.wb_rst_i = self.create_driver("wb_rst_i", True)
        self.wb_cyc_i = self.create_driver("wb_cyc_i", False)
        self.wb_stb_i = self.create_driver("wb_stb_i", False)
        self.wb_we_i = self.create_driver("wb_we_i", False)
        self.wb_adr_i = self.create_bus_driver("wb_adr_i", self.addr_width, 0)
        # self.wb_sel_i = self.create_bus_driver("wb_sel_i", self.word_width//8, 0)
        self.wb_sel_i = self.create_driver("wb_sel_i", 0)
        self.wb_dat_i = self.create_bus_driver("wb_dat_i", self.word_width, 0)

        self.write_table_include("blown.map", self.blown_map)

    def clock_ticks(self, nclocks : int = 1):
        hp = self.clock_period/2-2*TRANSITION_TIME
        for i in range(nclocks):
            self.wait_for(SETUP_TIME)
            self.set(self.wb_clk_i, True)
            self.wait_for(hp)
            self.set(self.wb_clk_i, False)
            self.wait_for(hp-SETUP_TIME)

    def wb_reset(self):
        self.clock_ticks(4)
        self.set(self.wb_rst_i, False)
        self.clock_ticks(1)

    def perform_wb_read(self, addr : int, sleep : int = 1):
        """
        Generate PWL sequence for Wishbone read.
        """
        # create pwl data
        self.set(self.wb_adr_i, addr)
        self.set(self.wb_cyc_i, True)
        self.set(self.wb_stb_i, True)
        self.set(self.wb_we_i, False)
        self.clock_ticks(3)

        # check read val after simulation
        self.checks.append((self.time, "wb_ack_o", 1, 1))
        self.checks.append((self.time, "wb_dat_o", self.word_width, self.memory[addr]))

        self.set(self.wb_cyc_i, False)
        self.set(self.wb_stb_i, False)

        self.clock_ticks(sleep)

    def perform_efuse_write(self, addr : int, data : int, sleep : int = 1):
        """
        Generate PWL sequence for Wishbone read.
        """
        # create pwl data
        self.set(self.wb_adr_i, addr)
        self.set(self.wb_dat_i, data)
        self.set(self.wb_sel_i, (1<<(self.word_width//8))-1)
        self.set(self.wb_cyc_i, True)
        self.set(self.wb_stb_i, True)
        self.set(self.wb_we_i, True)
        self.clock_ticks(1002)

        # check read val after simulation
        self.checks.append((self.time, "wb_ack_o", 1, 1))
        # self.checks.append((self.time, "wb_dat_o", self.word_width, self.memory[addr]))

        self.set(self.wb_cyc_i, False)
        self.set(self.wb_stb_i, False)
        self.set(self.wb_we_i, False)

        self.clock_ticks(sleep)
        
        self.memory[addr] = data

    def fuse_num(self, s : str):
        """
        Get fuse number based on subcircuit hierarchy.
        """
        s = s.split(":")
        if self.is_flat:
            return int(s[1][1:])
        else:
            return int(s[1][1:])*1000 + int(s[2][1:])

    def add_to_blown_map(self, num):
        """
        Add fuse to a map of blown fuses to form a blown.map table.
        """
        logging.debug("Blown " + str(num))
        self.blown_map[num] = 1
        # mark previous and next with 0 if not present already, 0th element is always present
        if num+1 not in self.blown_map:
            self.blown_map[num+1] = 0
        if num-1 not in self.blown_map:
            self.blown_map[num-1] = 0


    def check_fuse_currents(self, blow_allowed : bool = True):
        """
        Check maximum currents flowing via each eFuse to determine which of them will be blown.
        """
        currents = self.get_max_currents()
        logging.debug("Blown fuses:")
        for c in currents:
            sc = self.fuse_num(c[0])
            if blow_allowed and (c[1] > EFUSE_BLOW_CURRENT):
                self.add_to_blown_map(sc)
            elif c[1] > EFUSE_SAFE_CURRENT:
                # assert False, f"Forbidden current level {c[1]} via fuse {sc} at time {c[2]} in test {self.test_name}"
                logging.warning(f"Forbidden current level {c[1]} via fuse {sc} at time {c[2]} in test {self.test_name}")

    def dump_memory(self):
        """
        Test memory array dump for debugging.
        """
        logging.debug("############### Memory dump ###############")
        for i in range(self.nwords):
            logging.debug(f"{i:04d} : {self.memory[i]:016x}")
        logging.debug("###########################################")

    def wb_single_test(self):
        """
        To simulate blown fuses we patch the netlist inbetween tests based on maximum current level through fuse.
        """
        # write wb memory
        self.new_test_run("xyce_wb_write")
        self.wb_reset()
        self.perform_efuse_write(29, 0xAA)
        # for i in range(self.nwords):
            # self.perform_efuse_write(i, random.randrange(self.max_word_val+1), random.randrange(10,100)*0.1e-9)
        self.simulate_and_check()
        self.check_fuse_currents()
        self.dump_memory()

        # read wb  memory
        self.new_test_run("xyce_wb_read")
        self.wb_reset()
        # for i in range(self.nwords):
        #     self.perform_efuse_read(i, random.randrange(10,100)*0.1e-9)
        self.perform_wb_read(29)
        self.simulate_and_check()
        self.check_fuse_currents(False)

    def run_tests(self) -> bool:
        """
        Run the test. Return True if everything has finished without errors.
        """
        try:
            self.wb_single_test()
            self.reset()
        except AssertionError as e:
            logging.error(e)
            return False
        return True
