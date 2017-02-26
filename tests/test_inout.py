#!/usr/bin/env python

from kitsh.core.inout import Channel, DataStream


def test_channel():
	chan = Channel()
	chan.send("derp")
	assert len(chan) == 1
	assert chan.recv() == "derp"

	chan.send("yay")
	chan.send("poop")
	for msg in chan:
		assert len(chan) == 1
		assert msg == "yay"
		chan.close()
		break


def test_datastream():
	sockB = Channel()
	with DataStream(sockB) as streamB:
		streamB.write("derp\nmer")
		streamB.write("p\nyay\n")
		sockB.close()
		streamB.readline() == "derp"
		streamB.readline() == "merp"
		streamB.readline() == "yay"


# TODO: test DataStream.read(), where maxbytes != None


def test_subscribe():
	chan = Channel()

	chan.send("test0")
	assert len(chan) == 1

	with chan.watch() as sub:
		assert len(sub) == 1
		assert sub.recv() == "test0"

		assert len(sub) == 0
		chan.send("test1")

		# Only then will the subscriber receive the message
		assert len(sub) == 1
		assert sub.recv() == "test1"
		assert len(sub) == 0

		chan.send("test2")
		assert len(sub) == 1
		for msg in sub:
			assert msg == "test2"
			chan.close()


if __name__ == "__main__":
	test_channel()
	test_datastream()
	test_subscribe()
