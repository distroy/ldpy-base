#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import time
import backgrounds
import fcntl
import logging
import os
import setproctitle
import signal
import socket
import stat
import sys
from typing import Generic, List, Optional, TypeVar

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

from .. import ldlog
from . import call_service, call_worker

P = ParamSpec('P')
R = TypeVar('R')


class Lock(object):
    def __init__(self, file_path: str) -> None:
        self.lock_file_path = file_path
        self.dir_path = os.path.dirname(file_path)
        self.lock_fd = None

    def try_lock(self):
        lock_path = self.lock_file_path
        lock_dir = os.path.dirname(lock_path)
        try:
            os.makedirs(lock_dir, 0o755, True)
        except Exception as exc:
            logging.error(f'os.makedirs fail. dir:{lock_dir}', exc_info=exc)

        lock_fd = open(lock_path, 'w')
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd = lock_fd
            return True

        except BlockingIOError:
            lock_fd.close()
            return False

    def unlock(self):
        lock_fd = self.lock_fd
        self.lock_fd = None
        if lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()


class CallMaster(Generic[P, R]):
    def __init__(self, base: 'call_worker.CallBase[P, R]'):
        super().__init__()

        self._base = base
        worker_cls = base._worker_cls

        pid = os.getpid()
        self._logid = f'[master-{self._base._name}:{pid}]'

        self._running = False
        self._worker_num = max(worker_cls.worker_num(), 1)
        self._children: 'List[int]' = []

    def name(self): return self._base.name()

    def _stop(self):
        self._running = False

    def run(self):
        backgrounds.start()
        self._running = True

        def graceful_exit(sig, frame):
            self._stop()

        signal.signal(signal.SIGTERM, graceful_exit)
        signal.signal(signal.SIGINT, graceful_exit)

        lock = Lock(self._base._master_lock_path)
        if not lock.try_lock():
            logging.warning(f'{self._logid} exit because locked by another')
            sys.exit(0)
        logging.info(f'{self._logid} continue start after locked')

        logging.info(f'{self._logid} run begin')
        try:
            self._run_pre_fork_funcs()

            self._run()
        finally:
            lock.unlock()
            logging.info(f'{self._logid} run end')

    def _run_pre_fork_funcs(self):
        # 在 master 进程内、fork 任何 worker 之前，逐个执行预加载钩子。
        # 单个钩子失败不应拖垮 master：记录异常后继续，把最终是否可用交给 worker 自身的加载逻辑。
        logid = self._logid
        for func in self._base._pre_fork_funcs:
            name = getattr(func, '__name__', repr(func))
            with ldlog.WithLog(f'{logid} pre_fork_func {name}', ignore_exc=True):
                func()

    def _run(self):
        sock = self._listen()

        try:
            while self._running:
                self._start_children(sock)
                self._check_children_exit()
                time.sleep(0.2)

        finally:
            sock.close()
            self._wait_children()

    def _wait_children(self):
        logid = self._logid

        try:
            logging.info(f'{logid} kill all children at exit')
            for pid in self._children:
                os.kill(pid, signal.SIGTERM)

            logging.info(f'{logid} wait all children at exit')

            ddl = time.time() + 60
            while len(self._children) > 0:
                self._check_children_exit()
                now = time.time()
                if now > ddl:
                    break
                time.sleep(0.2)

            for pid in self._children:
                os.kill(pid, signal.SIGKILL)

        except Exception as exc:
            logging.error(f'{logid} wait all children panic at exit',
                          exc_info=exc)
        finally:
            logging.info(f'{logid} wait all children end at exit')

    def _check_children_exit(self):
        logid = self._logid

        for pid in self._children:
            try:
                ret_pid, status = os.waitpid(pid, os.WNOHANG)
                if ret_pid != pid:  # 子进程已结束
                    continue
                code = os.WEXITSTATUS(status)
                logging.info(f'{logid} wait child exit. pid:{pid}, code:{code}')
                self._children.remove(pid)
            except ChildProcessError:
                # 指定的子进程不存在
                code = 'unknow'
                logging.info(f'{logid} wait child exit. pid:{pid}, code:{code}')
                self._children.remove(pid)

    def _start_children(self, sock: socket.socket):
        num = self._worker_num
        while len(self._children) < num:
            pid = call_service.start(num, sock, self._base)
            self._children.append(pid)
            logging.info(f'{self._logid} start call worker succ. pid:{pid}')

    def _listen(self):
        sock_path = self._base._worker_sock_path
        if os.path.exists(sock_path):
            os.remove(sock_path)

        backlog = self._base._worker_cls.backlog()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(sock_path)
        sock.listen(backlog)

        logging.info(f'{self._logid} call worker listen succ. sock:{sock_path}')
        return sock


def _is_socket(fd: int):
    try:
        # 1. 检查是否是 socket
        mode = os.fstat(fd).st_mode
        if stat.S_IFMT(mode) != stat.S_IFSOCK:
            return False

        # 2. 创建临时 socket 对象（不拥有 fd 的所有权）
        s = socket.socket(fileno=fd)
        # 3. 获取 SO_ACCEPTCONN 选项
        opt = s.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN)
        # 4. 将 fd 从 socket 对象中分离，防止对象销毁时关闭 fd
        s.detach()
        return opt == 1
    except OSError:
        # fd 无效或不存在，忽略
        return False

    return True


def _logging_fds() -> 'set':
    fds = set()
    loggers = [logging.getLogger()]
    for name in list(logging.root.manager.loggerDict):
        lg = logging.getLogger(name)
        if isinstance(lg, logging.Logger):
            loggers.append(lg)

    for lg in loggers:
        for h in getattr(lg, 'handlers', []):
            for attr in ('sock', 'socket', 'stream'):
                obj = getattr(h, attr, None)
                if obj is None:
                    continue
                try:
                    fds.add(obj.fileno())
                except (OSError, ValueError, AttributeError):
                    pass
    return fds


def close_all_socket(skip_fds: 'Optional[set]' = None):
    try:
        max_fd = os.sysconf('SC_OPEN_MAX')
    except (ValueError, OSError):
        max_fd = 1024   # 常见系统的安全上限

    skip_fds = skip_fds or set()

    # skip stdin(0), stdout(1), stderr(2)
    for fd in range(3, max_fd):
        if fd in skip_fds:
            continue
        try:
            if _is_socket(fd):
                os.close(fd)
        except:
            pass


def start(base: 'call_worker.CallBase[P, R]'):
    # wait + fork 2次，避免僵尸进程
    pid = os.fork()
    if pid > 0:
        # in parent
        os.waitpid(pid, 0)
        return pid

    pid = os.fork()
    if pid > 0:
        # in parent
        sys.exit(0)

    # in child
    # macOS: fork 后不 exec 直接调用 setproctitle 会走 CoreFoundation 导致段错误，故跳过
    if sys.platform != 'darwin':
        proc_title = call_worker.make_proc_title('master', base.name())
        setproctitle.setproctitle(proc_title)

    with ldlog.WithLog('close_all_socket'):
        close_all_socket(skip_fds=_logging_fds())

    mgr = CallMaster(base)
    mgr.run()
    sys.exit(0)
