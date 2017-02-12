#!/usr/bin/env python

from gevent import monkey
monkey.patch_all()

import sys
import logging
from flask import Flask

from .plugin import Plugin, Host


class HttpdPlugin(Plugin):
    def __init__(self, blueprints):
        self._log = logging.getLogger(__name__)
        self._blueprints = blueprints
        self._flask = None
        self._listen = None

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

    def run(self):
        from gevent.pywsgi import WSGIServer
        from geventwebsocket.handler import WebSocketHandler
        self._log.info('running on %r:%r', self._listen[0], self._listen[1])

        flask = Flask(__name__)
        for blueprint in self._blueprints:
            flask.register_blueprint(blueprint)

        http_server = WSGIServer(self._listen, flask,
            log=self._log,
            handler_class=WebSocketHandler)
        try:
            http_server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    from .frontend import FrontendBlueprint
    server = HttpdPlugin([FrontendBlueprint()])
    Host(server).main(sys.argv[1:])
