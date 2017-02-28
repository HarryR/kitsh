from __future__ import print_function

import os
import pty
import logging
import struct
import fcntl
import termios

import gevent
from gevent.hub import get_hub
from gevent.socket import wait, cancel_wait
from gevent.event import Event
from gevent.subprocess import Popen

__all__ = ('Process',)


LOG = logging.getLogger(__name__)


def set_winsize(fileno, row, col, xpix=0, ypix=0):
    winsize = struct.pack("HHHH", row, col, xpix, ypix)
    fcntl.ioctl(fileno, termios.TIOCSWINSZ, winsize)


class Process(object):
    # TODO: handle bot stdout and stderr
    # TODO: refactor into TTY, Process and TTYProcess?
    def __init__(self, args, env=None, executable=None, shell=False):
        master, slave = pty.openpty()
        fcntl.fcntl(master, fcntl.F_SETFL, os.O_NONBLOCK)

        self._finished = Event()
        self._master = master
        self._read_event = get_hub().loop.io(master, 1)
        self._write_event = get_hub().loop.io(master, 2)
        self._args = args
        self._proc = Popen(
            args, env=env, executable=executable, shell=shell,
            stdin=slave, stdout=slave, stderr=slave, bufsize=0,
            universal_newlines=False, close_fds=True)

    def __repr__(self):
        return "Process:%x %r" % (id(self), self._args)

    @property
    def finished(self):
        return self._finished.ready()

    def _waitclosed(self):
        self._proc.wait()
        self.stop()

    def _writer(self, inch):
        """
        This greenlet will block until messages are ready to be written to pty
        """
        try:
            sock = self._master
            for msg in inch.watch():
                if 'resize' in msg:
                    set_winsize(sock, msg['resize']['width'], msg['resize']['height'])
                if 'data' in msg:
                    buf = msg['data']
                    while not self.finished and len(buf):
                        try:
                            wait(self._write_event)
                        except Exception:
                            break
                        nwritten = os.write(sock, msg['data'])
                        buf = buf[nwritten:]
        except Exception:
            LOG.exception("In Process._writer")

    def run(self, task):
        writer_task = gevent.spawn(self._writer, task.input)
        gevent.spawn(self._waitclosed)
        proc = self._proc
        try:
            sock = self._master
            while not self.finished:
                try:
                    wait(self._read_event)
                except Exception:
                    break
                data = os.read(sock, 1024)
                if len(data) == 0 or data is StopIteration:
                    break                
                if sock == proc.stderr:
                    task.output.send(dict(error=data))
                else:
                    task.output.send(dict(data=data))
        except Exception:
            LOG.exception("While reading from process")
        finally:
            writer_task.kill()
            self.stop()

    def stop(self):
        if not self.finished:
            cancel_wait(self._read_event)
            cancel_wait(self._write_event)
            try:
                os.close(self._master)
            except Exception:
                pass
            if not self._proc.poll():
                self._proc.terminate()
                self._proc.wait()
            self._finished.set()
