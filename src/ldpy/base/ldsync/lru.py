#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import functools
import logging
import time
from collections import OrderedDict
from typing import Any, Callable, Tuple, TypeVar

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

P = ParamSpec('P')
T = TypeVar('T')

class Lru(object):
    def __init__(self, size: 'int' = 128, ttl: 'int' = 60, log_interval_times=0):
        self.maxsize = size
        self.ttl = ttl
        self.log_interval_times = log_interval_times
        self._cache = OrderedDict()
        self.hits = 0
        self.misses = 0

    def __call__(self, func: 'Callable[P, T]') -> 'Callable[P, T]':
        @functools.wraps(func)
        def wrapper(*args: 'P.args', **kwargs: 'P.kwargs') -> 'T':
            total = self.hits + self.misses
            if self.log_interval_times > 0 and total > 0 and (total % self.log_interval_times) == 0:
                # print(f"hit cache rate: {self.cache_info()}")
                logging.info(f"[lru] hit rate: {self.cache_info()}")

            key = self._make_key(args, kwargs)
            res, ok = self._get_key(key)
            if ok:
                self.hits += 1
                self._cache.move_to_end(key)
                if self.log_interval_times > 0:
                    logging.info(f"[lru] hit cache: {func.__name__}{args}")
                return res

            self.misses += 1
            if self.log_interval_times > 0:
                logging.info(f"[lru] miss cache: {func.__name__}{args}")
            result = func(*args, **kwargs)
            self._set_cache(key, result)
            return result

        setattr(wrapper, 'lru', self)
        return wrapper

    def _make_key(self, args, kwargs) -> 'Tuple':
        return (args, tuple(sorted(kwargs.items())))

    def _get_key(self, key) -> 'Tuple[Any, bool]':
        if key not in self._cache:
            return None, False

        result, timestamp = self._cache[key]
        if time.time() - timestamp > self.ttl:
            del self._cache[key]
            return None, False

        return result, True

    def _set_cache(self, key, value):
        self._cache[key] = (value, time.time())
        if len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)

    def cache_info(self) -> 'dict':
        """获取缓存信息"""
        return {
            'size': len(self._cache),
            'maxsize': self.maxsize,
            'ttl': self.ttl,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')

    __c = 0

    @Lru(ttl=2,log_interval_times=16)
    def test(a: 'int', b: 'int'):
        global __c
        __c += 1
        return a * b + __c

    for i in range(16):
        print(f' === test(1, 2): {test(1, 2)}')
    for i in range(16):
        print(f' === test(2, 3): {test(2, 3)}')
    time.sleep(2)
    print(f' === test(1, 2): {test(1, 2)}')
    print(f' === test(2, 3): {test(2, 3)}')
    print()
    print(f' === cache info: {test.lru.cache_info()}')
