#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#
# pyright: reportInvalidTypeVarUse=false


import multiprocessing.reduction
import os
from typing import Callable, Dict, Generic, List, Optional, Protocol, Type, TypeVar

try:
    from typing import ParamSpec, Concatenate
except ImportError:
    from typing_extensions import ParamSpec, Concatenate

PICKLER = multiprocessing.reduction.ForkingPickler

P = ParamSpec('P')
R = TypeVar('R')


# proc title 生成函数的签名：接收 (type, name)，返回最终进程标题。
#   type -> 'master' | 'worker'
#   name -> worker 的名字
ProcTitleFunc = Callable[[str, str], str]


def _default_proc_title_func(type: 'str', name: 'str') -> 'str':
    # 默认实现，保持既有行为不变：
    #   master 进程 -> "call: master [xxx]"
    #   worker 进程 -> "call: worker [xxx]"
    return f'call: {type} [{name}]'


_proc_title_func: 'ProcTitleFunc' = _default_proc_title_func


def set_proc_title_func(func: 'ProcTitleFunc') -> 'None':
    '''全局注入 proc title 生成函数。func 接收 (type, name) 并返回进程标题，
    对之后 fork 出的所有 master/worker 进程生效。传入 None 恢复默认实现。'''
    global _proc_title_func
    _proc_title_func = func or _default_proc_title_func


def make_proc_title(type: 'str', name: 'str') -> 'str':
    '''按当前生效的生成函数产出进程标题，供 master/worker 启动时设置进程名。'''
    return _proc_title_func(type, name)


class CallWorker(Protocol[P, R]):
    @classmethod
    def name(cls) -> str: ...
    @classmethod
    def backlog(cls) -> int: ...
    @classmethod
    def worker_num(cls) -> int: ...
    @classmethod
    def start_timeout(cls) -> int: ...

    def process(self, *args: 'P.args', **kwargs: 'P.kwargs') -> 'R': ...


NextFunc = Callable[P, R]

class CallMidware(Protocol[P, R]):
    # midware 的语义契约：第一个参数是 next（与 process 同签名），其余参数与 process 保持一致。
    # 实际接收处统一用 `Callable[Concatenate[NextFunc[P, R], P], R]`，以便 IDE 悬停时展开出完整签名。
    def __call__(self, next: 'NextFunc[P, R]', *args: 'P.args', **kwargs: 'P.kwargs') -> 'R':
        ...


class CallClient(Protocol[P, R]):
    def name(self) -> str: ...
    def add_post_fork_func(self, func: 'Callable[[], None]'): ...
    def add_pre_fork_func(self, func: 'Callable[[], None]'): ...
    def add_server_midware(self, mw: 'Callable[Concatenate[NextFunc[P, R], P], R]'): ...
    def add_client_midware(self, mw: 'Callable[Concatenate[NextFunc[P, R], P], R]'): ...
    def start(self): ...
    def connect(self): ...
    def process(self, *args: 'P.args', **kwargs: 'P.kwargs') -> 'R': ...


class CallBase(Generic[P, R]):
    def __init__(self, worker_cls: 'Type[CallWorker[P, R]]'):
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

        self._pre_fork_funcs: 'List[Callable[[], None]]' = []
        self._post_fork_funcs: 'List[Callable[[], None]]' = []
        self._server_midwares: 'List[Callable[Concatenate[NextFunc[P, R], P], R]]' = []
        self._client_midwares: 'List[Callable[Concatenate[NextFunc[P, R], P], R]]' = []

    def name(self) -> str:
        return self._name

    def add_post_fork_func(self, func: 'Callable[[], None]'):
        self._post_fork_funcs.append(func)

    def add_pre_fork_func(self, func: 'Callable[[], None]'):
        self._pre_fork_funcs.append(func)

    def add_server_midware(self, mw: 'Callable[Concatenate[NextFunc[P, R], P], R]'):
        self._server_midwares.append(mw)

    def add_client_midware(self, mw: 'Callable[Concatenate[NextFunc[P, R], P], R]'):
        self._client_midwares.append(mw)

    def _build_process_func(self, func: 'NextFunc[P, R]', mws: 'List[Callable[Concatenate[NextFunc[P, R], P], R]]') -> 'Callable[P, R]':
        def get_next_func(next, mw):
            def next_func(*args: 'P.args', **kwargs: 'P.kwargs'):
                return mw(next, *args, **kwargs)
            return next_func

        i = len(mws)
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


class CallResponse(Generic[R]):
    def __init__(self, exc: 'Optional[Exception]' = None, res: 'Optional[R]' = None) -> None:
        super().__init__()

        self.exc = exc
        self.res = res

    @classmethod
    def decode(cls, raw: 'bytes') -> 'CallResponse[R]':
        return PICKLER.loads(raw)

    @classmethod
    def encode(cls, obj: 'CallResponse[R]') -> 'bytes':
        raw = PICKLER.dumps(obj)
        return bytes(raw)
