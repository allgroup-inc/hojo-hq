"""
Pytest configuration for Block 2 integration tests
"""

import pytest
import os
from pathlib import Path

@pytest.fixture
def base_url():
    """API ベース URL"""
    return os.environ.get('BASE_URL', 'http://localhost:3000')

@pytest.fixture
def api_key():
    """API キー (オプション)"""
    return os.environ.get('API_KEY', None)

@pytest.fixture
def jwt_token():
    """JWT トークン"""
    return os.environ.get('JWT_TOKEN', 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test')

@pytest.fixture
def test_data_dir():
    """テストデータディレクトリ"""
    return Path(__file__).parent / "test_data"

def pytest_configure(config):
    """Pytest 初期化"""
    config.addinivalue_line(
        "markers", "integration: integration test"
    )
    config.addinivalue_line(
        "markers", "performance: performance test"
    )
    config.addinivalue_line(
        "markers", "business_axis: business axis connectivity test"
    )

def pytest_collection_modifyitems(config, items):
    """テスト収集時の調整"""
    for item in items:
        # すべてのテストに integration マーカーを追加
        item.add_marker(pytest.mark.integration)

        # パフォーマンステストにマーカーを追加
        if "performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)

        # 業務軸テストにマーカーを追加
        if "business_axis" in item.nodeid:
            item.add_marker(pytest.mark.business_axis)
