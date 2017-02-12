import os
import logging
from flask import Blueprint, request, render_template, redirect, Markup
from werkzeug.exceptions import BadRequest, NotFound
import jinja2

from .task import TaskManager
import json


LOG = logging.getLogger(__name__)


def _websocket_recv(websocket):
    data = websocket.receive()
    if data is StopIteration or data is None:
        return StopIteration
    try:
        return json.loads(data)
    except Exception:
        LOG.exception("While decoding from client: %r", data)


def _websocket_send(websocket, msg):
    if msg is StopIteration or msg is None:
        websocket.send(json.dumps(dict(close=True)))
        websocket.close()
        return
    websocket.send(json.dumps(msg))



class FrontendBlueprint(Blueprint):
    def __init__(self, *args, **kwargs):
        self._log = logging.getLogger(__name__)
        template_folder = root_path = os.path.dirname(__file__)
        super(FrontendBlueprint, self).__init__('frontend', __name__, template_folder=template_folder)

        self.static_folder = os.path.join(root_path, 'static')

        @self.route('/')
        def index():
            return render_template('index.html', tasks=TaskManager.tasks)

        @self.route('/console', methods=['GET', 'POST'])
        def console():
            task_id = request.args.get('id')
            if task_id:
                task = TaskManager.get(task_id)
            else:
                from .tasks.console import ConsoleTask
                task = TaskManager.start(ConsoleTask())
            if task is None:
                return redirect("/")
            return render_template('view.html', session_id=task.pid)

        def _websocket_communicate(bridge):
            assert bridge is not None
            # Abort if this is not a websocket request
            websocket = request.environ.get('wsgi.websocket')
            if not websocket:
                self._log.error('Abort: Request is not WebSocket upgradable')
                raise BadRequest()
            self._log.info("WEBSOCKET connect: %r", request.remote_addr)
            try:
                bridge.attach_client(
                    lambda: _websocket_recv(websocket),
                    lambda x: _websocket_send(websocket, x))
            except Exception:
                self._log.exception("WEBSOCKET error: %r", request.remote_addr)
                raise
            finally:
                websocket.close()            
            self._log.info("WEBSOCKET disconnect: %r", request.remote_addr)

        @self.route('/websocket')
        def websocket():
            task_id = request.args.get('id', None)
            if task_id:
                task = TaskManager.get(task_id)
                if not task:
                    raise NotFound("Unknown task")
            else:
                from .tasks.python import PythonConsole
                from .tasks.console import ConsoleTask
                task = TaskManager.start(PythonConsole())
            try:
                _websocket_communicate(task.bridge)
            finally:
                task.stop()
            return str()

"""
        @self.route('/start/ssh', methods=['POST'])
        def start_ssh():
            from .tasks.ssh import SSHTask
            remote = request.remote_addr
            username = request.form['username']
            hostname = request.form['hostname']
            command = request.form.get('run')

            self._log.debug('{remote} -> {username}@{hostname}: {command}'.format(
                    remote=remote,
                    username=username,
                    hostname=hostname,
                    command=command,
                ))

            try:
                ssh = SSHTask(
                    hostname=hostname,
                    username=username,
                    password=request.form.get('password'),
                    command=command,
                    port=int(request.form.get('port')),
                    private_key=request.form.get('private_key'),
                    key_passphrase=request.form.get('key_passphrase'))
            except Exception as e:
                msg = 'Error while connecting to {0}: {1}'.format(
                    hostname, e.message)
                self._log.exception(msg)
                return str(msg)

            task = TaskManager.start(ssh)
            return redirect('/watch/' + task.pid)
"""