"""
pipeline/publish/transport.py — Chapter 8 Lab: mock SSH transport with
WPPublisher.py's real retry/backoff constants.

This is a reader-safe MOCK. It makes zero real network calls and zero
real SSH/SCP/wp-cli calls. It simulates a transport that fails N times
with a transient-pattern error, then succeeds (or exhausts its
attempts), so the Lab can watch the real retry mechanics play out
without a live host.

Mirrors, exactly, ~/Projects/MarketSectorPipeline/src/WPPublisher.py's
_retry_wrapper() [src: WPPublisher.py:25-52]:
  - max_attempts = 7
  - retries only on a case-insensitive substring match against one of
    the transient patterns below (taken verbatim from the real code)
  - exponential backoff: 2 ** attempt seconds -> 2, 4, 8, 16, 32, 64, 128

`sleep_scale` lets the Lab run in seconds instead of minutes while
still LOGGING the real, unscaled backoff numbers; pass
`real_timing=True` to actually sleep the true seconds (up to 2+4+8+
16+32+64 = 126s of sleep before the 7th and final attempt).
"""
import logging
import time

logger = logging.getLogger("transport_mock")

# Verbatim from WPPublisher._retry_wrapper [src: WPPublisher.py:33-39]
TRANSIENT_PATTERNS = [
    "connection refused",
    "connection reset",
    "timeout",
    "broken pipe",
    "connection timed out",
]

MAX_ATTEMPTS = 7  # WPPublisher.py:25 -- _retry_wrapper(..., max_attempts: int = 7)


class FakeTransientFailure(Exception):
    """Simulated transient SSH/SCP error. Never a real network error."""


def _simulated_op(attempt: int, fail_times: int) -> str:
    """One simulated SSH/SCP attempt. Fails with a transient-pattern
    error string for the first `fail_times` attempts, then succeeds."""
    if attempt <= fail_times:
        raise FakeTransientFailure(
            f"connection timed out (SIMULATED, attempt {attempt})"
        )
    return "OK"


def retry_wrapper(fail_times: int, max_attempts: int = MAX_ATTEMPTS,
                   sleep_scale: float = 0.01, real_timing: bool = False):
    """Mirrors WPPublisher._retry_wrapper's control flow: retries only
    on a transient-pattern match, with backoff = 2 ** attempt.

    Returns (success: bool, attempts_made: int, last_result_or_error: str).
    """
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = _simulated_op(attempt, fail_times)
            logger.info(f"[transport] attempt {attempt}/{max_attempts} succeeded")
            return True, attempt, result
        except FakeTransientFailure as e:
            last_err = str(e)
            err_lower = last_err.lower()
            is_transient = any(p in err_lower for p in TRANSIENT_PATTERNS)
            if is_transient and attempt < max_attempts:
                wait_time = 2 ** attempt  # real WPPublisher.py number, unscaled
                sleep_for = wait_time if real_timing else wait_time * sleep_scale
                logger.warning(
                    f"[transport] attempt {attempt}/{max_attempts} failed "
                    f"({last_err}); real backoff={wait_time}s "
                    f"(sleeping {sleep_for:.3f}s{' [scaled for Lab speed]' if not real_timing else ''})"
                )
                time.sleep(sleep_for)
                continue
            else:
                break
    logger.error(
        f"[transport] gave up after {max_attempts} attempts (max_attempts "
        f"exhausted, matching WPPublisher.py's real behavior): {last_err}"
    )
    return False, max_attempts, last_err


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Ch8 Lab: mock SSH transport exercising WPPublisher.py's "
                     "real retry/backoff constants (max_attempts=7, 2**attempt backoff)"
    )
    ap.add_argument("--fail-times", type=int, default=0,
                     help="number of leading attempts to fail with a transient error")
    ap.add_argument("--real-timing", action="store_true",
                     help="sleep the true seconds (2,4,8,...,128) instead of a scaled demo delay")
    ap.add_argument("--sleep-scale", type=float, default=0.01,
                     help="scale factor applied to the real backoff seconds when not using --real-timing")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    ok, attempts, result = retry_wrapper(
        args.fail_times, sleep_scale=args.sleep_scale, real_timing=args.real_timing
    )
    if ok:
        print(f"[transport] SUCCESS after {attempts} attempt(s): {result}")
        raise SystemExit(0)
    else:
        print(f"[transport] FAILED after {attempts} attempts "
              f"(exhausted max_attempts={MAX_ATTEMPTS}): {result}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
