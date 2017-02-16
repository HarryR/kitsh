import logging

LOG = logging.getLogger(__name__)


class ConsoleTask(object):
    def __repr__(self):
        return "Console @ %x" % (id(self),)

    def run(self, bridge):
        sock = bridge.stdin()
        sock.write("{%shell begin %}")
        while True:
            sock.write(u"> ")
            line = sock.readline()
            if not line:
                break
            sock.write(line + "\r\n")
            if line == 'exit':
                break
        sock.write("{%shell end %}")
        LOG.info("Console Finished")
