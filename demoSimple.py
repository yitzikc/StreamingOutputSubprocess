#!/usr/bin/env python3

import logging
try:
    import colorlog as logging_mod
except ImportError:
    logging_mod = logging


import sys
sys.path.append(".")
from StreamingOutputSubprocess import StreamingOutputFormattingProcess

def demoSimple():
    cmd1 = "bash -c 'echo stdout && sleep 1 && echo stderr 1>&2 && sleep 1 && echo done && exit 1'"
    Spec = StreamingOutputFormattingProcess.OutputSpec
    sofp = StreamingOutputFormattingProcess(Spec("STDOUT: {}"), Spec("STDERR: {}", sys.stderr))
    status = sofp.run(cmd1)
    print("Finished with status: {}.".format(status))

if __name__ == "__main__":
    logging_mod.basicConfig(level = logging.DEBUG)
    demoSimple()
