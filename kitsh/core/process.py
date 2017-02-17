from __future__ import print_function

import os
import pty
from subprocess import PIPE, Popen
from select import select


class Process(object):
	def __init__(self, args, env=None, executable=None, shell=False):
		master, slave = pty.openpty()
		self._master = os.fdopen(master)
		self._slave = os.fdopen(slave)
		self._args = args
		self._ret = None
		self._proc = Popen(
			args, env=env, executable=executable, shell=shell,
			stdin=self._master, stdout=PIPE, stderr=PIPE, bufsize=0,
			universal_newlines=True)

	def __repr__(self):
		return "Process %r %r" % (self._args, self._ret)

	def send(self, msg):
		if 'data' in msg:
			print("Process Recvd")
			self._master.write(data['msg'])

	def run(self, task):
		with task.input.monitor(self.send):
			proc = self._proc
			readable = [proc.stdout, proc.stderr]
			while len(readable):
				rs, ws, es = select(readable, [], readable)
				for sock in rs:
					data = sock.read()
					if not data or data is StopIteration:
						#self.stop()
						#readable = []
						readable.remove(sock)
						break
					if sock in (proc.stdout, proc.stderr):
						task.output.send(data=data)
					elif sock in (self._master):
						self._slave.write(data)
			self._ret = self._proc.wait()
			return self._ret

	def stop(self):
		print(self._master)
		print(self._slave)
		self._master.close()
		self._slave.close()
		self._proc.stdout.close()
		self._proc.stderr.close()
