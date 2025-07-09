"""Xyce eFuse tests generators reside here."""

import random
import logging
from .xyce_test_runner import XyceTestRunner

PRESET_TIME         = 10e-9
BITSEL_TIME         = 10e-9
SENSE_TIME          = 10e-9
PROG_TO_SEL_TIME    = 10e-9
PROG_TIME           = 100e-9
EFUSE_BLOW_CURRENT  = 12e-3
EFUSE_SAFE_CURRENT  = 1e-3

class EfuseArrayTest(XyceTestRunner):
    """
    Class based on XyceTestRunner to run the tests on eFuse array netlists.
    """
    def __init__(self, nwords : int, word_width : int, tb : str, netlist : str, uut_file : str, vdd : float, ncpus : int = 1):
        self.nwords = nwords
        self.word_width = word_width
        self.max_word_val = 2**self.word_width - 1

        super().__init__(tb, netlist, uut_file, vdd, 0.1e-9, ncpus)
        logging.getLogger(__name__)

        # create test memory array
        self.memory = [0] * self.nwords

    def new_test_run(self, test_name : str):
        """
        Prepare new test run keeping memory contents.
        """
        # start from the begining
        super().new_test_run(test_name)

        # create tb drivers
        self.preset_n = self.create_driver("PRESET_N", True)
        self.sense = self.create_driver("SENSE", False)
        self.col_prog_n = self.create_bus_driver("COL_PROG_N", self.word_width, self.max_word_val)
        self.bit_sel = self.create_bus_driver("BIT_SEL", self.nwords, 0)

    def perform_efuse_read(self, word_addr : int, sleep : float = 0.0):
        """
        Generate PWL sequence for eFuse read.
        """
        # create pwl data
        self.set(self.preset_n, False)
        self.set(self.sense, True)
        self.wait_for(PRESET_TIME)
        self.set(self.preset_n, True)
        self.wait_for(BITSEL_TIME)
        self.set(self.bit_sel, 1<<word_addr)
        self.wait_for(SENSE_TIME)
        self.set(self.sense, False)
        self.set(self.bit_sel, 0)

        # check read val after simulation
        self.checks.append((self.time, "OUT", self.word_width, self.memory[word_addr]))

        self.wait_for(sleep)

    def perform_efuse_write(self, word_addr : int, data : int, sleep : float = 0.0):
        """
        Generate PWL sequence for eFuse write.
        """
        # create pwl data
        self.set(self.sense, True) # perform sense to remove charge from bitline prior to writing
        self.wait_for(SENSE_TIME)
        self.set(self.sense, False)
        self.wait_for(PROG_TO_SEL_TIME)
        self.set(self.col_prog_n, self.max_word_val - data)  # binary negated data
        self.wait_for(PROG_TO_SEL_TIME)
        self.set(self.bit_sel, 1<<word_addr)
        self.wait_for(PROG_TIME)
        self.set(self.bit_sel, 0)
        self.set(self.col_prog_n, self.max_word_val)
        
        self.wait_for(sleep)

        self.memory[word_addr] = data

    def check_fuse_currents(self, blow_allowed : bool = True):
        """
        Check maximum currents flowing via each eFuse to determine which of them will be blown.
        """
        currents = self.get_max_currents()
        logging.debug("Blown fuses:")
        for c in currents:
            sc = c[0].split(":")[1]
            if blow_allowed and (c[1] > EFUSE_BLOW_CURRENT):
                logging.debug(sc)
                self.regexp_patch(self.netlist, f"^({sc} .* efuse)", r"\1 PARAMS: PBLOW=1")
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

    def full_range_test(self):
        """
        Simple eFuse test which first fills whole array with random data and reads ant verifies it afterwards.
        To simulate blown fuses we patch the netlist inbetween tests based on maximum current level through fuse.
        """
        # write all memory
        self.new_test_run("xyce_full_write")
        self.wait_for(10e-9)
        for i in range(self.nwords):
            self.perform_efuse_write(i, random.randrange(self.max_word_val+1), random.randrange(10,100)*0.1e-9)
        self.simulate_and_check()
        self.check_fuse_currents()
        self.dump_memory()

        # read all memory
        self.new_test_run("xyce_full_read")
        self.wait_for(10e-9)
        for i in range(self.nwords):
            self.perform_efuse_read(i, random.randrange(10,100)*0.1e-9)
        self.simulate_and_check()
        self.check_fuse_currents(False)

    def run_tests(self) -> bool:
        """
        Run the test. Return True if everything have finished without errors.
        """
        try:
            self.full_range_test()
            self.reset()
        except AssertionError as e:
            logging.error(e)
            return False
        return True
