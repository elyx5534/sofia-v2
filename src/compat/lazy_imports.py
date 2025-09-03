from __future__ import annotations

import os

TEST_MODE = os.getenv("TEST_MODE", "0") == "1"


def is_test():
    return TEST_MODE
