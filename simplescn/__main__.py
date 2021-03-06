#! /usr/bin/env python3

"""
start file for simplescn
license: MIT, see LICENSE.txt
"""

import sys
import os
import logging
import threading
import signal
import json

# don't load different module
if __name__ == "__main__":
    ownpath = os.path.dirname(os.path.realpath(__file__))
    sys.path.insert(0, os.path.dirname(ownpath))

from simplescn import config, running_instances
from simplescn._common import scnparse_args, loglevel_converter

def _signal_handler(_signal, frame):
    """ handles signals; shutdown properly """
    for elem in running_instances:
        elem.quit()
    logging.shutdown()
    sys.exit(0)

_is_init_already = False
def _init_scn():
    """ initialize once and only in mainthread """
    global _is_init_already
    if not _is_init_already and threading.current_thread() == threading.main_thread():
        _is_init_already = True
        logging.basicConfig(level=loglevel_converter(config.default_loglevel), format=config.logformat)
        signal.signal(signal.SIGINT, _signal_handler)

def server(argv=sys.argv[1:], doreturn=False):
    """ start server component """
    _init_scn()
    from simplescn.server import server_paramhelp, default_server_args, server_init
    kwargs = scnparse_args(argv, server_paramhelp, default_server_args)
    os.makedirs(kwargs["config"], 0o750, True)
    server_instance = server_init.create(**kwargs)
    if doreturn or not server_instance:
        return server_instance
    else:
        running_instances.append(server_instance)
        print(json.dumps(server_instance.show()))
        server_instance.join()

def client(argv=sys.argv[1:], doreturn=False):
    """ client """
    _init_scn()
    from simplescn.client import client_paramhelp, default_client_args, client_init
    kwargs = scnparse_args(argv, client_paramhelp, default_client_args)
    os.makedirs(kwargs["config"], 0o750, True)
    client_instance = client_init.create(**kwargs)
    if doreturn or not client_instance:
        return client_instance
    else:
        running_instances.append(client_instance)
        print(json.dumps(client_instance.show()))
        client_instance.join()

def hashpw(argv=sys.argv[1:]):
    """ create pw hash for *pwhash """
    _init_scn()
    from simplescn.tools import dhash
    import base64
    if len(sys.argv) < 2 or sys.argv[1] in ["--help", "help"]:
        print("Usage: {} hashpw <pw>/\"random\"".format(sys.argv[0]))
        return
    pw = argv[0]
    if pw == "random":
        pw = str(base64.urlsafe_b64encode(os.urandom(10)), "utf-8")
    print("pw: {}, hash: {}".format(pw, dhash(pw)))

def cmdcom(argv=sys.argv[1:]):
    """ wrapper for cmdcom """
    from simplescn.cmdcom import _init_method_main as init_cmdcom
    return init_cmdcom(argv)

def cmd_massimport(argv=sys.argv[1:]):
    """ wrapper for cmdmassimport """
    from simplescn.massimport import cmdmassimport
    return cmdmassimport(argv)


def _init_method_main(argv=sys.argv[1:]):
    """ starter method """
    if len(argv) > 0:
        toexe = globals().get(argv[0].strip("_"), None)
        if callable(toexe):
            toexe(argv[1:])
        else:
            print("Not available", file=sys.stderr)
            print("Available: client, server, hashpw, cmdcom, cmd_massimport", file=sys.stderr)
    else:
        print("Available: client, server, hashpw, cmdcom, cmd_massimport", file=sys.stderr)

if __name__ == "__main__":
    _init_method_main()
