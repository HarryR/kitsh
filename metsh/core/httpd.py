#!/usr/bin/env python

import logging
from flask import Flask
from . import Plugin


LOG = logging.getLogger(__name__)


class Httpd(Plugin):
    def __init__(self, blueprints):
        self._blueprints = blueprints
        self._flask = None
        self._listen = None
        self._server = None

    def options(self, parser, env):
        parser.add_argument('--port', '-p',
            type=int,
            default=5000,
            help='Port to bind (default: 5000)')

        parser.add_argument('--host', '-H',
            default='0.0.0.0',
            help='Host to listen to (default: 0.0.0.0)')

    def configure(self, options, conf):
        self._listen = (options.host, options.port)

    def __repr__(self):
        return "%s%r @ http://%s:%d" % (self.__class__.__name__,
                            self._blueprints,
                             self._listen[0], int(self._listen[1]))

    def stop(self):
        self._server.stop()

    def run(self, task):
        from gevent.pywsgi import WSGIServer
        from geventwebsocket.handler import WebSocketHandler

        flask = Flask(__name__, static_folder=None)
        for blueprint in self._blueprints:
            flask.register_blueprint(blueprint)

        self._server = WSGIServer(self._listen, flask,
            log=LOG,
            handler_class=WebSocketHandler)
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            self.stop()

