#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import logging
import time
import traceback
from typing import Mapping, Optional
try:
    from typing import Protocol
except:
    from typing_extensions import Protocol


class Logger(Protocol):
    def log(self, level: 'int', msg: 'object', *args: 'object', exc_info: 'Optional[Exception]' = None,
            stack_info: 'bool' = False, stacklevel: 'int' = 1, extra: 'Optional[Mapping[str, object]]' = None):
        ...


class WithLog(object):
    def __init__(self, name: str, logging=True, level=logging.INFO, ignore_exc: bool = False,
                 logger: 'Optional[Logger]' = None):
        self._name = name
        self._begin = 0
        self._ignore_exc = ignore_exc
        self._logging = logging
        self._level = level
        self._logger = logger

    def _log_func(self, msg: 'str', stacklevel: 'int', exc_info: 'Optional[Exception]' = None):
        if self._logger:
            self._logger.log(self._level, msg, stacklevel=stacklevel + 1,
                             exc_info=exc_info)
        elif self._logging:
            logging.log(self._level, msg, stacklevel=stacklevel + 1,
                        exc_info=exc_info)
        elif exc_info:
            print(f'{msg}\n{"".join(traceback.format_exception(exc_info))}')

        else:
            print(msg)

    def __enter__(self):
        self._begin = time.time()
        self._log_func(f' === with log begin. name:{self._name}', stacklevel=2)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        cost = time.time() - self._begin
        self._log_func(f' === with log end. name:{self._name}, cost:{cost}s', stacklevel=2,
                       exc_info=exc_value)
        if self._ignore_exc:
            return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
    with WithLog('logging=1,ignore_exc=1', logging=False, ignore_exc=True):
        1 / 0
    with WithLog('ignore_exc=1', ignore_exc=True):
        1 / 0
    with WithLog('ignore_exc=1,logger=logging', logger=logging, ignore_exc=True):
        1 / 0
