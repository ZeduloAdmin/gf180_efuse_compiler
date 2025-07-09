# GF180MCU eFuse array compiler

This repository contains eFuse array compiler for the GF180MCU process. Original compiler was used to do a tapeout during thr Open MPW GFMPW-0 run, but this branch holds a newer compiler version with increased density and automated flow scripts. This branch is still in development phase and not ready for general use.

## Compiler features

eFuse compiler provides:

* Synchronous nonvolatile array of eFuse memory for GF180MCU process.
* GDS and over files necessary for integration into any GF180MCU-based chip design.
* Configurable word width and memory depth. Currently only 16, 32 and 64 words depths are supported.
* Support for the open source GF180MCU PDK.
* Digital wrapper with Wishbone interface to eFuse memory (TODO).

## Requirements

To generate and verify an eFuse array the following tools are required to be present in the PATH:
1. Python 3.8+ with klayout package (0.29+) installed.
2. KLayout 0.29+ (for DRC & LVS).
3. magic (any version compatible with GF180MCU PDK for the circuit extraction).
4. Xyce (any version compatible with GF180MCU PDK for the circuit verification).

Additionally the open source GF180MCU PDK should be installed and environmental variables PDK_ROOT should point to it's location and variable PDK to directory name. The recommended way to install the PDK is [ciel](https://github.com/fossi-foundation/ciel). Tested only on Linux system.

## How to run

An flow script for eFuse generation and verification efuse.py is located in repository root. It requires two parameters: eFuse memory depth in words and single word width, all other options are described in script help message. Runtime files will be produced in temporary runs directory and resulting files will be copied to macros directory.

For example to generate a minimal possible array with 16 1-bit eFuse words run:

```
./efuse.py 16 1
```

To generate 64x64 array skipping Xyce verification run:

```
./efuse.py --xyce_netlist=none 64 64
```

## Examples

Files for several precompiled configurations are provides in macros directory. Here are some GDS screenshots.

![efuse_array_16x1](docs/efuse_array_16x1.png?raw=true)

Minimal eFuse array with 16 1-bit words.

![efuse_array_64x8](docs/efuse_array_64x8.png?raw=true)

Larger eFuse array with 64 8-bit words.

## TODO

* Improve a sense amplifier to reduce read currents.
* Add a digital wrapper generation for Wishbone and probably SPI interfaces.
* Fill sense amp digital cells column with buffers and capacitor cells.
* Allow more different memory configurations and improve aspect ratios for large arrays.
* Add some documentation.