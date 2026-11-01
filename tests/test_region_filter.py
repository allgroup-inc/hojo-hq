import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from region_filter import other_region  # noqa: E402


@pytest.mark.parametrize("name", [
    "いわき市診療所開設・承継支援補助金",
    "令和８年度東京港物流効率化等事業補助金",
    "京都市企業立地促進制度補助金",
    "【倉敷市】実証実験サポート事業",
    "休廃止鉱山鉱害防止等工事費補助金【北海道監督部】",
])
def test_other_region_is_excluded(name):
    assert other_region({"name": name})


@pytest.mark.parametrize("name", [
    "【沖縄】令和８年度中小企業最低賃金引上げ支援対策費補助金",
    "那覇市中小企業支援事業補助金",
    "うるま市創業支援補助金",
    "宮古島市省エネ設備導入補助金",
    "令和８年度都市ガス分野の災害対応・レジリエンス強化に係る支援事業費補助金",
    "海外市場開拓支援補助金",
    "令和8年度SDS電子化補助金",
])
def test_okinawa_or_nationwide_is_kept(name):
    assert not other_region({"name": name})
