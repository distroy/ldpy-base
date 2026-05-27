#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import logging
import os
import sys
import tempfile


class TempDir(object):
    def __init__(self, dir='', prefix=''):
        if not os.path.exists(dir):
            os.makedirs(dir, exist_ok=True)

        self._root_dir = dir
        self._tdir = tempfile.TemporaryDirectory(dir=dir, prefix=prefix)
        self.path = self._tdir.name
        logging.info(f' === open temporary directory. dir:{self.path}')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self._tdir.cleanup()
        logging.info(f' === clean temporary directory. dir:{self.path}')
