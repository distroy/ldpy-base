#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


from collections.abc import Iterable, Mapping
import logging
import os
import socket
import select
import time
from typing import Type, TypeVar

# import bytedance.context
# from euler.errors import EulerError

from . import conn, call_worker, call_master

RES = TypeVar('RES')


class CallClientImpl(call_worker.CallBase[RES]):
    def __init__(self, worker_cls: 'Type[call_worker.CallWorker[RES]]'):
        super().__init__(worker_cls)

        pid = os.getpid()
        self._logid = f'[client-{self._name}:{pid}]'

        self._process_func = self._process

    def start(self):
        call_master.start(self)

    def connect(self):
        logid = self._logid
        logging.info(f'{logid} connect to call worker begin')

        self._process_func = self._build_process_func(self._process, self._client_midwares)

        try:
            now = time.time()
            timeout = self._worker_cls.start_timeout()
            ddl = now + timeout
            while True:
                try:
                    c = self._connect(False)
                    # logging.info(f'{logid} connect succ')

                    req = call_worker.CallRequest(cmd=call_worker.CMD_INIT)
                    req_raw = call_worker.CallRequest.encode(req)
                    c.send(req_raw)
                    # logging.info(f'{logid} send succ')

                    rsp_raw = c.recv()
                    rsp = call_worker.CallResponse[RES].decode(rsp_raw)
                    logging.info(f'{logid} connect to call worker succ')
                    return

                except Exception as exc:
                    if time.time() < ddl:
                        continue

                    logging.error(f'{logid} connect to call worker panic.',
                                  exc_info=exc)
                    raise exc
        finally:
            logging.info(f'{logid} connect to call worker end')

    def _connect(self, timeout=1, need_log: 'bool' = True):
        '''
            panic if not log
        '''

        logid = self._logid

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.setblocking(False)
        try:
            sock.connect(self._worker_sock_path)
        except BlockingIOError:
            pass
        except Exception as exc:
            sock.close()

            if not need_log:
                logging.error(f'{logid} connect to call worker panic.',
                              exc_info=exc)
            raise exc

        _, writeable, _ = select.select([], [sock], [], timeout)
        if writeable:
            # 再次检查连接状态
            ret = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if ret == 0:
                sock.setblocking(True)  # 恢复为阻塞模式以便后续操作
                return conn.Conn(sock)

            sock.close()
            if need_log:
                logging.error(
                    f'{logid} connect to call worker fail. ret:{ret}')
            raise ConnectionError(f'connect to call worker fail. ret:{ret}')

        sock.close()
        if need_log:
            logging.error(f'{logid} connect to call worker timeout:{timeout}s')
        raise TimeoutError(
            f'connect to call worker timeout. timeout:{timeout}s')

    def process(self, *args, **kwargs) -> 'RES':
        return self._process_func(*args, **kwargs)

    def _process(self, *args, **kwargs) -> 'RES':
        # logid = bytedance.context.get('logid')
        req = call_worker.CallRequest(args=list(args), kwargs=kwargs)
        req_raw = call_worker.CallRequest.encode(req)

        i = 0
        max_retry = 3
        while True:
            i += 1
            try:
                rsp_raw = self._send_and_recv(req_raw)
                break

            except OSError as exc:
                if exc.errno == 107 and i <= max_retry:
                    continue

                logging.error(f'{self._logid} send to call worker fail',
                              exc_info=exc)
                raise exc

        rsp = call_worker.CallResponse[RES].decode(rsp_raw)
        if rsp.exc:
            raise rsp.exc

        res = rsp.res
        logging.info(f'call worker process succ. worker:{self._name}, '
                     f'args:{_to_print(args)}, kwargs:{_to_print(kwargs)}, '
                     f'res:{_to_print(res)}')
        return res

    def _send_and_recv(self, req0_raw: 'bytes') -> 'bytes':
        c = self._connect()

        try:
            c.send(req0_raw)
            return c.recv()

        finally:
            c.close()

try:
    from torch import Tensor
except:
    class Tensor(object):
        dtype = 0
        device = 0
        shape = 0

        def detach(self, *args, **kwargs): return self
        def reshape(self, *args, **kwargs): return self
        def numpy(self, *args, **kwargs): return self
        def __getitem__(self, key): return self

def _to_print(obj, seen=None):
    """
    将任意对象递归转换为 dict / list 结构，基础类型原样返回。

    参数:
        obj: 任意 Python 对象
        seen: 用于检测循环引用的集合（内部使用，一般不需要手动提供）

    返回:
        转换后的 dict / list / 基础类型
    """
    if seen is None:
        seen = set()

    # 避免循环引用导致的无限递归
    obj_id = id(obj)
    if obj_id in seen:
        # 循环引用时返回字符串标识（也可返回 None 或原对象，视需求而定）
        return f"<recursion: {repr(obj)}>"
    seen.add(obj_id)

    try:
        try:
            if isinstance(obj, Tensor):
                return f'<torch.Tensor(dtype={obj.dtype}, device={obj.device}, shape={obj.shape}, ' \
                    f'sample={obj.detach()[:10].reshape(-1)[:10].numpy()})>'
        except:
            pass

        # 1. 基础类型（不可变且无需转换）
        if isinstance(obj, (int, float, str, bool, type(None))):
            return obj

        if isinstance(obj, bytes):
            return f'<bytes(size={len(obj)}, sample={obj[:10]})>'

        # 2. 字典或映射类型
        if isinstance(obj, Mapping):
            return {_to_print(k, seen): _to_print(v, seen) for k, v in obj.items()}

        # 3. 可迭代对象（list, tuple, set, frozenset 等）
        if isinstance(obj, Iterable) and not isinstance(obj, (str, bytes, dict)):
            # 注意：str/bytes 已在上面的基础类型中处理，此处不会重复
            return [_to_print(item, seen) for item in obj]

        # 4. 自定义类实例（包括 namedtuple、dataclass、普通类）
        # 优先使用 __dict__，若没有则尝试 __slots__
        if hasattr(obj, '__dict__'):
            # 直接使用实例字典
            return _to_print(vars(obj), seen)

        if hasattr(obj, '__slots__'):
            # __slots__ 类没有 __dict__，手动构建字典
            slots_dict = {
                slot: getattr(obj, slot)
                for slot in obj.__slots__ if hasattr(obj, slot)
            }
            return _to_print(slots_dict, seen)
        # 5. 其他无法转换的对象（函数、模块、类型、None 等）
        # 可根据需要改为 str(obj) 或抛出异常，这里保留原样
        return obj

    finally:
        # 递归返回后移除 id，允许其他分支复用 seen
        seen.remove(obj_id)


def new_call(worker_cls: 'Type[call_worker.CallWorker[RES]]', start=False, connect=False) -> 'call_worker.CallClient[RES]':
    cli = CallClientImpl[RES](worker_cls)
    if start or connect:
        cli.start()
    if connect:
        cli.connect()
    return cli
