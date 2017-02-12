# -*- coding: utf-8 -*-


import os
from base64 import b32encode
import logging

from .inou import Bridge

import gevent
from gevent.event import Event


LOG = logging.getLogger(__name__)


def random_name():
    return b32encode(os.urandom(10))


class Task(object):
    def __init__(self, function=None):
        self.pid = random_name()
        self.bridge = Bridge()
        self._func = function
        self.stopped = Event()
        self.running = Event()
        self.error = Event()

    def _run(self):
        if self._func:            
            if callable(self._func):
                method = self._func
            elif hasattr(self._func, 'run'):
                method = self._func.run
            method(self.bridge, self)
        else:
            raise NotImplementedError("")

    def _target(self):
        if not self._func:
            return self
        return self._func

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
        return "<Task:%s:%r>" % (self.pid, self._target())

    def __str__(self):
        return "%s [%s] %r" % (self.pid, self.state, self._target())

    def stop(self):
        if self.running.ready():
            self.bridge.stop()
            for name in ['close', 'stop']:
                method = getattr(self._func, name, None)
                if method:
                    method()


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
