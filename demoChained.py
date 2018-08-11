#!/usr/bin/env python3

import logging
try:
    import colorlog as logging_mod
except ImportError:
    logging_mod = logging


import sys
sys.path.append(".")
from StreamingOutputSubprocess import StreamingOutputFormattingProcess

def demoChained():
    """Demonstrate monitoring the standard error of a process for the string 'trigger', and when found - launching a second process
    which outlives its parent"""
    
    class ChainingSOFP(StreamingOutputFormattingProcess):
        def onStdoutLine(self, tag, line):
            super().onStdoutLine(tag, "[{}] {}".format(tag, line.decode()).encode())

        def onStderrLine(self, tag, line):
            super().onStderrLine(tag, "[{}] {}".format(tag, line.decode()).encode())
            if tag == "main" and b"trigger" in line:
                cmdChained = "bash -c 'echo chained stdout && sleep 2 && echo stderr chained 1>&2 && sleep 1 && echo done chained'"
                self.run(cmdChained, "chained")

    cmdInitial = "bash -c 'echo stdout && sleep 1 && echo trigger chained 1>&2 && sleep 1 && echo more output && sleep 1 && echo done && exit 3'"
    Spec = ChainingSOFP.OutputSpec
    sofp = ChainingSOFP(Spec("STDOUT: {}"), Spec("STDERR: {}", sys.stderr))
    status = sofp.run(cmdInitial, "main")
    print("Initial finished with status: {}.".format(status))

if __name__ == "__main__":
    print("demoChained:", demoChained.__doc__)
    logging_mod.basicConfig(level = logging.DEBUG)
    demoChained()
