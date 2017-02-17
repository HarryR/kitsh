from kitsh.core.inout import Channel


def test_sock():
	sockA = Channel()
	sockA.send("derp")
	assert len(sockA) == 1
	assert sockA.recv() == "derp"

	with sockA.monitor() as mon:
		sockA.send("yay")
		sockA.send("poop")
		for msg in mon:
			assert len(mon) == 1
			print("sock msg is", msg)			
			assert msg == "yay"			
			sockA.close()
			break


def test_datastream():
	sockB = Channel()
	with sockB.datastream() as streamB:
		streamB.write("derp\nmerp\n")
		sockB.close()
		line = streamB.readline()
		assert line == "derp"
		assert streamB.readline() == "merp"


if __name__ == "__main__":
	test_sock()
	test_datastream()
