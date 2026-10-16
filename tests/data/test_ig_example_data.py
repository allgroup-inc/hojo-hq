"""
Test: 3 test subsidies (one per template) have complete example data for IG posts.
"""

import json
import pytest


def test_example_subsidies_have_complete_data():
    """
    Verify 3 representative test subsidies (one per template) have:
    - ig_before_amount: positive, > ig_after_amount
    - ig_after_amount: non-negative, < ig_before_amount
    - ig_example_industry: set and non-empty

    These IDs are used as reference examples for IG post generation.
    """
    subsidies = json.load(open('data/subsidies.json'))
    items = subsidies['items']

    # 3 test subsidy IDs, one from each template
    test_ids = {
        # Template1: ~¥450万 max, realistic investment scenario
        "a0WJ200000CDYDCMA5": {
            "template": "template1",
            "example_industry": "農業",
            "before_amount": 4000000,    # ¥400万
            "after_amount": 1000000,     # ¥100万
        },
        # Template2: free support, Okinawa SME focus
        "okinawa_ric-3": {
            "template": "template2",
            "example_industry": "小売業",
            "before_amount": 1500000,    # ¥150万
            "after_amount": 0,           # free
        },
        # Template3: ¥1.5B max, large transformation
        "a0WJ200000CDNDnMAP": {
            "template": "template3",
            "example_industry": "製造業",
            "before_amount": 50000000,   # ¥5000万
            "after_amount": 15000000,    # ¥1500万
        },
    }

    for seido_id, expected in test_ids.items():
        item = next((s for s in items if s['id'] == seido_id), None)

        # Check subsidy exists
        assert item is not None, f"Test subsidy {seido_id} not found in data/subsidies.json"

        # Check template
        assert item.get('ig_template') == expected['template'], \
            f"{seido_id}: template mismatch (expected {expected['template']}, got {item.get('ig_template')})"

        # Check before/after amounts
        assert item.get('ig_before_amount') is not None and item['ig_before_amount'] > 0, \
            f"{seido_id}: ig_before_amount must be set and positive"
        assert item.get('ig_after_amount') is not None and item['ig_after_amount'] >= 0, \
            f"{seido_id}: ig_after_amount must be set and non-negative"
        assert item['ig_before_amount'] > item['ig_after_amount'], \
            f"{seido_id}: before ({item['ig_before_amount']}) must be > after ({item['ig_after_amount']})"

        # Check example industry
        assert item.get('ig_example_industry'), \
            f"{seido_id}: ig_example_industry must be set"
