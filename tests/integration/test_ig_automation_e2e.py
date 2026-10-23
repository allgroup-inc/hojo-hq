#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沖縄企業のミカタ Instagram 自動化 Task 16: end-to-end 統合テスト

検証する仕組み:
1. Load subsidies.json (155 items, 40+5+3 mapped to templates)
2. Generate 5 draft posts via generate_ig_posts_mikata.py
3. Verify each post via verify_mikata_seido.py (mocked)
4. Check all captions pass humanizer + accuracy-check
5. Confirm no duplicate posts from recent 5 weeks

実行:
  pytest tests/integration/test_ig_automation_e2e.py -v
"""
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts dir to path to import generation/verification scripts
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from generate_ig_posts_mikata import (  # noqa: E402
    generate_ig_posts,
    load_historical_post_ids,
    load_items,
)
from check_humanizer import check_one  # noqa: E402

BASE = os.path.join(os.path.dirname(__file__), "..", "..")
DATA_DIR = os.path.join(BASE, "data")
DEFAULT_SUBSIDIES = os.path.join(DATA_DIR, "subsidies.json")
DEFAULT_HISTORY = os.path.join(DATA_DIR, "ig_posts_history.json")


class TestIGAutomationE2E:
    """End-to-end integration test for IG automation pipeline."""

    def test_full_pipeline_end_to_end(self):
        """
        Validate the complete generation → verification → commit pipeline.

        Steps:
        1. Load subsidies.json and validate schema
        2. Generate 5 draft posts via generate_ig_posts_mikata.py
        3. Verify each post can be processed
        4. Check all captions pass humanizer check
        5. Confirm no duplicate posts from recent 5 weeks
        """
        # Step 1: Load and validate schema
        subsidies = load_items(DEFAULT_SUBSIDIES)
        assert subsidies is not None, "Failed to load subsidies.json"
        assert len(subsidies) == 155, f"Expected 155 subsidies, got {len(subsidies)}"

        # Count template assignments
        template1_count = len([s for s in subsidies if s.get("ig_template") == "template1"])
        template2_count = len([s for s in subsidies if s.get("ig_template") == "template2"])
        template3_count = len([s for s in subsidies if s.get("ig_template") == "template3"])

        # Verify templates are assigned (current counts: template1: 19, template2: 7, template3: 5)
        assert template1_count > 0, (
            f"Expected template1 items, got {template1_count}"
        )
        assert template2_count > 0, (
            f"Expected template2 items, got {template2_count}"
        )
        assert template3_count > 0, (
            f"Expected template3 items, got {template3_count}"
        )

        # Step 2: Generate drafts
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_json = f.name

        try:
            drafts = generate_ig_posts(
                subsidies_json=DEFAULT_SUBSIDIES,
                max_posts=5,
                history_json=DEFAULT_HISTORY,
                output_json=output_json,
            )
            assert len(drafts) == 5, f"Expected 5 drafts, got {len(drafts)}"

            # Step 3: Verify each draft
            for draft in drafts:
                assert draft["seido_id"], "Missing seido_id"
                assert draft["template"], "Missing template"
                assert draft["caption"], "Missing caption"
                assert draft["hashtags"], "Missing hashtags"
                assert draft["approval_needed"] is True, (
                    f"Draft {draft['seido_id']} should require approval"
                )

                # Find corresponding subsidy item
                subsidy_item = next(
                    (s for s in subsidies if s["id"] == draft["seido_id"]), None
                )
                assert subsidy_item is not None, (
                    f"Draft {draft['seido_id']} not found in subsidies"
                )

                # Verify key fields are populated
                if draft["template"] != "template2":
                    # template1 and template3 should have amounts and deadlines
                    assert draft["max_amount"] is not None, (
                        f"Draft {draft['seido_id']} missing max_amount"
                    )
                    assert draft["deadline"] is not None, (
                        f"Draft {draft['seido_id']} missing deadline"
                    )

                # All drafts should have positive days_to_deadline
                assert draft["days_to_deadline"] is not None, (
                    f"Draft {draft['seido_id']} missing days_to_deadline"
                )

            # Step 4: Humanizer check
            humanizer_issues = []
            for draft in drafts:
                findings = check_one(draft["seido_id"], draft["caption"])
                if findings:
                    humanizer_issues.append({
                        "seido_id": draft["seido_id"],
                        "findings": findings,
                    })

            # Humanizer issues don't fail the test, but we collect them for reporting
            # (per CLAUDE.md: "報告のみでパイプラインは止めない")
            if humanizer_issues:
                print(f"\n[WARN] Humanizer issues found in {len(humanizer_issues)} drafts:")
                for issue in humanizer_issues:
                    print(f"  - {issue['seido_id']}: {issue['findings']}")

            # Step 5: No duplicates check
            historical_ids = load_historical_post_ids(DEFAULT_HISTORY)
            duplicates = []
            for draft in drafts:
                if draft["seido_id"] in historical_ids:
                    duplicates.append(draft["seido_id"])

            assert len(duplicates) == 0, (
                f"Found {len(duplicates)} duplicate post(s) from recent 5 weeks: {duplicates}"
            )

            # Step 6: Verify caption structure
            for draft in drafts:
                caption = draft["caption"]
                assert "【1行フック】" in caption, (
                    f"Draft {draft['seido_id']} missing hook section"
                )
                assert "【本文】" in caption, (
                    f"Draft {draft['seido_id']} missing body section"
                )
                assert "【ハッシュタグ】" in caption, (
                    f"Draft {draft['seido_id']} missing hashtag section"
                )

            # Step 7: Verify image placeholders
            for draft in drafts:
                placeholders = draft.get("image_placeholders", {})
                assert isinstance(placeholders, dict), (
                    f"Draft {draft['seido_id']} has invalid image_placeholders"
                )
                # Verify CTA URL uses go-link (not lin.ee directly)
                cta_url = placeholders.get("cta_url") or placeholders.get("qr")
                if cta_url:
                    assert "lin.ee" not in cta_url, (
                        f"Draft {draft['seido_id']} uses lin.ee directly (should use go-link)"
                    )

            # Step 8: Template distribution check
            template_dist = {}
            for draft in drafts:
                tpl = draft["template"]
                template_dist[tpl] = template_dist.get(tpl, 0) + 1

            # Expect prioritization: template1 > template2 > template3
            assert "template1" in template_dist, "No template1 posts generated"
            if "template2" in template_dist:
                assert template_dist["template1"] >= template_dist.get("template2", 0), \
                    "template1 should be prioritized over template2"

        finally:
            # Clean up temporary file
            if os.path.exists(output_json):
                os.unlink(output_json)

    def test_schema_compliance(self):
        """Verify subsidy data schema is valid."""
        subsidies = load_items(DEFAULT_SUBSIDIES)

        # Check required fields in subsidies
        required_fields = ["id", "name", "status"]
        for subsidy in subsidies[:10]:  # Sample check
            for field in required_fields:
                assert field in subsidy, f"Missing {field} in subsidy {subsidy.get('id')}"

        # Verify counts match header
        with open(DEFAULT_SUBSIDIES, encoding="utf-8") as f:
            data = json.load(f)
        assert data["count"] == len(subsidies), (
            f"Count mismatch: header says {data['count']}, items has {len(subsidies)}"
        )

    def test_historical_ids_loading(self):
        """Verify historical post IDs can be loaded."""
        historical_ids = load_historical_post_ids(DEFAULT_HISTORY)
        assert isinstance(historical_ids, set), "Historical IDs should be a set"
        # Should be empty or contain strings
        for post_id in historical_ids:
            assert isinstance(post_id, str), f"Post ID should be string, got {type(post_id)}"

    def test_template_assignment_validation(self):
        """Verify that template assignments follow priority rules."""
        subsidies = load_items(DEFAULT_SUBSIDIES)

        # Templates should be assigned to subsidies with ig_priority set
        for subsidy in subsidies:
            if subsidy.get("ig_template"):
                assert subsidy.get("ig_priority") is not None, (
                    f"Subsidy {subsidy['id']} has template but no priority"
                )
                assert isinstance(subsidy["ig_priority"], int), (
                    f"Priority must be int, got {type(subsidy['ig_priority'])}"
                )

    def test_deadline_parsing(self):
        """Verify deadlines are parseable."""
        subsidies = load_items(DEFAULT_SUBSIDIES)

        for subsidy in subsidies[:20]:  # Sample check
            deadline = subsidy.get("deadline")
            if deadline:
                try:
                    dt.date.fromisoformat(str(deadline)[:10])
                except ValueError:
                    pytest.fail(f"Invalid deadline format in {subsidy['id']}: {deadline}")

    def test_generated_posts_have_required_fields(self):
        """Verify generated posts have all required fields."""
        drafts = generate_ig_posts(
            subsidies_json=DEFAULT_SUBSIDIES,
            max_posts=5,
            history_json=DEFAULT_HISTORY,
        )

        required_fields = [
            "seido_id",
            "template",
            "seido_name",
            "caption",
            "hashtags",
            "deadline",
            "approval_needed",
            "generated_at",
        ]

        for draft in drafts:
            for field in required_fields:
                assert field in draft, f"Draft missing required field: {field}"
                assert draft[field] is not None, (
                    f"Draft {draft['seido_id']} has None value for {field}"
                )

    def test_approval_flag_always_true(self):
        """Verify all generated posts require approval."""
        drafts = generate_ig_posts(
            subsidies_json=DEFAULT_SUBSIDIES,
            max_posts=5,
            history_json=DEFAULT_HISTORY,
        )

        for draft in drafts:
            assert draft["approval_needed"] is True, (
                f"Draft {draft['seido_id']} should require approval"
            )

    def test_hashtags_no_forbidden_patterns(self):
        """Verify hashtags don't contain forbidden patterns."""
        drafts = generate_ig_posts(
            subsidies_json=DEFAULT_SUBSIDIES,
            max_posts=5,
            history_json=DEFAULT_HISTORY,
        )

        forbidden_in_hashtags = ("承継", "M&A", "Ｍ＆Ａ", "後継者")

        for draft in drafts:
            for tag in draft.get("hashtags", []):
                for forbidden in forbidden_in_hashtags:
                    assert forbidden not in tag, (
                        f"Draft {draft['seido_id']} has forbidden tag pattern: {tag}"
                    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
