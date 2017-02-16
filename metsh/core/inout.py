from __future__ import print_function

import logging
from sets import Set

import gevent
from gevent.queue import Queue
from gevent.event import Event

__all__ = ('Channel',)


LOG = logging.getLogger(__name__)


class Monitor(object):
    __slots__ = ('_sock', '_queue', 'closed', '_closed', '_replyfn')

    def __init__(self, sock, replyfn=None):
        assert replyfn is None or callable(replyfn)
        self._sock = sock
        self._replyfn = replyfn
        self._queue = Queue()
        self._closed = Event()
        self._sock._mon.add(self)

    def __len__(self):
        return self._queue.qsize()

    @property
    def closed(self):
        return self._closed.ready()

    def __call__(self, msg):
        try:
            if self._replyfn:
                self.replyfn(msg)
        finally:
            self._queue.put_nowait(msg)

    def __enter__(self):
        return self

    def __del__(self):
        self.detach()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.detach()

    def __iter__(self):
        while not self._sock.closed:
            msg = self._queue.get()
            if msg is StopIteration:
                break
            yield msg

    def detach(self):
        if not self.closed:
            self._sock._mon.discard(self)
            self._queue.put(StopIteration)
            self._closed.set()


class Channel(object):
    __slots__ = ('_recvq', '_closed', '_mon', '_task')

    def __init__(self):
        self._mon = Set()
        self._recvq = Queue()
        self._closed = Event()
        self._task = gevent.spawn(self._recvloop)

    def __len__(self):
        return self._recvq.qsize()

    def __repr__(self):
        return "<%s:%x>" % (self.__class__, id(self))

    def __iter__(self):
        for msg in self.monitor():
            yield msg

    def __call__(self, *msg_list):
        self.send(*msg_list)

    def send(self, *msg_list):
        for msg in msg_list:
            self._recvq.put_nowait(msg)

    def monitor(self, replyfn=None):
        return Monitor(self, replyfn=replyfn)

    def recv(self):
        """
        Receive the next message in sequence for this queue.
        Block until message is ready.
        If multiple threads call .recv() each message will only be delivered
        to one thread.
        """
        msg = self._recvq.get()
        for monitorfn in self._mon:
            monitorfn(msg)
        if msg is not StopIteration:
            return msg

    def _recvloop(self):
        while not self.closed:
            self.recv()
        self._closed.set()

    @property
    def closed(self):
        return self._closed.ready()

    def close(self):
        if not self.closed:
            self._recvq.put_nowait(StopIteration)

    def datastream(self):
        return DataStreamChannel(self)


class DataStreamChannel(object):
    __slots__ = ('_buf', '_sock', '_mon')

    def __init__(self, sock):
        self._buf = ''
        self._sock = sock
        self._mon = sock.monitor()

    def __len__(self):
        return len(self._buf)

    def readline(self, newline='\n'):
        if newline in self._buf:
            pos = self._buf.index(newline)
            line = self._buf[:pos]
            self._buf = self._buf[pos:]
            return line.rstrip(newline)

        for data in self.__iter__():
            if newline in data:
                pos = data.index(newline) + 1
                line = self._buf + data[:pos]
                self._buf = data[pos:]
                return line.rstrip(newline)
            else:
                self._buf += data

    def __iter__(self):
        while not self._sock.closed:
            yield self.read()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._mon.detach()

    def write(self, data):
        self._sock.send(dict(data=data))

    def read(self, maxbytes=None):
        for msg in self._mon:
            if 'data' not in msg:
                continue
            data = msg['data']
            if maxbytes is None:
                return data
            self._buf += data
            if len(self._buf) >= maxbytes:
                retval = self._buf[:maxbytes]
                self._buf = self._buf[maxbytes:]
                return retval
        raise StopIteration
