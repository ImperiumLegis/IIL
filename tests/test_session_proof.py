import os
import socket
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.exceptions import InvalidSignature

from imperium_iil.requester_session import Session
from imperium_iil.session_proof import Presentation, receive, respond


def test_proof_binds_own_submission_and_nonce():
    key = Ed25519PrivateKey.generate()
    binding = Session("demo", "agent", "a" * 64, key.public_key().public_bytes_raw())
    pending = Presentation.for_submission(binding, b"receipt", b"call")
    nonce = os.urandom(32)
    signature = respond(key, pending, pending.challenge(nonce))
    key.public_key().verify(signature, pending.message(nonce))
    for other in (Presentation.for_submission(binding, b"other", b"call"),
                  Presentation.for_submission(binding, b"receipt", b"other")):
        with pytest.raises(ValueError):
            respond(key, other, pending.challenge(nonce))
    with pytest.raises(InvalidSignature):
        key.public_key().verify(signature, pending.message(os.urandom(32)))


def test_partial_frame_times_out():
    sender, receiver = socket.socketpair()
    with sender, receiver:
        sender.sendall(b"x")
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            receive(receiver, 64, start + 0.05)
        assert time.monotonic() - start < 1
        sender.shutdown(socket.SHUT_WR)
        with pytest.raises(EOFError):
            receive(receiver, 64, time.monotonic() + 1)
