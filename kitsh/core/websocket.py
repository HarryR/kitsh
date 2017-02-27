from __future__ import print_function

import logging
import json

import gevent
from gevent.event import Event

LOG = logging.getLogger(__name__)


class Websocket(object):
    def __init__(self, websocket, readonly=False, remote=None):
        self._ws = websocket
        self._closed = Event()
        self._readonly = readonly
        self._remote = remote
        self._tasks = None

    def __repr__(self):
        return "%s @ %s" % (self.__class__.__name__, self._remote or "%x" % (id(self),))

    def run(self, task):
        assert self._tasks is None
        try:
            self._tasks = [
                gevent.spawn(self._recvloop, task),
            ]
            if not self._readonly:
                gevent.spawn(self._sendloop, task)
            self.wait()
        finally:
            self.stop()

    @property
    def closed(self):
        return self._closed.ready()

    def wait(self):
        assert self._tasks is not None
        gevent.joinall(self._tasks)

    def _recvloop(self, task):
        from geventwebsocket.exceptions import WebSocketError
        while not self.closed:
            try:
                data = self._ws.receive()
            except WebSocketError:
                LOG.exception("%r recvloop", self)
                break
            if data in (StopIteration, None):
                LOG.info("Websocket closed gracefully!")
                break                
            try:
                msg = json.loads(data)
            except ValueError:
                LOG.exception("%r recv decode error for %r", self, data)
                continue
            LOG.info("recvloop Got %r - %r", msg, len(task.input._mon))
            task.output.send(msg)
        self.stop()

    def _sendloop(self, task):
        for msg in task.input.watch():
            #LOG.info("sendloop Got %r", msg)
            if msg is StopIteration or self.closed:
                break
            try:
                self._ws.send(json.dumps(msg))
            except Exception:
                LOG.exception("%r send error for %r", self, msg)
                continue
        LOG.debug("%r sendloop finished", self)
        self.stop()

    def stop(self):
        if not self.closed:
            self._ws.close()
            self._closed.set()
            #self.bridge.close()
            LOG.debug("%r stopping", self)

    @classmethod
    def communicate(cls, websocket, bridge):
        ws2b = cls(websocket)                
        ws2b.run(bridge)
