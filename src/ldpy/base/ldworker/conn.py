#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) tanrenchong
#


import socket


PADDING = b'x'[0]

class Conn(object):
    def __init__(self, sock: 'socket.socket') -> None:
        self.sock = sock

    def recv_exact(self, n: 'int'):
        sock = self.sock
        data = b''
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("connection has been closed")
            data += chunk
        return data

    def recv(self):
        """full message: 1 byte padding + 4 bytes size + raw"""
        raw0 = self.recv_exact(1)
        pad = raw0[0]
        if pad != PADDING:
            raise Exception(f'recv invalid padding. want:{PADDING}, got:{pad}')
        raw1 = self.recv_exact(4)
        size = int.from_bytes(raw1, 'big', signed=True)

        raw = self.recv_exact(size)
        return raw

    def send(self, raw: bytes):
        """full message: 1 byte padding + 4 bytes size + raw"""
        raw0 = bytes([PADDING])
        size = len(raw)
        raw1 = size.to_bytes(4, 'big', signed=True)

        buff = b''.join([raw0, raw1, raw])
        self.sock.sendall(buff)

    def close(self):
        self.sock.close()
