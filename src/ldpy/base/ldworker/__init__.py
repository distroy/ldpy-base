#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) tanrenchong
#


import logging
from .. import ldenv
from .call_client import new_call

DEFAULT_START_TIMEOUT = 600


class CallWorkerBase(object):
    def __init__(self):
        pass

    @classmethod
    def name(cls):
        n = cls.__name__
        n = n.removesuffix('Worker')
        n = n.lower()
        n = n.removesuffix('_worker')
        return n

    @classmethod
    def backlog(cls) -> int:
        n = cls.name()
        key0 = f'{n.upper()}_BACKLOG'
        key1 = 'BACKLOG'
        backlog = ldenv.get_as_int(key0) or ldenv.get_as_int(key1)
        backlog = max(backlog, 0)
        logging.info(f'get call worker listen backlog succ. worker:{n}, '
                     f'backlog:{backlog}')
        return backlog

    @classmethod
    def worker_num(cls):
        n = cls.name()
        key = f'{n.upper()}_WORKER_NUM'
        num = ldenv.get_as_int(key)
        num = max(num, 1)
        logging.info(f'get call worker num succ. worker:{n}, num:{num}')
        return num

    @classmethod
    def start_timeout(cls):
        n = cls.name()
        key0 = f'{n.upper()}_START_TIMEOUT'
        key1 = 'START_TIMEOUT'
        timeout = ldenv.get_as_int(key0) or ldenv.get_as_int(key1)
        timeout = timeout if timeout > 0 else DEFAULT_START_TIMEOUT
        logging.info(f'get call worker start timeout succ. worker:{n}, '
                     f'timeout:{timeout}')
        return timeout


__all__ = [
    'DEFAULT_START_TIMEOUT',
    'new_call',
    'CallWorkerBase',
]
