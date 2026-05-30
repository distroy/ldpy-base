#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import logging
import time
import traceback
from typing import Optional


class WithLog(object):
    def __init__(self, name: str, logging=True, level=logging.INFO, ignore_exc: bool = False):
        self._name = name
        self._begin = 0
        self._ignore_exc = ignore_exc
        self._logging = logging
        self._level = level

    def _log_func(self, msg: 'str', stacklevel: 'int', exc_info: 'Optional[Exception]' = None):
        if self._logging:
            logging.log(self._level, msg, stacklevel=stacklevel + 1,
                        exc_info=exc_info)
        elif exc_info:
            print(f'{msg}\n{"".join(traceback.format_exception(exc_info))}')

        else:
            print(msg)

    def __enter__(self):
        self._begin = time.time()
        self._log_func(f' === do {self._name} begin', stacklevel=2)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        cost = time.time() - self._begin
        self._log_func(f' === do {self._name} end. cost:{cost}s', stacklevel=2,
                       exc_info=exc_value)
        if self._ignore_exc:
            return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
    with WithLog('abc', logging=False, ignore_exc=True):
        1 / 0
    with WithLog('abc', ignore_exc=True):
        1 / 0
