"""
线程安全数据库连接池（基于 queue.Queue）。

配合 db_config.Connection：close() 将连接归还池中，而非物理关闭。
"""
from __future__ import annotations

import queue
import threading
from typing import Callable, Optional


class ConnectionPool:
    def __init__(self, factory: Callable, pool_size: int = 10, overflow: int = 5):
        self._factory = factory
        self._pool_size = max(1, pool_size)
        self._overflow = max(0, overflow)
        self._pool: queue.Queue = queue.Queue(maxsize=self._pool_size)
        self._overflow_count = 0
        self._lock = threading.Lock()
        self._closed = False

        for _ in range(self._pool_size):
            self._pool.put(self._factory())

    def acquire(self, timeout: Optional[float] = 5.0):
        if self._closed:
            raise RuntimeError("连接池已关闭")
        try:
            return self._pool.get(block=True, timeout=timeout)
        except queue.Empty:
            with self._lock:
                if self._overflow_count < self._overflow:
                    self._overflow_count += 1
                    return self._factory()
            raise TimeoutError("获取数据库连接超时，请稍后重试")

    def release(self, conn, *, discard: bool = False):
        if self._closed or discard:
            try:
                conn.close()
            except Exception:
                pass
            with self._lock:
                if self._overflow_count > 0:
                    self._overflow_count -= 1
            return

        try:
            conn.rollback()
        except Exception:
            discard = True

        if discard:
            try:
                conn.close()
            except Exception:
                pass
            with self._lock:
                if self._overflow_count > 0:
                    self._overflow_count -= 1
            try:
                self._pool.put_nowait(self._factory())
            except queue.Full:
                pass
            return

        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            try:
                conn.close()
            except Exception:
                pass

    def close_all(self):
        self._closed = True
        while True:
            try:
                conn = self._pool.get_nowait()
            except queue.Empty:
                break
            try:
                conn.close()
            except Exception:
                pass

    @property
    def stats(self) -> dict:
        return {
            "pool_size": self._pool_size,
            "available": self._pool.qsize(),
            "overflow_in_use": self._overflow_count,
            "closed": self._closed,
        }
