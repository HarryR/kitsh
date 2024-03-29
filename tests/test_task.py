#!/usr/bin/env python
from __future__ import print_function

from kitsh.core.task import TaskManager
from gevent.event import Event


def test_stdio():
	"""
	Verifies that stdout is redirected to tasks Output channel
	"""
	def printer(task):
		print("Derp")
		print("Merp")
	task = TaskManager.spawn(printer)
	with task.output.datastream() as stream:
		assert stream.readline() == "Derp"
		assert stream.readline() == "Merp"
	task.wait()


class Receiver(object):
	def __init__(self, sig):
		self.sig = sig

	def run(self, task):
		assert task.state != 'NEW'
		msg = task.input.recv()
		assert msg == "STEP1"
		task.output.send("STEP2")
		self.sig.set()


class Sender(object):
	def __init__(self, sig):
		self.sig = sig

	def run(self, task):
		task.output.send("STEP1")
		msg = task.input.recv()
		assert msg == "STEP2"
		self.sig.set()


def test_bridge():
	rsig = Event()
	ssig = Event()

	receiver = TaskManager.spawn(Receiver(rsig))
	sender = TaskManager.spawn(Sender(ssig))
	with receiver.bridge(sender) as bridge:
		assert TaskManager.count() == 2
		# Wait for tasks to finish
		receiver.wait()
		sender.wait()

	# An ensure they set the flags correctly
	assert rsig.ready()
	assert ssig.ready()

	assert TaskManager.count() == 0


if __name__ == "__main__":
	import logging
	logging.basicConfig()
	test_stdio()
	test_bridge()
