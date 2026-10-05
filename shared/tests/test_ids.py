import threading
from itertools import pairwise

from lms_common import ids
from lms_common.ids import new_public_id, parse_public_id


def test_generated_ids_round_trip() -> None:
    first = new_public_id()
    assert parse_public_id(str(first)) == first


def test_ids_are_strictly_increasing_even_within_one_millisecond() -> None:
    burst = [new_public_id() for _ in range(50_000)]  # far more than fit in distinct milliseconds
    assert all(later > earlier for earlier, later in pairwise(burst))
    assert len(set(burst)) == len(burst)


def test_ids_stay_increasing_and_unique_when_the_clock_steps_back(monkeypatch) -> None:
    before = new_public_id()
    monkeypatch.setattr(ids.time, "time", lambda: (ids._EPOCH_MS + 1_000) / 1000)  # long ago
    after = [new_public_id() for _ in range(5)]
    assert after[0] > before and after == sorted(set(after))


def test_ids_from_many_threads_never_collide() -> None:
    results: list[list[int]] = []

    def work() -> None:
        results.append([new_public_id() for _ in range(5_000)])

    threads = [threading.Thread(target=work) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    everything = [value for chunk in results for value in chunk]
    assert len(set(everything)) == len(everything) == 40_000
    assert all(chunk == sorted(chunk) for chunk in results)  # each thread saw them in increasing order


def test_ids_are_still_random_in_their_low_bits() -> None:
    """Monotonic must not mean guessable: consecutive ids after a pause are not simply +1."""
    import time

    first = new_public_id()
    time.sleep(0.01)
    second = new_public_id()
    assert second - first > 1 and second >> 22 > first >> 22  # a later millisecond, freshly random low bits


def test_ids_keep_the_public_shape() -> None:
    value = new_public_id()
    assert 10 <= len(str(value)) <= 19 and value < 2**63


def test_parse_rejects_malformed_values() -> None:
    assert parse_public_id("not-a-number") is None
    assert parse_public_id("0123") is None  # leading zero
    assert parse_public_id(None) is None
    assert parse_public_id(12345) is None  # must be a string
