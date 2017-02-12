import logging
import code

LOG = logging.getLogger(__name__)


class PythonConsole(code.InteractiveConsole, object):

    ident = 0  # Id of next instance; also counts instances

    def __repr__(self):
        return "Python @ %x" % (id(self),)

    def __init__(self, symtab=None):
        if symtab is None:
            symtab = dict()
        # Make exit() in the console only exit the console, not the program.
        # (There's still sys.exit().)
        symtab['exit'] = self.stop
        self._line = ''
        # TODO get the right context in here (locals)
        super(PythonConsole, self).__init__(
            filename='<Python-' + str(self) + '>',
            locals=symtab)

    def raw_input(self, prompt):
        self.write(prompt)
        empty = tuple()
        while True:
            msg = self.sock.recv()
            if msg is StopIteration:
                break
            if 'data' in msg:
                data = msg['data']
                if '\r' not in data:
                    self._line += data
                    self.sock.send(dict(data=data))
                else:
                    pos = data.index('\r') + 1
                    before = data[:pos]
                    after = data[pos:]
                    self.sock.send(dict(data=before))
                    self._line += before
                    line = self._line[0:len(self._line)].rstrip("\r\n")
                    self._line = after
                    return line
        raise EOFError()

    def write(self, strdata):
        self.sock.send(dict(data=strdata.replace("\n", "\r\n")))

    def run(self, bridge, task):
        self.sock = bridge.server_sock()
        try:
            try:
                self.interact()
            except Exception:
                pass
        finally:
            self.sock.close()

    def stop(self):
        self.sock.close()
