import argparse
import logging
import logging.config
import os
import sys
from fcntl import flock, LOCK_EX, LOCK_UN, LOCK_NB

__all__ = ('Plugin', 'Host', 'Loader')


class ArgumentParser(argparse.ArgumentParser):
    """
    Plugin-friendly argument parser that doesn't sys.exit()...
    """
    def _get_action_from_name(self, name):
        """
        Given a name, get the Action instance registered with this parser.
        If only it were made available in the ArgumentError object. It is
        passed as it's first arg...
        """
        container = self._actions
        if name is None:
            return None
        for action in container:
            if '/'.join(action.option_strings) == name:
                return action
            elif action.metavar == name:
                return action
            elif action.dest == name:
                return action

    def exit(self, status=0, message=None):
        raise SystemExit(message)

    def error(self, message):
        exc = sys.exc_info()[1]
        if exc:
            exc.argument = self._get_action_from_name(exc.argument_name)
            raise exc


class Plugin(object):
    """
    Provides an interface to validate options and initialise its self
    similar to: http://nose.readthedocs.org/en/latest/plugins/writing.html
    """
    __slots__ = ()

    def options(self, parser, env):
        """
        Add additional program options to the parser

        :type parser: ArgumentParser
        :param env dict: Envoronment options
        """
        pass

    def configure(self, options, conf):
        """
        Add additional program options to the parser

        :type parser: ArgumentParser
        :param env dict: Other configuration flags
        """
        pass

    def run(self):
        """
        Invoke whichever action the plugin needs to perform.
        """
        pass


def str_to_class(module_name, class_name):
    """
    :returns: class for "package.module.Class" etc.
    """
    import importlib
    class_ = None
    try:
        module_ = importlib.import_module(module_name)
        try:
            class_ = getattr(module_, class_name)
        except AttributeError:
            logging.error('Class %s does not exist in %s',
                          class_name, module_name)
    except ImportError:
        logging.error('Module does not exist')
    return class_ or None


def _modname(cls, full=False):
    """
    Full module name, avoids using '__main__' unless necessary
    """
    module = cls.__module__
    if module is None or module == str.__class__.__module__:
        return cls.__name__
    if full and module == "__main__":
        import inspect
        the_module = inspect.getmodule(cls)
        spec = getattr(the_module, '__spec__', None)
        if spec is None:
            if the_module.__name__ == '__main__':
                module = '.'.join([the_module.__package__,
                                   os.path.basename(the_module.__file__.split('.')[0])])
            else:
                module = getattr(the_module, '__package__', None)
        else:
            module = spec.name if spec else module
        return module
    return module + '.' + cls.__class__.__name__


def _fullname(obj):
    """
    Full module name of a class
    """
    if obj is None:
        return None
    return _modname(obj, True)


class Host(Plugin):
    """
    Utility class that provides a standard way of
    hosting services as system process.

      * Command line parsing
      * Logging configuration
      * Pid file management
    """
    __slots__ = ('_plugin', '_options', '_pidfile', '_log')

    def __init__(self, plugin_obj):
        assert plugin_obj is not None
        assert not isinstance(plugin_obj, self.__class__)
        self._log = logging.getLogger()
        self._pidfile = None
        self._plugin = plugin_obj
        self._options = None

    def options(self, parser, env):
        """
        After the ArgumentParser has been constructed in __init__
        the callee of the daemon will call `parse_args` with the
        daemon arguments.
        """
        plugin_name = _fullname(self._plugin)
        parser.add_argument(
            '-0', '--name', metavar="name", dest='name',
            default=plugin_name, help='hange process name to this')
        parser.add_argument('-v', '--verbose', action='store_const',
                        dest="loglevel", const=logging.INFO,
                        help="Log informational messages")
        parser.add_argument('--debug', action='store_const', dest="loglevel",
                            const=logging.DEBUG, default=logging.WARNING,
                            help="Log debugging messages")
        parser.add_argument(
            '-L', '--log-config', metavar="filename", dest='logconfig',
            default=env.get('LOGGING_CONF'),
            type=argparse.FileType('r'), help='ogging configuration file')
        parser.add_argument(
            '-P', '--pid', dest='pidfile', metavar="filename", nargs='?')
        self._plugin.options(parser, env)

    def configure(self, options, conf):
        assert options is not None
        self._options = options
        if options.logconfig:
            logging.config.fileConfig(options.logconfig)
            self._log = logging.getLogger(_fullname(self._plugin))
        else:
            logging.basicConfig(
                level=options.loglevel,
                format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                datefmt='%Y-%m-%d %H:%M')
        try:
            from setproctitle import setproctitle
            setproctitle(options.name)
        except ImportError:
            self._log.debug("Process name unchanged, no setproctitle")
        self._setup_pidfile(options)
        if self._plugin:
            self._plugin.configure(options, conf)

    def _delpid(self):
        """
        Unlock and remove pid file.
        """
        pidfile = self._pidfile
        if pidfile is not None:
            self._log.debug('Removing pidfile: %s (%d)',
                            pidfile.name, os.getpid())
            flock(pidfile, LOCK_UN)
            pidfile.close()
            os.remove(pidfile.name)
            self._pidfile = None

    def _setup_pidfile(self, options):
        """
        Create a file containing the pid and lock it.
        """
        if options.pidfile:
            pidfile = open(options.pidfile, "w")
            pid = str(os.getpid())
            try:
                flock(pidfile, LOCK_EX | LOCK_NB)
            except IOError as ex:
                pidfile.close()
                self._log.error('Cannot lock pidfile!')
                raise ex
            self._log.info('Writing pidfile: %s (%s)', pidfile.name, pid)
            pidfile.write("%s\n" % (pid,))
            pidfile.flush()
            self._pidfile = pidfile

    def run(self):
        return self._plugin.run()

    def main(self, args=None):
        """
        Construct and run the daemon, usually from __main__

        This is the preferred way of running plugins.
        """
        if args is None:
            args = sys.argv[1:]
        assert len(args) >= 0
        plugin_name = _fullname(self._plugin)
        parser = ArgumentParser(prog=plugin_name)
        self.options(parser, {})
        retval = None
        try:
            options = parser.parse_args(args)
            try:
                self.configure(options, {})
                retval = self.run()
            except Exception:
                self._log.exception("Failed to run!")
        except SystemExit:
            pass
        self._delpid()
        return retval


class WaitForever(Plugin):
    """
    Sleeps until interrupted
    """
    def run(self):
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


class Loader(Plugin):
    """
    Loads a dotted class name and runs with arguments
    """
    _plugin = None
    _args = None

    def __init__(self):
        pass

    def options(self, parser, env):
        parser.add_argument('mod_name', metavar='name',
                            nargs=1, help="Full module path")
        parser.add_argument('args', nargs=argparse.REMAINDER,
                            help="Command-line arguments")

    def configure(self, options, conf):
        if not getattr(options, 'mod_name', None):
            raise RuntimeError('No mod name specified!')
        assert len(options.mod_name)
        name = options.mod_name[0]
        parts = name.split('.')
        if len(parts) < 2:
            raise RuntimeError('Must specify class name')
        cls = str_to_class('.'.join(parts[0:-1]), parts[-1])
        if cls is None or not hasattr(cls, 'run'):
            logging.debug("Could not load plugin: %r", cls)
            raise RuntimeError("Not a Plugin class: %s" % (cls,))        
        logging.debug('Loaded %s', cls)
        self._plugin = cls()
        self._args = options.args

    def run(self):
        return Host(self._plugin).main(self._args)

if __name__ == "__main__":
    Host(Loader()).main(sys.argv[1:])
