"""Minimal client for the Cheat Engine MCP bridge (TCP side).

The relay process (started by the user, medium integrity) speaks the length
prefixed JSON-RPC frames to CE's named pipe. Our sandbox is Low integrity and
cannot open the pipe itself, but loopback TCP is unrestricted.
"""
from __future__ import annotations

import json
import socket
import struct
import time


class CEClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 9876, timeout: float = 20.0) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._id = 0

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def _read_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("relay closed the connection")
            buf += chunk
        return buf

    def call(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        body = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._id,
        }).encode("utf-8")
        self.sock.sendall(struct.pack("<I", len(body)) + body)
        header = self._read_exact(4)
        (size,) = struct.unpack("<I", header)
        payload = self._read_exact(size)
        return json.loads(payload.decode("utf-8"))

    def lua(self, code: str) -> str:
        """Evaluate arbitrary Lua inside CE and return its string result."""
        resp = self.call("evaluate_lua", {"code": code})
        if "error" in resp:
            raise RuntimeError(resp["error"])
        result = resp.get("result", resp)
        if isinstance(result, dict):
            return str(result.get("result", result))
        return str(result)


if __name__ == "__main__":
    c = CEClient()
    print("ping   :", c.call("ping", {}))
    print("process:", c.call("get_process_info", {}))
    print("lua    :", c.lua("return 'hello from CE '..(getOpenedProcessID() or 0)"))
    c.close()
