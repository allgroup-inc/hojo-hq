# -*- coding: utf-8 -*-
"""tests/test_guards.py のテスト(売上自動化 Task 5-6)。実行: python3 -m pytest tests/test_guards.py"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from build_facts import FactsError, FactsDict  # noqa: E402
from guards import Guard  # noqa: E402

# Note: NumberVerifier, BannedPhrasesChecker, SegmentFitChecker will be added in Tasks 2-4
