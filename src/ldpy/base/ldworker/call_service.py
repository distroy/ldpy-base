#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import threading
import time
import backgrounds
import logging
import os
import sys
import signal
import socket
from typing import Generic, TypeVar
import psutil
import setproctitle

from .. import ldlog
from . import conn, call_worker


RES = TypeVar('RES')


class Service(Generic[RES]):
    def __init__(self, worker_num: 'int', sock: 'socket.socket', base: 'call_worker.CallBase[RES]'):
        super().__init__()

        self._base = base
        worker_cls = base._worker_cls

        ppid = os.getppid()
        pid = os.getpid()

        self._logid = f'[worker-{worker_cls.name()}:{pid}]'

        with ldlog.WithLog(f'init_worker_object {worker_cls.name()}'):
            w = worker_cls()

        self._ppid = ppid
        self._name = worker_cls.name()
        self._worker_cls = worker_cls
        self._worker = w
        self._worker_num = worker_num

        self._process_func = base._build_process_func(w.process, base._server_midwares)

        self._sock = sock
        self._running = False

    def _stop(self):
        self._running = False

    def run(self):
        backgrounds.start()
        self._running = True

        def graceful_exit(sig, frame):
            self._stop()

        signal.signal(signal.SIGTERM, graceful_exit)
        signal.signal(signal.SIGINT, graceful_exit)

        th = threading.Thread(target=self._thread_check_parent)
        th.daemon = True
        th.start()

        for func in self._base._post_fork_funcs:
            func()

        self._sock.settimeout(1.0)

        logid = self._logid
        logging.info(f'{logid} call worker run begin')
        try:
            while self._running:
                try:
                    sock, addr = self._sock.accept()
                except socket.timeout:
                    # 超时后继续循环，检查 should_exit
                    continue

                # logging.info(f'{logid} accept conn succ. addr:{addr}')
                c = conn.Conn(sock)

                try:
                    self._handle_conn(c)
                except Exception as exc:
                    logging.info(f'{logid} call worker handle conn panic', exc_info=exc)
                finally:
                    c.close()
        finally:
            logging.info(f'{logid} call worker run end')

    def _thread_check_parent(self):
        ppid = self._ppid
        logid = self._logid

        logging.info(f'{logid} thread check parent begin. ppid:{ppid}')

        pps = psutil.Process(ppid)
        while self._running:
            try:
                status = pps.status()
                if status in (psutil.STATUS_DEAD, psutil.STATUS_STOPPED):
                    logging.warning(f'{logid} parent is not running now. '
                                    f'ppid:{ppid}')
                    self._stop()
            except psutil.NoSuchProcess:
                logging.warning(f'{logid} parent is not running now. '
                                f'ppid:{ppid}')
                self._stop()
            finally:
                time.sleep(1)
        logging.info(f'{logid} thread check parent end. ppid:{ppid}')

    def _handle_conn(self, c: 'conn.Conn'):
        req_raw = c.recv()
        req = call_worker.CallRequest.decode(req_raw)

        if req.command == call_worker.CMD_INIT:
            rsp = call_worker.CallResponse[RES]()
        elif req.command == call_worker.CMD_CALL:
            rsp = self._process_request(req)
        else:
            msg = f'invalid command. cmd:{req.command}, worker:{self._name}'
            logging.error(msg)
            exc = Exception(msg)
            rsp = call_worker.CallResponse[RES](exc=exc)

        rsp_raw = call_worker.CallResponse.encode(rsp)
        c.send(rsp_raw)

    def _process_request(self, req: 'call_worker.CallRequest') -> 'call_worker.CallResponse[RES]':
        logid = self._logid

        with ldlog.WithLog(f'call worker process [{self._name}]'):
            try:
                # res = self._worker.process(*req.args, **req.kwargs)
                res = self._process_func(*req.args, **req.kwargs)
                logging.info(f'{logid} process request succ')
                return call_worker.CallResponse[RES](res=res)

            except Exception as exc:
                logging.error(f'{logid} process request panic', exc_info=exc)
                return call_worker.CallResponse[RES](exc=exc)


def start(worker_num: 'int', sock: 'socket.socket', base: 'call_worker.CallBase[RES]') -> 'int':
    pid = os.fork()
    if pid > 0:
        # in parent
        return pid

    # in child
    s = Service(worker_num, sock, base)

    worker_cls = base._worker_cls
    proc_title = f'call: worker [{worker_cls.name()}]'
    setproctitle.setproctitle(proc_title)

    s.run()
    sys.exit(0)
