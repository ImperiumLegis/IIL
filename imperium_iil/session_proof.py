"""Fixed-size challenge and response on a launcher-provided private socket."""

from dataclasses import dataclass
from hashlib import sha256
from time import monotonic

from .receipts import framed
from .requester_session import Session
from .reviewer_trust import require


@dataclass(frozen=True)
class Presentation:
    binding: Session
    receipt_digest: bytes
    call_digest: bytes

    @classmethod
    def for_submission(cls, binding, receipt, call):
        return cls(binding, sha256(receipt).digest(), sha256(call).digest())

    def message(self, nonce):
        require(len(nonce) == 32)
        s = self.binding
        return framed(b"IIL-REQUESTER-PROOF", (b"1", nonce, s.organization.encode(),
                      s.requester.encode(), s.session.encode(), sha256(s.public_key).digest(),
                      self.receipt_digest, self.call_digest))

    def challenge(self, nonce):
        return nonce + sha256(self.message(nonce)).digest()


def respond(key, pending, challenge):
    """Only sign the requester's independently prepared pending submission."""
    require(key.public_key().public_bytes_raw() == pending.binding.public_key)
    nonce = challenge[:32]
    require(pending.challenge(nonce) == challenge)
    return key.sign(pending.message(nonce))


def remaining(deadline):
    seconds = deadline - monotonic()
    if seconds <= 0:
        raise TimeoutError
    return seconds


def receive(channel, size, deadline):
    data = bytearray()
    while len(data) < size:
        channel.settimeout(remaining(deadline))
        chunk = channel.recv(size - len(data))
        if not chunk:
            raise EOFError
        data.extend(chunk)
    remaining(deadline)
    return bytes(data)
