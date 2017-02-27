from __future__ import print_function

import os
import pty
import logging
import struct
import termios
import fcntl
from subprocess import PIPE

import gevent
from gevent.subprocess import Popen
from gevent.select import select

__all__ = ('Process',)


LOG = logging.getLogger(__name__)


def set_winsize(fd, row, col, xpix=0, ypix=0):
    winsize = struct.pack("HHHH", row, col, xpix, ypix)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


class Process(object):
    def __init__(self, args, env=None, executable=None, shell=False):
        master, slave = pty.openpty()
        fcntl.fcntl(master, fcntl.F_SETFL, os.O_NONBLOCK)
        self._master = master
        self._args = args
        self._ret = None
        self._proc = Popen(
            args, env=env, executable=executable, shell=shell,
            stdin=slave, stdout=PIPE, stderr=PIPE, bufsize=0,
            universal_newlines=False)

    def __repr__(self):
        return "Process:%x %r" % (id(self), self._args)

    def _writer(self, inch):
        for msg in inch.watch():
            if 'resize' in msg:
                set_winsize(self._master, msg['resize']['width'], msg['resize']['height'])
            if 'data' in msg:
                writable = [self._master]
                buf = msg['data']
                while len(buf):
                    sock_sets = select([], writable, [])
                    for sock in sock_sets[1]:
                        nwritten = os.write(sock, msg['data'])
                        buf = buf[nwritten:]

    def run(self, task):
        writer_task = gevent.spawn(self._writer, task.input)
        proc = self._proc
        readable = [proc.stdout, proc.stderr]
        while len(readable):
            sock_sets = select(readable, [], [])
            for sock in sock_sets[0]:
                data = sock.read(1024)
                if not data or data is StopIteration:
                    readable.remove(sock)
                    break                
                if sock == proc.stdout:
                    task.output.send(dict(data=data))
                elif sock == proc.stderr:
                    task.output.send(dict(error=data))
        self._ret = self._proc.wait()
        writer_task.kill()

    def stop(self):
        self._master.close()
        self._slave.close()
        self._proc.stdout.close()
        self._proc.stderr.close()
