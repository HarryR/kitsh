from __future__ import print_function

import logging

from gevent.queue import Queue
from gevent.event import Event

__all__ = ('Channel', 'Subscriber', 'Publisher', 'DataStream')


LOG = logging.getLogger(__name__)


class Subscriber(object):
    __slots__ = ('_pub', '_queue', '_closed', '_replyfn')

    def __init__(self, pub):
        assert isinstance(pub, Publisher)
        self._pub = pub
        self._queue = Queue()
        self._closed = Event()
        pub.attach(self)

    def __len__(self):
        if self._queue:
            return self._queue.qsize()

    def __call__(self, msg):
        return self.send(msg)

    def __enter__(self):
        return self

    def __del__(self):
        self.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __iter__(self):
        if not self.closed:
            while self._queue is not None:
                msg = self.recv()
                if msg is None:
                    break
                yield msg

    def recv(self):
        if self._queue:
            msg = self._queue.get()
            if msg is StopIteration:
                self._queue = None
                self.close()
                return None
            return msg

    def send(self, msg):
        if self.closed:
            # XXX: raise better exception
            raise RuntimeError("Closed")
        if msg is StopIteration:
            return self.close()
        self._queue.put_nowait(msg)

    @property
    def closed(self):
        return self._closed.ready() and self._queue is None

    def close(self):
        if self._queue is not None:
            self._queue.put(StopIteration)
        if not self.closed:
            self._pub.detach(self)
            self._closed.set()

    def datastream(self):
        return DataStream(self)


class Publisher(object):
    __slots__ = ('_subs',)

    def __init__(self):
        self._subs = set()

    def __len__(self):
        return len(self._subs)

    def __del__(self):
        self.close()

    def subscribe(self):
        return Subscriber(self)

    def attach(self, receiverfn):
        self._subs.add(receiverfn)

    def detach(self, receiverfn):
        self._subs.discard(receiverfn)

    def send(self, msg):
        for receiverfn in self._subs.copy():
            receiverfn(msg)

    def close(self):
        self.send(StopIteration)


class Channel(object):
    __slots__ = ('_recvq', '_closed', '_mon')

    def __init__(self):
        self._mon = Publisher()
        self._recvq = Queue()
        self._closed = Event()

    def __iter__(self):
        while not self.closed:
            msg = self.recv()
            if msg is StopIteration:
                break
            yield msg

    def __len__(self):
        """
        Number of messages in buffer which haven't been delivered to watchers
        """
        return self._recvq.qsize()

    def __del__(self):
        self.close()

    def send(self, msg):
        self._recvq.put_nowait(msg)
        if len(self._mon):
            self.recv()

    def watch(self):
        was_first = len(self._mon) == 0
        subscriber = self._mon.subscribe()
        if was_first:
            self._recvall()
        return subscriber

    def _recvall(self):
        while self._recvq.qsize():
            self.recv()

    def write(self, data):
        self.send(dict(data=data))

    def recv(self):
        if self.closed:
            # XXX: raise better exception
            raise RuntimeError("Closed")
        msg = self._recvq.get()
        self._mon.send(msg)
        if msg is StopIteration:
            self._closed.set()
        return msg

    def wait(self):
        return self._closed.wait()

    @property
    def closed(self):
        return self._closed.ready()

    def close(self):
        if not self.closed:
            self.send(StopIteration)

    def datastream(self):
        return DataStream(self)


class DataStream(object):
    __slots__ = ('_buf', '_sock')

    def __init__(self, sock):
        self._buf = ''
        self._sock = sock

    def __len__(self):
        return len(self._buf)

    def readline(self, newline='\n'):
        if newline in self._buf:
            pos = self._buf.index(newline)
            line = self._buf[:pos]
            self._buf = self._buf[pos:]
            return line.rstrip(newline)

        for data in self:
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
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        self._sock = None

    def write(self, data):
        self._sock.send(dict(data=data))

    def read(self, maxbytes=None):
        for msg in self._sock:
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
