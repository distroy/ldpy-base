#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#
# pyright: reportInvalidTypeVarUse=false


import multiprocessing.reduction
import os
from typing import Callable, Dict, Generic, List, Optional, Protocol, Type, TypeVar

PICKLER = multiprocessing.reduction.ForkingPickler

RES = TypeVar('RES')


class CallWorker(Protocol[RES]):
    @classmethod
    def name(cls) -> str: ...
    @classmethod
    def backlog(cls) -> int: ...
    @classmethod
    def worker_num(cls) -> int: ...
    @classmethod
    def start_timeout(cls) -> int: ...

    def process(self, *args, **kwargs) -> 'RES': ...


class CallMidware(Protocol[RES]):
    def __call__(self, *args, next: 'Callable[..., RES]', **kwargs) -> 'RES':
        ...


class CallClient(Protocol[RES]):
    def name(self) -> str: ...
    def add_post_fork_func(self, func: 'Callable[[], None]'): ...
    def add_server_midware(self, mw: 'CallMidware[RES]'): ...
    def add_client_midware(self, mw: 'CallMidware[RES]'): ...
    def start(self): ...
    def connect(self): ...
    def process(self, *args, **kwargs) -> 'RES': ...


class CallBase(Generic[RES]):
    def __init__(self, worker_cls: 'Type[CallWorker[RES]]'):
        super().__init__()

        name = worker_cls.name()
        name = name.removesuffix('_worker')
        self._worker_cls = worker_cls
        self._name = name

        cwd = os.path.abspath(os.getcwd())
        cache_dir = os.path.join(cwd, f'.cache/ld-call-worker')

        self._cache_dir = cache_dir
        self._master_lock_path = os.path.join(cache_dir, f'{name}-master.lock')
        self._worker_sock_path = os.path.join(cache_dir, f'{name}-worker.sock')

        self._post_fork_funcs: 'List[Callable[[], None]]' = []
        self._server_midwares: 'List[CallMidware[RES]]' = []
        self._client_midwares: 'List[CallMidware[RES]]' = []

    def name(self) -> str:
        return self._name

    def add_post_fork_func(self, func: 'Callable[[], None]'):
        self._post_fork_funcs.append(func)

    def add_server_midware(self, mw: 'CallMidware[RES]'):
        self._server_midwares.append(mw)

    def add_client_midware(self, mw: 'CallMidware[RES]'):
        self._client_midwares.append(mw)

    def _build_process_func(self, func: 'Callable[..., RES]', mws: 'List[CallMidware[RES]]'):
        i = len(mws)
        def get_next_func(next, mw):
            return lambda *args, **kwargs: mw(*args, next=next, **kwargs)
        while i > 0:
            i -= 1
            mw = mws[i]
            func = get_next_func(func, mw)
        return func



CMD_INIT = 0
CMD_CALL = 1


class CallRequest(object):
    def __init__(self, cmd=CMD_CALL, args: 'List' = [], kwargs: 'Dict' = {}) -> None:
        super().__init__()

        self.command = cmd
        self.args = args
        self.kwargs = kwargs

    @classmethod
    def decode(cls, raw: 'bytes') -> 'CallRequest':
        return PICKLER.loads(raw)

    @classmethod
    def encode(cls, obj: 'CallRequest') -> 'bytes':
        raw = PICKLER.dumps(obj)
        return bytes(raw)


class CallResponse(Generic[RES]):
    def __init__(self, exc: 'Optional[Exception]' = None, res: 'Optional[RES]' = None) -> None:
        super().__init__()

        self.exc = exc
        self.res = res

    @classmethod
    def decode(cls, raw: 'bytes') -> 'CallResponse[RES]':
        return PICKLER.loads(raw)

    @classmethod
    def encode(cls, obj: 'CallResponse[RES]') -> 'bytes':
        raw = PICKLER.dumps(obj)
        return bytes(raw)
