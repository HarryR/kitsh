#!/usr/bin/env python

from kitsh.core.process import Process
from kitsh.core.task import TaskManager


def test_proc_stdout():
	task = TaskManager.spawn(Process(['ps', '-ax']))
	task.wait()
	assert len(task.output) > 0


if __name__ == "__main__":
	import logging
	logging.basicConfig()
	test_proc_stdout()
