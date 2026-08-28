"""A spend guard for the model-backed endpoints.

Every request to ``/api/agent`` costs real money on somebody's OpenAI key. That is
fine on localhost and not fine behind a public tunnel URL, which is where this
gets shared with teammates and, in principle, with anyone who learns the address.

So the agent endpoints carry two ceilings: a per-caller allowance so one person
cannot loop a script, and an everyone-together budget so the worst case is
bounded no matter how many callers appear.

Both are rolling windows rather than lifetime counters. A lifetime counter was
the first version and it is wrong for anything deployed: the site sits behind a
real hostname for days, quietly burns through its budget, and then refuses every
question until somebody notices and restarts it. A dead agent during judging
looks exactly like a broken product. A rolling budget recovers on its own.

Both limits read from the environment so the deployment can choose its own
appetite without a code change.

Deliberately in-process and dependency-free. A shared store would be the right
answer for several instances behind a load balancer; there is one instance behind
Caddy, so a shared store would be more moving parts than the problem deserves.
The cost of that choice is that the budget resets on restart, which is the safe
direction to be wrong in.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque

# Per caller, in a rolling window.
PER_IP = int(os.getenv("RESPITE_LIMIT_PER_IP", "25"))
WINDOW_SECONDS = int(os.getenv("RESPITE_LIMIT_WINDOW_SECONDS", "3600"))

# Everyone together, in a longer rolling window.
TOTAL = int(os.getenv("RESPITE_LIMIT_TOTAL", "300"))
TOTAL_WINDOW_SECONDS = int(os.getenv("RESPITE_LIMIT_TOTAL_WINDOW_SECONDS", "86400"))


def _window_label(seconds: int) -> str:
    """Human wording for the budget window, since it is configurable.

    Integer hours read as "0 hours" for anything under an hour, which is the sort
    of detail that makes a message look broken to the person it is aimed at.
    """
    if seconds >= 7200:
        return f"{seconds // 3600} hours"
    if seconds >= 3600:
        return "hour"
    minutes = max(1, seconds // 60)
    return f"{minutes} minutes" if minutes > 1 else "minute"

_hits: dict[str, deque[float]] = defaultdict(deque)
_all: deque[float] = deque()


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


def _expire(q: deque, now: float, window: float) -> None:
    while q and now - q[0] > window:
        q.popleft()


def check(request) -> None:
    """Raise :class:`RateLimited` if this call should not be spent."""
    now = time.time()

    _expire(_all, now, TOTAL_WINDOW_SECONDS)
    if len(_all) >= TOTAL:
        wait = _window_label(int(TOTAL_WINDOW_SECONDS - (now - _all[0])))
        raise RateLimited(
            f"This instance has answered {TOTAL} agent questions in the last "
            f"{_window_label(TOTAL_WINDOW_SECONDS)}, which is its budget. Some of it "
            f"frees up again in about {wait}. Every measurement, the map and the charts "
            "on this page are unaffected."
        )

    who = caller(request)
    q = _hits[who]
    _expire(q, now, WINDOW_SECONDS)

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
    _all.append(now)


def state() -> dict:
    """For /health, so the limit is visible without reading the code."""
    _expire(_all, time.time(), TOTAL_WINDOW_SECONDS)
    return {
        "agent_calls_used": len(_all),
        "agent_calls_limit": TOTAL,
        "agent_calls_window_hours": TOTAL_WINDOW_SECONDS // 3600,
        "per_caller_hourly_limit": PER_IP,
    }
