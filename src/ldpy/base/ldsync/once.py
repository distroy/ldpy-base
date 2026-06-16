#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import threading
from typing import Callable, Generic, Optional, TypeVar


T = TypeVar('T')


class _once(Generic[T]):
    def __init__(self, func: 'Callable[[], T]'):
        if not callable(func):
            raise TypeError("the first argument must be callable")

        self.__func = func

        self.__done = False
        self.__res = None

    def reset(self):
        self.__done = False

    def done(self):
        return self.__done

    def __call__(self) -> T:
        return self.call()

    def call(self) -> T:
        if self.__done:
            return self.__res

        self.__res = self.__func()
        self.__done = True

        return self.__res

    def _get_res(self) -> 'Optional[T]':
        return self.__res


class Once(Generic[T]):
    def __init__(self, func: 'Callable[[], T]'):
        self.__once = _once(func)

        self.__lock = threading.Lock()

    def reset(self):
        with self.__lock:
            self.__once.reset()

    def done(self):
        return self.__once.done()

    # @decorator.decorator
    def __call__(self) -> T:
        return self.call()

    def call(self) -> T:
        if self.done():
            return self.__once._get_res()

        with self.__lock:
            return self.__once.call()


class ThreadOnce(Generic[T]):
    def __init__(self, func: 'Callable[[], T]'):
        if not callable(func):
            raise TypeError("the first argument must be callable")

        self.__func = func
        self.__data = threading.local()

    def _get(self, force: bool = True) -> 'Optional[_once[T]]':
        attr = 'value'
        if hasattr(self.__data, attr):
            return getattr(self.__data, attr)

        if not force:
            return None

        v = _once(self.__func)
        setattr(self.__data, attr, v)
        return v

    def reset(self):
        v = self._get(force=False)
        if not v:
            return
        v.reset()

    def done(self) -> bool:
        v = self._get(force=False)
        return bool(v) and v.done()

    def __call__(self) -> T:
        return self.call()

    def call(self) -> T:
        v = self._get(force=True)
        return v.call()


def main():
    __key = 'sequence'
    __cache = {__key: 0}

    def get_seq() -> int:
        key = 'sequence'
        __cache[key] += 1
        return __cache[key]

    def get_thread_run(fn: 'Callable[[], T]'):
        def thread_run():
            try:
                import time
                time.sleep(1)
                print(fn(), fn(), fn())
            except Exception as exc:
                import traceback
                print(traceback.format_exception(exc))
        return thread_run

    from concurrent.futures import ThreadPoolExecutor
    num = 10

    fn0 = Once(get_seq)
    with ThreadPoolExecutor(max_workers=num) as executor:
        for _ in range(num):
            executor.submit(get_thread_run(fn0))
    print(' === ')

    fn1 = ThreadOnce(get_seq)
    with ThreadPoolExecutor(max_workers=num) as executor:
        for _ in range(num):
            executor.submit(get_thread_run(fn1))
    print(' === ')


if __name__ == "__main__":
    main()
