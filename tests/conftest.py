import os
import time

import pytest


def pytest_addoption(parser):
    parser.addoption("--total-shards", action="store", type=int, default=1)
    parser.addoption("--shard-index", action="store", type=int, default=1)


def pytest_collection_modifyitems(config, items):
    total = config.getoption("total_shards")
    index = config.getoption("shard_index")

    if total < 1:
        raise pytest.UsageError("--total-shards must be at least 1")
    if not 1 <= index <= total:
        raise pytest.UsageError("--shard-index must be 1..total-shards")

    # Round-robin assignment by collection order, with no duplicates.
    selected = [item for position, item in enumerate(items)
                if position % total == (index - 1)]
    deselected = [item for position, item in enumerate(items)
                  if position % total != (index - 1)]

    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = selected
    print(f"SHARD {index}/{total}: {len(selected)} selected, "
          f"{len(deselected)} deselected")


@pytest.fixture(autouse=True)
def simulate_nontrivial_test_duration():
    delay = float(os.getenv("PYTEST_DEMO_DELAY", "0"))
    if delay > 0:
        time.sleep(delay)
