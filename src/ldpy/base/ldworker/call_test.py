#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import logging
import os
import sys
from typing import Any, Callable, Dict, Optional, Tuple

from .. import ldlog

from . import CallWorkerBase, new_call


def log(source: 'str', globals: 'Optional[Dict[str, Any]]' = None, locals: 'Optional[Dict[str, Any]]' = None):
    logging.info(f'{source} = {eval(source, globals, locals)}')


class TestWorker(CallWorkerBase):
    def process(self, a: 'int', b: 'int') -> 'Tuple[float, int]':
        return a / b, a % b


def server_midware(*args, next: 'Callable', **kwargs):
    with ldlog.WithLog('server_midware'):
        return next(*args, **kwargs)

def client_midware(*args, next: 'Callable', **kwargs):
    with ldlog.WithLog('client_midware'):
        return next(*args, **kwargs)


def main():
    cli = new_call(TestWorker)

    cli.add_client_midware(client_midware)
    cli.add_server_midware(server_midware)
    cli.add_post_fork_func(lambda: logging.info(f'worker has started. pid:{os.getpid()}'))

    cli.start()
    cli.connect()

    locals = {'cli': cli}
    log('cli.process(1, 2)', locals=locals)
    log('cli.process(a=1, b=0)', locals=locals)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\033[1;31moperation cancelled by user\033[0m\n")
        sys.exit(-1)
