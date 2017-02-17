import paramiko
from paramiko import PasswordRequiredException
from paramiko.dsskey import DSSKey
from paramiko.rsakey import RSAKey
from paramiko.ssh_exception import SSHException

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


class SSHTask(object):
    __slots__ = ('_ssh', '_command', '_term', '_title')
    """ WebSocket to SSH Bridge Server """

    def __init__(self, hostname, port=22, username=None, password=None,
                    private_key=None, key_passphrase=None, allow_agent=False,
                    timeout=None, command=None, term='xterm'):
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(
            paramiko.AutoAddPolicy())
        self._command = command
        self._term = term
        self._title = "%s@%s:%d" % (username, hostname, port)

        pkey = None
        if private_key:
            pkey = self._load_private_key(private_key, key_passphrase)
        self._ssh.connect(
            hostname=hostname,
            port=port,
            username=username,
            password=password,
            pkey=pkey,
            timeout=timeout,
            allow_agent=allow_agent,
            look_for_keys=False)

    def __str__(self):
        return "<SSH %s>" % (self._title)

    def _load_private_key(self, private_key, passphrase=None):
        """ Load a SSH private key (DSA or RSA) from a string

        The private key may be encrypted. In that case, a passphrase
        must be supplied.
        """
        key = None
        last_exception = None
        for pkey_class in (RSAKey, DSSKey):
            try:
                key = pkey_class.from_private_key(StringIO(private_key),
                    passphrase)
            except PasswordRequiredException as e:
                # The key file is encrypted and no passphrase was provided.
                # There's no point to continue trying
                raise
            except SSHException as e:
                last_exception = e
                continue
            else:
                break
        if key is None and last_exception:
            raise last_exception
        return key

    def close(self):
        self._ssh.close()

    def _write(self, msg):
        if 'data' in msg:
            return msg['data']

    def _read(self, data):
        return dict(data=data)

    def run(self, bridge):
        if self._command:
            session = self._ssh.get_transport().open_session()
            session.get_pty(self._term)
            session.exec_command(self._command)
        else:
            session = self._ssh.invoke_shell(self._term)

        return bridge.attach_server(session, encode=self._read, decode=self._write)
