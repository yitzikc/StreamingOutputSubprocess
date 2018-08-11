import sys
assert(sys.version_info >= (3, 5))

import abc
import shlex
import asyncio
import collections
import functools

try:
    import colorlog as logging_mod
except ImportError:
    import logging as logging_mod

global logger
logger = logging_mod.getLogger(__name__)

class StreamingOutputSubprocess(metaclass=abc.ABCMeta):

    def __init__(self):
        self.processes = collections.OrderedDict()
        self.loop = None

    def run(self, cmdLine, tag = "default"):
        "Run a process synchronously, and keep running until all the processes have finished running"
        if self.loop is None:
            assert(self.runningProcessCount == 0)
            self.loop = asyncio.new_event_loop()
            # FIXME: Avoid polluting the global event loop. Apparently this is required in Python
            # 3.5. Should re-check this when we migrate to 3.6
            asyncio.set_event_loop(self.loop)

            mainRc = self.loop.run_until_complete(self.runMain(cmdLine, tag))
            self.loop.close()
            self.loop = None
            return mainRc
        else:
            future = self.runAsync(cmdLine, tag)
            asyncio.ensure_future(future, loop = self.loop)
            return None

    @property
    def totalProcessCount(self):
        return len(self.processes)

    @property
    def runningProcessCount(self):
        return len([ p for p in self.processes.values() if p.running ])

    @property
    def mainProcessStatus(self):
        for p in self.processes.values():
            return p.status

    class TaggedProcess(object):
        "A helper class representing a single process being run"
        def __init__(self, cmdLine, tag, owner):
            self.cmdLine = cmdLine
            self.tag     = tag
            self.owner   = owner
            self.status  = None
            self.process = None

        @property
        def complete(self):
            return self.status is not None

        @property
        def running(self):
            return self.process is not None and not self.complete

        async def run(self):
            cmdTokens = shlex.split(self.cmdLine)
            self.process = await asyncio.create_subprocess_exec(*cmdTokens,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, loop=self.owner.loop)

            return self.process

        @staticmethod
        async def _readStream(stream, cb):
            while True:
                line = await stream.readline()
                if line:
                    cb(line)
                else:
                    break

        async def stream(self):
            callbacks = [ functools.partial(cb, self.tag) for cb in (self.owner.onStdoutLine, self.owner.onStderrLine) ]
            await asyncio.wait([
                    self._readStream(self.process.stdout, callbacks[0]),
                    self._readStream(self.process.stderr, callbacks[1])
                ],
                loop = self.owner.loop)
            logger.debug(self.tag + " outputs presumably closed")
            self.status = await self.process.wait()
            assert(self.status == self.process.returncode)
            return self.status

    async def runAsync(self, cmdLine, tag):
        if tag in self.processes:
            raise ValueError("Duplicate tag: {}.".format(tag))

        process = self.TaggedProcess(cmdLine, tag, self)
        await process.run()
        self.processes[tag] = process
        self.onProcessStarted(tag)
        status = await process.stream()
        self.onProcessEnded(tag)
        return status

    async def runMain(self, cmdLine, tag):
        mainRc = await self.runAsync(cmdLine, tag)
        await self.awaitAllPendingTasks()
        return mainRc

    async def awaitAllPendingTasks(self):
        currentTask = asyncio.Task.current_task()
        while True:
            tasksPending = [ task for task in asyncio.Task.all_tasks(loop = self.loop) if task is not currentTask and not task.done() ]
            if len(tasksPending) > 0:
                logger.debug("{} task(s) are still pending after The main process has exited".format(len(tasksPending)))
                await asyncio.wait(tasksPending)
            else:
                break
        logger.debug("All the pending tasks have finished")

    # Methods which the user must override
    @abc.abstractmethod
    def onStdoutLine(self, tag, line: bytes):
        pass

    @abc.abstractmethod
    def onStderrLine(self, tag, line: bytes):
        pass

    # Methods which the user may optionally override
    def onProcessStarted(self, tag):
        logger.info("Process '{}' created with pid {}.".format(tag, self.processes[tag].process.pid))

    def onProcessEnded(self, tag):
        process = self.processes[tag]
        logger.info("Process '{}' pid {} exited with status {}.".format(tag, process.process.pid, process.status))

class StreamingOutputFormattingProcess(StreamingOutputSubprocess):
    class OutputSpec:
        "A helper class which the user would use to specify formatting and an output stream for each of stdout and stderr"
        def __init__(self, fmt = "{}", ostream = sys.stdout):
            assert(fmt.count("{}") == 1)
            self.fmt = fmt
            assert(callable(ostream.write))
            self.ostream = ostream

        def write(self, value):
            try:
                s = value.decode()
            except UnicodeDecodeError:
                s = str(value)
            self.ostream.write(self.fmt.format(s))

    def __init__(self, stdoutSpec, stderrSpec):
        super().__init__()
        self.stdoutSpec = stdoutSpec
        self.stderrSpec = stderrSpec

    def onStdoutLine(self, tag, line):
        self.stdoutSpec.write(line)

    def onStderrLine(self, tag, line):
        self.stderrSpec.write(line)
