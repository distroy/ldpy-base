#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import logging
import time


class WithLog(object):
    def __init__(self, name: str, ignore_exc: bool = False):
        self._name = name
        self._begin = 0
        self._ignore_exc = ignore_exc

    def __enter__(self):
        self._begin = time.time()
        logging.info(f' === do {self._name} begin', stacklevel=2)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        cost = time.time() - self._begin
        logging.info(f' === do {self._name} end. cost:{cost}s', stacklevel=2,
                     exc_info=exc_value)
        if self._ignore_exc:
            return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
    with WithLog('abc', ignore_exc=True):
        1 / 0
