"""Retry wrapper for transient network and service failures.

Two distinct classes of flakiness showed up during the sprint and both will
wreck a long unattended run:

* DNS for ``api.fortyguard.com`` intermittently fails to resolve from this
  machine -- twice in one day -- which surfaces as ``getaddrinfo failed``;
* the service itself returned 500s, 503s, and accepted-then-``Failed`` jobs
  across three separate outages in four days.

Failed tasks do not consume credits, so retrying is free. A *successful* call
whose download times out is billed, which is why the HTTP timeout is generous
elsewhere rather than something we retry into.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar

import requests

from .client import EmptyResultError

T = TypeVar("T")

# Transient: worth retrying.
TRANSIENT = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


def with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 4,
    base_delay: float = 3.0,
    label: str = "call",
) -> T:
    """Run ``fn``, retrying transient failures with exponential backoff.

    Deliberately does **not** retry :class:`EmptyResultError`. An empty result
    means the requested window has no data -- asking again will return empty
    again and bill again. That is a caller mistake, not a blip.
    """
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except EmptyResultError:
            raise
        except TRANSIENT as exc:
            last = exc
            reason = type(exc).__name__
        except Exception as exc:  # noqa: BLE001 - service-side failures vary
            msg = str(exc).lower()
            if not any(k in msg for k in ("failed", "500", "502", "503", "504", "timeout")):
                raise
            last = exc
            reason = type(exc).__name__

        if i == attempts - 1:
            break
        delay = base_delay * (2 ** i)
        print(f"    {label}: {reason}, retry {i + 1}/{attempts - 1} in {delay:.0f}s")
        time.sleep(delay)

    raise RuntimeError(f"{label} failed after {attempts} attempts: {last}") from last
