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
            "a test tried to open a socket. Tests must never reach the network — "
            "inject or patch the fetcher instead."
        )

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
