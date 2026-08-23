"""A spend guard for the model-backed endpoints.

Every request to ``/api/agent`` costs real money on somebody's OpenAI key. That is
fine on localhost and not fine behind a public tunnel URL, which is where this
gets shared with teammates and, in principle, with anyone who learns the address.

So the agent endpoints carry two ceilings: a per-caller allowance so one person
cannot loop a script, and a process-wide total so the worst case is bounded no
matter how many callers appear. Both reset on restart, which is the right
behaviour for a demo rather than a service.

Deliberately in-process and dependency-free. A shared store would be the right
answer for something long-lived; for a tunnel that exists for an afternoon it
would be more moving parts than the problem deserves.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

# Per caller, in a rolling window.
PER_IP = 25
WINDOW_SECONDS = 3600

# Per process lifetime, across every caller. Restart to clear.
TOTAL = 300

_hits: dict[str, deque[float]] = defaultdict(deque)
_total = 0


class RateLimited(Exception):
    """Raised with a message suitable for showing a person."""


def caller(request) -> str:
    """Best-effort caller identity.

    Behind a tunnel the socket peer is the tunnel itself, so the forwarded header
    is the only thing that distinguishes callers. It is spoofable, which is why
    the process-wide total exists as well: the per-caller limit discourages
    casual looping, the total is what actually bounds the bill.
    """
    fwd = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check(request) -> None:
    """Raise :class:`RateLimited` if this call should not be spent."""
    global _total

    if _total >= TOTAL:
        raise RateLimited(
            f"This demo instance has answered its limit of {TOTAL} agent questions. "
            "Every other part of the page still works. Restart the server to reset."
        )

    who = caller(request)
    now = time.time()
    q = _hits[who]
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()

    if len(q) >= PER_IP:
        # The oldest hit is what has to age out, so it gives the wait. Guarded
        # because an allowance of zero satisfies the test with an empty queue,
        # and a misconfiguration should still return 429 rather than crash.
        wait = int((WINDOW_SECONDS - (now - q[0])) / 60) + 1 if q else WINDOW_SECONDS // 60
        raise RateLimited(
            f"You have used this demo's allowance of {PER_IP} agent questions per hour. "
            f"Try again in about {wait} minutes. The map, the charts and every "
            "measurement on the page are unaffected."
        )

    q.append(now)
    _total += 1


def state() -> dict:
    """For /health, so the limit is visible without reading the code."""
    return {
        "agent_calls_used": _total,
        "agent_calls_limit": TOTAL,
        "per_caller_hourly_limit": PER_IP,
    }
