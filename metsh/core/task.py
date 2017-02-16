# -*- coding: utf-8 -*-


import os
from base64 import b32encode
import logging

from .inout import Channel

import gevent
from gevent.event import Event


LOG = logging.getLogger(__name__)


def random_name():
    return b32encode(os.urandom(5))


def make_callable(what, names):
    if callable(what):
        return what
    for name in names:
        method = getattr(what, name, None)
        if method:
            return method
    raise ValueError("Unable to call %r" % (what,))


class Task(object):
    def __init__(self, obj, inch=None, outch=None):
        assert obj is not None
        self._obj = obj
        self.pid = random_name()
        self.input = inch or Channel()
        self.output = outch or Channel()
        self.stopped = Event()
        self.running = Event()
        self.error = Event()

    def wait(self):
        try:
            self.stopped.wait()
        except KeyboardInterrupt:
            self.stop()
            self.stopped.wait()
        return self

    def _run(self):
        make_callable(self._obj, ['run'])(self)

    @property
    def state(self):
        states = (
            (self.stopped, 'STOPPED'),
            (self.running, 'RUNNING'),
            (self.error, 'ERROR')
        )
        for event, name in states:
            if event.ready():
                return name
        return 'NEW'

    def __repr__(self):
        return "%s:%s %r" % (self.__class__.__name__, self.pid, self._obj)

    def __str__(self):
        return "%s [%s] %r" % (self.pid, self.state, self._obj)

    def stop(self):
        if self.running.ready():
            self.input.close()
            self.output.close()
            make_callable(self._obj, ['stop', 'close'])()


class TaskManager(object):
    tasks = dict()

    @classmethod
    def _run(cls, task):        
        try:
            task.running.set()
            LOG.info("RUNNING %r", task)
            task._run()
            LOG.info("STOPPED %r", task)
            task.stopped.set()
        except Exception:
            task.stopped.set()
            LOG.exception("EXCEPTION %r", task)            
            task.error.set()
        finally:
            task.stop()
        del cls.tasks[task.pid]

    @classmethod
    def start(cls, task):
        if not isinstance(task, Task):
            task = Task(task)
        if task.pid not in cls.tasks:
            cls.tasks[task.pid] = task
        if task.state == 'NEW':
            gevent.spawn(cls._run, task)
        return task

    @classmethod
    def get(cls, name):
        return cls.tasks.get(name, None)        

    @classmethod
    def list(cls):
        return cls.tasks.keys()

    @classmethod
    def stop(cls, name):
        task = cls.tasks.get(name)
        if task:
            task.close()
