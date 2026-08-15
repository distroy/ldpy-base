#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import logging
import os
import tempfile


class TempDir(object):
    def __init__(self, dir='', prefix=''):
        dir = dir or '.'
        if not os.path.exists(dir):
            os.makedirs(dir, exist_ok=True)

        self._root_dir = dir
        self._tdir = tempfile.TemporaryDirectory(dir=dir, prefix=prefix)
        logging.info(f' === open temporary directory. dir:{self.path}')

    @property
    def path(self): return self._tdir.name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self._tdir.cleanup()
        logging.info(f' === clean temporary directory. dir:{self.path}')


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')

    with TempDir() as d:
        logging.info(f'TempDir: {d.path}')
