# -*- coding: utf-8 -*-
__all__ = ('Task', 'TaskManager')

import sys
import logging

from gevent.event import Event
from gevent.greenlet import Greenlet

from .inout import Channel


LOG = logging.getLogger(__name__)


def make_callable(what, names):
    if callable(what):
        return what
    for name in names:
        method = getattr(what, name, None)
        if method:
            return method


class _GreenletStdio(Greenlet):
    """
    A greenlet that replaces sys.std[in/out/err] while running.
    Borrowed from: https://github.com/gevent/gevent/blob/master/src/gevent/backdoor.py

    Based on gevent.backdoor, Copyright (c) 2009-2014, gevent contributors
    Based on eventlet.backdoor, Copyright (c) 2005-2006, Bob Ippolito

    https://raw.githubusercontent.com/gevent/gevent/master/LICENSE (MIT atow)
    """
    _fileobj = None
    saved = None

    def switch(self, *args, **kw):
        if self._fileobj is not None:
            self.switch_in()
        Greenlet.switch(self, *args, **kw)

    def switch_in(self, fileobj=None):
        self.saved = sys.stdin, sys.stderr, sys.stdout
        if fileobj:
            self._fileobj = fileobj
        if self._fileobj:
            sys.stdin, sys.stdout, sys.stderr = self._fileobj

    def switch_out(self):
        if self.saved:
            sys.stdin, sys.stderr, sys.stdout = self.saved
        self.saved = None

    def throw(self, *args, **kwargs):
        if self.saved is None and self._fileobj is not None:
            self.switch_in()
        Greenlet.throw(self, *args, **kwargs)

    def run(self):
        try:
            return Greenlet.run(self)
        finally:
            # Make sure to restore the originals.
            self.switch_out()


class _TaskIOBridge(object):
    def __init__(self, intask, outtask):
        self._in2out = intask.output.watch(outtask.input.send)
        self._out2in = outtask.output.watch(intask.input.send)
        self._closed = Event()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    @property
    def closed(self):
        return self._closed.ready()

    def wait(self):
        if not self.closed:
            return self._closed.wait()

    def close(self):
        if not self.closed:
            self._in2out.close()
            self._out2in.close()
            self._closed.set()


class Task(object):
    def __init__(self, run):
        assert run is not None
        self.input = Channel()
        self.output = Channel()
        self._obj = run
        self._greenlet = None
        TaskManager.register(self)

    def __nonzero__(self):
        if self._greenlet is None:
            return False
        return bool(self._greenlet)

    def __bool__(self):
        return self.__nonzero__()

    def wait(self, timeout=None):
        # XXX: before it's started, there is no _greenlet...
        self._greenlet.join(timeout=timeout)

    def start(self):
        if self.state == 'NEW':
            self._greenlet = _GreenletStdio(self._run)
            self._greenlet.start()
            return
        raise RuntimeError('Cannot start, invalid state: ' + self.state)

    def _run(self):
        method = make_callable(self._obj, ['run'])
        if not method:
            raise ValueError("Unable to run: %r" % (self._obj,))

        if self._greenlet:
            # Redirect stdio of Greenlet to Tasks channels...
            self._greenlet.switch_in((self.input, self.output, self.output))

        LOG.info("RUNNING %r", self)
        try:
            method(self)
            LOG.info("STOPPED %r", self)
        except Exception as ex:
            LOG.exception("ERROR %r", self)
            raise ex
        finally:
            TaskManager.unregister(self)

    def bridge(self, othertask):
        """
        Sends the output of this task to the input of the other task
        And the output of the other task to the input of this task
        """
        assert isinstance(othertask, Task)
        return _TaskIOBridge(self, othertask)

    @property
    def error(self):
        if self._greenlet:
            return self._greenlet.exception

    @property
    def state(self):
        if self._greenlet is None:
            return 'NEW'
        if bool(self._greenlet):
            return 'RUNNING'
        if not self._greenlet.successful():
            return 'ERROR'
        return 'STOPPED'

    def __repr__(self):
        return "%s:%x %r" % (self.__class__.__name__, id(self), self._obj)

    def __str__(self):
        return "%x [%s] %r" % (id(self), self.state, self._obj)

    def stop(self):
        if self.state == 'RUNNING':
            self.input.close()
            self.output.close()
            stop_fn = make_callable(self._obj, ['stop', 'close'])
            if stop_fn:
                stop_fn()


class TaskManager(object):
    _tasks = dict()

    @classmethod
    def count(cls):
        return len(cls._tasks)

    @classmethod
    def tasks(cls):
        return cls._tasks

    @classmethod
    def spawn(cls, obj):
        task = Task(obj)
        task.start()
        return task

    @classmethod
    def register(cls, task):
        assert isinstance(task, Task)
        if id(task) not in cls._tasks:
            cls._tasks[id(task)] = task

    @classmethod
    def unregister(cls, task):
        assert isinstance(task, Task)
        if id(task) in cls._tasks:
            del cls._tasks[id(task)]

    @classmethod
    def get(cls, name):
        return cls._tasks.get(name, None)

    @classmethod
    def list(cls):
        return cls._tasks.keys()

    @classmethod
    def stop(cls, name):
        task = cls._tasks.get(name)
        if task:
            task.stop()

    @classmethod
    def stopall(cls):
        for task in cls._tasks.itervalues():
            task.stop()
