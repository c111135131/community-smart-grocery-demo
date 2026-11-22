"""Block until PostgreSQL accepts connections (used by the Docker entrypoint).

    python -m app.wait_for_db            # waits up to 60 s
    python -m app.wait_for_db --timeout 5

Exit code 0 once the database answers, 1 if it never does. Needed because
`docker compose` can start the backend container before PostgreSQL is ready to
accept connections.
"""
import argparse
import sys
import time
from collections.abc import Callable

from app.core.database import check_database


def wait_for_database(
    timeout_seconds: float = 60.0,
    interval_seconds: float = 1.0,
    check: Callable[[], bool] = check_database,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """Poll `check` until it returns True or the timeout passes. Returns the outcome."""
    deadline = clock() + timeout_seconds
    while True:
        if check():
            return True
        if clock() >= deadline:
            return False
        sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Wait for the database to accept connections.")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()
    print(f"Waiting for the database (up to {args.timeout:g}s)...", flush=True)
    if wait_for_database(args.timeout):
        print("Database is ready.", flush=True)
        return
    print("Database did not become ready in time.", file=sys.stderr, flush=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
