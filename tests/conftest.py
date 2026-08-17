"""Test-wide guarantees that do not depend on the code under test being correct.

The suite's no-network property was previously a convention: one non-autouse
fixture in one module patching one function. A phase-gate review measured 17
outbound attempts across three mutants, one run taking 150s against a 2s
baseline. Isolation has to be a mechanism.
"""
import socket

import pytest


class NetworkUseInTest(Exception):
    pass


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def blocked(*a, **kw):
        raise NetworkUseInTest(
            "a test tried to reach the network. Tests must never fetch — "
            "inject or patch the fetcher instead."
        )

    # Python's socket layer catches trafilatura (urllib3) and anything else in
    # pure Python.
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)

    # But it does NOT catch ddgs: it fetches through primp, a Rust client that
    # opens sockets in native code. You cannot guard a boundary you do not own.
    # research.search/extract are this project's only two fetch calls, and a
    # guard there cannot be bypassed by a dependency's choice of HTTP stack.
    from agenticsocial import research

    monkeypatch.setattr(research, "search", blocked)
    monkeypatch.setattr(research, "extract", blocked)
