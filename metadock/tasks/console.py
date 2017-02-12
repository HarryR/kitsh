import json
import logging

import gevent
from gevent.queue import Queue

LOG = logging.getLogger(__name__)


class ConsoleTask(object):
    """
    Allows for a single server socket to be connected to via multiple websocket
    Everything received from websockets is sent to server, everything received
    from server is sent to websockets, the input of each websocket isn't sent
    to other websockets.

    TL;DR - allows multiple people to view & interract with a single session,
    kinda like a PTY that you can re-attach to.
    """

    BUFFER_SIZE = 512   # Maximum size of a single read
    MAX_BUFFERS = 25    # Maximum number of buffer entries to store
    SCREEN_WIDTH = 80
    SCREEN_HEIGHT = 24

    def __repr__(self):
        return "Console @ %x" % (id(self),)

    def run(self, bridge, task):
        from io import BlockingIOError, TextIOWrapper
        infile = bridge.server_file()
        infile.write(u"Hello\n")
        LOG.info("Console ready")
        while True:
            line = infile.readline()
            if not line:
                LOG.warning("Console got None!")
                break
            LOG.info("Got line %r", line)
            infile.write(line + "\r\n")
            if line == 'x':
                break
        LOG.info("Console Finished")
        infile.close()