#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import os
from typing import TypeVar, Union

T = TypeVar('T')


def get(key: 'str', _def: 'T' = None) -> 'Union[str, T]':
    return os.getenv(key, _def)


def get_as_str(key: 'str', _def: 'str' = '') -> 'str':
    return get(key, _def)


def get_as_int(key: 'str', _def: 'int' = 0) -> 'int':
    v = get(key)
    if v is None:
        return _def
    try:
        return int(v)
    except:
        pass
    try:
        return int(float(v))
    except:
        pass
    try:
        return 1 if bool(v) else 0
    except:
        pass
    return _def


def get_as_bool(key: 'str', _def: 'bool' = False) -> 'bool':
    v = get(key)
    if not v:
        return _def
    try:
        return True if int(v) else False
    except:
        pass
    try:
        return bool(v)
    except:
        pass
    try:
        return True if float(v) else False
    except:
        pass
    v = v.lower()
    # if v in ('on', 'enable', 'enabled'):
    #     return True
    if v in ('off', 'disable', 'disabled', 'null'):
        return False
    return True
