import os
import logging

from flask import Blueprint, request, render_template, redirect
from werkzeug.exceptions import BadRequest

from .core import TaskManager, PluginHost, Httpd
from .cmd.websocket import Websocket


class WebUI(Blueprint):
    def __repr__(self):
        return "WebUI"

    def __init__(self, *args, **kwargs):
        
        root_path = os.path.dirname(__file__)
        template_folder = os.path.join(root_path, 'templates')
        static_folder = os.path.join(root_path, 'static')
        print("TEMPLATES", template_folder)
        print("STATIC", static_folder)
        
        super(WebUI, self).__init__(
            'webui', __name__,
            template_folder=template_folder,
            static_folder=static_folder)
        self._log = logging.getLogger(__name__)

        @self.route('/')
        def index():
            return render_template('index.html', tasks=TaskManager.tasks)

        @self.route('/console', methods=['GET'])
        def console():
            task = request.args.get('id')        
            if task:
                task = TaskManager.get(task)
            if not task:
                return redirect('/')
            return render_template('view.html', session_id=task.pid)

        @self.route('/websocket')
        def websocket():
            websocket = request.environ.get('wsgi.websocket')
            if not websocket:
                self._log.error('Abort: Request is not WebSocket upgradable')
                raise BadRequest()

            remote_addr = "%s:%s" % (request.remote_addr,
                                     request.environ.get('REMOTE_PORT'))
            task = TaskManager.start(Websocket(websocket, remote=remote_addr))
            task.wait()
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

if __name__ == "__main__":
    import sys
    HOST = PluginHost(Httpd([WebUI()]), sys.argv[1:])
    HOST.start().wait().stop()
