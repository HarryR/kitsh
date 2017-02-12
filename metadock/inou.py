import logging
import sys

import gevent
from gevent.queue import Queue

import socket


LOG = logging.getLogger(__name__)



if sys.version_info[:2] == (2, 7):
    # Python 2.7 has a working BufferedReader but socket.makefile() does not
    # use it.
    # Python 2.6's BufferedReader is broken (TypeError: recv_into() argument
    # 1 must be pinned buffer, not bytearray).
    from io import RawIOBase, BufferedRWPair, TextIOWrapper

    class SocketIO(RawIOBase):
        def __init__(self, sock):
            RawIOBase.__init__(self)
            self._sock = sock

        def readinto(self, b):
            self._checkClosed()
            while True:
                try:
                    data = self._sock.recv()
                    msg = bytearray(data, encoding="utf-8")
                    if msg:
                        b[:len(msg)] = msg
                        return len(msg)
                except socket.error as ex:
                    if ex.args[0] == EINTR:
                        continue
                    raise

        def write(self, data):
            """Write the given bytes or bytearray object *b* to the socket
            and return the number of bytes written.  This can be less than
            len(b) if not all data could be written.  If the socket is
            non-blocking and no bytes could be written None is returned.
            """
            self._checkClosed()
            self._checkWritable()
            data = bytearray(data)
            try:
                return self._sock.send(data)
            except error as e:
                # XXX what about EINTR?
                if e.args[0] in _blocking_errnos:
                    return None
                raise

        def readable(self):
            return self._sock is not None

        def writable(self):
            return self.readable()

        @property
        def closed(self):
            return self._sock is None

        def fileno(self):
            self._checkClosed()
            return self._sock.fileno()

        def seekable(self):
            return False

        @property
        def name(self):
            if not self.closed:
                return self.fileno()
            else:
                return -1

        def close(self):
            if self._sock is None:
                return
            else:
                self._sock.close()
                self._sock = None
                RawIOBase.close(self)

    def makefile(socket):
        sio = SocketIO(socket)
        return BufferedRWPair(sio, sio)
else:
    def makefile(socket):
        # XXX on python3 enable buffering
        return socket.makefile()


class Socket(object):
    def __init__(self):
        self._sendq = Queue()
        self._recvq = Queue()
        self._closed = False

    def _checkClosed(self):
        if self._closed:
            raise RuntimeError("Socket closed")

    def inject(self, msg):
        if msg is not StopIteration:
            self._checkClosed()
            self._recvq.put(msg)

    def recv(self):
        self._checkClosed()
        return self._recvq.get()

    def send(self, msg):
        self._checkClosed()
        if msg:
            self._sendq.put(msg)
            return len(msg)
        raise RuntimeError("Invalid Message")

    def eject(self):
        return self._sendq.get()

    def close(self):
        self._closed = True
        self._sendq.put(StopIteration)
        self._recvq.put(StopIteration)


class StreamSocket(Socket):
    def __init__(self):
        super(StreamSocket, self).__init__()
        self._buf = ''

    def readline(self, newline='\r'):
        if newline in self._buf:
            pos = self._buf.index(newline)
            line = self._buf[:pos]
            self._buf = self._buf[pos:]
            print "%r %r" % (self._buf,)
            return line.rstrip(newline)
        while True:
            data = self.recv()
            if data is StopIteration:
                break
            if newline in data:
                pos = data.index(newline) + 1
                line = self._buf + data[:pos]
                self._buf = data[pos:]
                return line.rstrip(newline)
            else:
                self._buf += data

    def recv(self):
        self._checkClosed()
        while True:
            msg = self._recvq.get()
            if msg is StopIteration:
                return StopIteration
            if 'data' not in msg:
                continue
            return msg['data']

    def write(self, data):
        return self.send(data)

    def send(self, data):
        self._checkClosed()
        data = str(data)
        self._sendq.put(dict(data=data))
        return len(data)

    def makefile(self):
        return makefile(self)


class Bridge(object):
    def __init__(self):
        self._inputs = []
        self._outputs = []
        self._i2o = Queue()
        self._o2i = Queue()
        self._tasks = None
        self._start()
    
    def stop(self):
        self._o2i.put(StopIteration)
        self._i2o.put(StopIteration)

    def wait(self):
        gevent.joinall(self._tasks)

    def inject(self, msg):
        self._o2i.put(msg)

    def send(self, msg):
        self._i2o.put(msg)

    def _run_send(self, fromq, targets):
        while True:
            try:
                msg = fromq.get()
            except Exception:
                break            
            for target in targets:
                try:
                    method = target if callable(target) else getattr(target, 'send')
                    assert method is not None
                    result = method(msg)
                except Exception:
                    LOG.exception("While sending to bridge target")
            if msg is StopIteration:
                break

    def _start(self):
        if self._tasks is None:
            self._tasks = [
                gevent.spawn(self._run_send, self._i2o, self._outputs),
                gevent.spawn(self._run_send, self._o2i, self._inputs),
            ]

    def _attach(self, group, recvfn, sendfn, replyfn):
        group.append(replyfn)
        try:
            while True:
                msg = recvfn()
                if msg is StopIteration:
                    break
                if sendfn:
                    result = sendfn(msg)
                    if result is StopIteration:
                        break
        finally:
            group.remove(replyfn)

    def attach_server(self, recvfn, replyfn):
        return self._attach(self._outputs, recvfn, self.inject, replyfn)

    def attach_client(self, recvfn, replyfn):
        return self._attach(self._inputs, recvfn, self.send, replyfn)

    def server_sock(self):
        handle = Socket()
        gevent.spawn(self.attach_server, handle.eject, handle.inject)
        return handle

    def server_file(self):
        handle = StreamSocket()
        gevent.spawn(self.attach_server, handle.eject, handle.inject)
        return handle

    def client_file(self):
        handle = StreamSocket()
        gevent.spawn(self.attach_client, handle.eject, handle.inject)
        return handle
