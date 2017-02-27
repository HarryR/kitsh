import argparse
import sys
import socket
import signal
import errno

import websocket
import select

import termios
import tty
import fcntl
import platform
import struct

try:
    import json
except ImportError:
    import simplejson as json


class ConnectionError(Exception):
    pass


def _pty_size():
    rows, cols = 24, 80
    # Can't do much for Windows
    if platform.system() == 'Windows':
        return rows, cols
    fmt = 'HH'
    buffer = struct.pack(fmt, 0, 0)
    result = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ,
        buffer)
    rows, cols = struct.unpack(fmt, result)
    return rows, cols


def _resize(ws):
    rows, cols = _pty_size()
    ws.send(json.dumps({'resize': {'width': cols, 'height': rows}}))


def invoke_shell(endpoint):
    try:
        ssh = websocket.create_connection(endpoint)
    except socket.error as ex:
        print >>sys.stderr, "error connecting to %s" % (endpoint,)
        print >>sys.stderr, " - " + str(ex)
        return
    _resize(ssh)
    oldtty = termios.tcgetattr(sys.stdin)
    old_handler = signal.getsignal(signal.SIGWINCH)

    def on_term_resize(signum, frame):
        _resize(ssh)
    signal.signal(signal.SIGWINCH, on_term_resize)

    try:
        #tty.setraw(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())

        rows, cols = _pty_size()
        ssh.send(json.dumps({'resize': {'width': cols, 'height': rows}}))

        while True:
            try:
                r, w, e = select.select([ssh.sock, sys.stdin], [], [])
                if ssh.sock in r:
                    data = ssh.recv()
                    if not data:
                        break
                    message = json.loads(data)
                    if 'error' in message:
                        raise ConnectionError(message['error'])
                    if 'data' in message:
                        sys.stdout.write(message['data'])
                    sys.stdout.flush()
                if sys.stdin in r:
                    x = sys.stdin.read(1)
                    if len(x) == 0:
                        break
                    ssh.send(json.dumps({'data': x}))
            except (select.error, IOError) as e:
                if e.args and e.args[0] == errno.EINTR:
                    pass
                else:
                    raise
    except websocket.WebSocketException:
        raise
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)
        signal.signal(signal.SIGWINCH, old_handler)


def main():
    parser = argparse.ArgumentParser(
        description='MetaDock - SSH Client')

    parser.add_argument('--host', '-H',
        help='MetaDock server host (default: 127.0.0.1)',
        default='127.0.0.1')

    parser.add_argument('--port', '-P',
        help='MetaDock server port (default: 5000)',
        type=int,
        default=5000)

    args = parser.parse_args()
    endpoint = 'ws://{host}:{port}/websocket'.format(**vars(args))

    try:
        invoke_shell(endpoint)
    except ConnectionError as e:
        print >>sys.stderr, 'client: {0}'.format(e.message or 'Connection error')
    else:
        print >>sys.stderr, 'client: Connection to {0} closed.'.format(args.host)


if __name__ == "__main__":
    main()
