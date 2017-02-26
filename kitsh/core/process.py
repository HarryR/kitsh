from __future__ import print_function

import os
import pty
from subprocess import PIPE, Popen

from gevent.select import select

__all__ = ('Process',)


class Process(object):
    def __init__(self, args, env=None, executable=None, shell=False):
        master, slave = pty.openpty()
        self._master = os.fdopen(master)
        self._slave = os.fdopen(slave)
        self._args = args
        self._ret = None
        self._proc = Popen(
            args, env=env, executable=executable, shell=shell,
            stdin=self._master, stdout=PIPE, stderr=PIPE, bufsize=0,
            universal_newlines=True)

    def write(self, msg):
        if 'data' in msg:
            self._master.write(msg['data'])

    def run(self, task):
        with task.input.watch(self.write):
            proc = self._proc
            readable = [proc.stdout, proc.stderr]
            while len(readable):
                sock_sets = select(readable, [], [])
                for sock in sock_sets[0]:
                    data = sock.read()
                    if not data or data is StopIteration:
                        readable.remove(sock)
                        break
                    if sock == proc.stdout:
                        task.output.send(dict(data=data))
                    elif sock == proc.stderr:
                        task.output.send(dict(error=data))
            self._ret = self._proc.wait()
            return self._ret

    def stop(self):
        self._master.close()
        self._slave.close()
        self._proc.stdout.close()
        self._proc.stderr.close()
