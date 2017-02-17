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

    def raw_input(self, prompt=""):
        newline = '\r'
        self.write(prompt)
        while True:            
            data = self.sock.read()
            if data is StopIteration:
                break
            if newline not in data:
                self._line += data
                self.sock.write(data)
            else:
                pos = data.index(newline) + 1
                before = data[:pos]
                after = data[pos:]
                self.sock.write(before)
                self._line += before
                line = self._line[0:len(self._line)].rstrip("\r\n")
                self._line = after
                return line
        raise EOFError()

    def write(self, strdata):
        self.sock.write(strdata.replace("\n", "\r\n"))

    def run(self, bridge):
        self.sock = bridge.stdin()
        try:
            try:
                self.interact()
            except Exception:
                pass
        finally:
            self.sock.close()

    def stop(self):
        self.sock.close()
