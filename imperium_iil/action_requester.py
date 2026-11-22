"""Child endpoint for the disposable action walkthrough."""

import os
import socket
import sys

from .actions import _worker
from .action_manifest import LIMIT
from .reviewer_trust import require


def main():
    stream = sys.stdin.buffer
    if os.name == "nt":
        size = int.from_bytes(stream.read(4), "big")
        require(0 < size <= 4096)
        channel = socket.fromshare(stream.read(size))
    else:
        channel = socket.socket(fileno=int(sys.argv[4]))
    call = stream.read(LIMIT + 1)
    require(len(call) <= LIMIT)
    _worker(channel, *sys.argv[1:4], call)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, EOFError):
        sys.exit(1)
