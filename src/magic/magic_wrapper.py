import logging
import sys
from os import environ, remove
from subprocess import run, STDOUT, DEVNULL
from pathlib import Path

def magic(script : Path, args : dict, log : str):
    """
    Run magic script. Passes arguments via environment.
    """
    args.update(environ)
    output = open(log, "w")
    try:
        tmp_script = "_magic_tmp.tcl"
        with open(tmp_script, "w") as f:
            f.write(f'catch {{ source {script} }} err\nputs $err\nif {{$err != ""}} {{exit 1}}')
        run(
            ["magic", "-noconsole", "-dnull", "-rcfile", Path(environ['PDK_ROOT']) / environ['PDK'] / f"libs.tech/magic/{environ['PDK']}.magicrc", tmp_script],
            check = True,
            stdout = output,
            env = args,
            stderr = STDOUT,
            stdin = DEVNULL
        )
        remove(tmp_script)
    except Exception:
        logging.error(f"Magic run failed, please check the logfile for more info {log}")
        sys.exit(1)
    
