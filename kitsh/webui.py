import os
import logging

from flask import Blueprint, request, render_template, redirect
from werkzeug.exceptions import BadRequest

from .core.task import TaskManager
from .core.plugin import PluginHost
from .core.httpd import Httpd
from .core.process import Process
from .core.websocket import Websocket


LOG = logging.getLogger(__name__)


def echoproc(task):
    LOG.info("echoproc started")
    for msg in task.input.watch():
        LOG.info("echoproc got %r", msg)
        task.output.send(msg)
    LOG.info("echoproc finished")


class WebUI(Blueprint):
    def __repr__(self):
        return "WebUI"

    def __init__(self):
        root_path = os.path.dirname(__file__)
        template_folder = os.path.join(root_path, 'templates')
        static_folder = os.path.join(root_path, 'static')
        
        super(WebUI, self).__init__(
            'webui', __name__,
            template_folder=template_folder,
            static_folder=static_folder)
        self._log = logging.getLogger(__name__)

        self.add_url_rule('/', view_func=self.index)
        self.add_url_rule('/', methods=['POST'], view_func=self.view)
        self.add_url_rule('/websocket', view_func=self.websocket)

    def index(self):
        return render_template('index.html', tasks=TaskManager.tasks())

    def view(self):
        task = request.args.get('id')
        if task:
            task = TaskManager.get(task)
        if not task:
            return redirect('/')
        return render_template('view.html', session_id=task.pid)

    def websocket(self):
        try:
            sock = request.environ.get('wsgi.websocket')
            if not sock:
                self._log.error('Abort: Request is not WebSocket upgradable')
                raise BadRequest()

            remote_addr = "%s:%s" % (request.remote_addr,
                                     request.environ.get('REMOTE_PORT'))
            task = TaskManager.spawn(Websocket(sock, remote=remote_addr))
            subtask = TaskManager.spawn(Process(["id"]))
            with task.bridge(subtask) as bridge:
                bridge.wait()
            subtask.wait()
            task.stop()
            task.wait()
        except Exception:
            LOG.exception("in websocket")
        return str()


if __name__ == "__main__":    
    PluginHost.main(Httpd([WebUI()]))
