# -*- coding: utf-8 -*-
"""市町村役場の窓口情報(住所・代表電話・開庁時間)— 2026-09-02 小柳さん発案
「申請の準備と、聞きに行く場所と営業時間がわかるように」の実装。
申請準備シート(generate_kit_pages)の「聞きに行く場所と時間」ボックスが参照する。

方針(正確性最優先):
- データは市町村役場(本庁)単位。担当課が別庁舎の場合があるため、表示側で必ず
  「課によっては別の建物の場合があります。お出かけ前に代表電話でご確認ください」を添える
- 開庁時間は各自治体の公式サイトで照合した表記のみ。公式で確認できなかった自治体は
  「要確認」(2026-09-02時点8村町: 宮古島・金武・本部・今帰仁・伊江・伊是名・座間味・粟国・渡名喜・与那国)
- 地図はGoogleマップの検索リンク(事実の断定を伴わない)
- 出典は各エントリの source_url(公式ドメイン)。年1回の棚卸しで再照合する(次回2027-09)
"""

MADOGUCHI = {
    "那覇市": {"hall": "那覇市役所(本庁舎)", "address": "沖縄県那覇市泉崎1丁目1番1号", "tel": "098-867-0111", "hours": "平日 8:30〜17:15", "hours_note": "閉庁日: 土日祝・慰霊の日(6/23)・年末年始(12/29〜1/3)", "source_url": "https://www.city.naha.okinawa.jp/admin/cityhall/annai/honchousha.html"},
    "宜野湾市": {"hall": "宜野湾市役所", "address": "沖縄県宜野湾市野嵩1丁目1番1号", "tel": "098-893-4411", "hours": "平日 8:30〜17:15", "hours_note": "閉庁日: 土日祝・慰霊の日・年末年始", "source_url": "https://www.city.ginowan.lg.jp/shisei/kokyoshisetsu/10/index.html"},
    "浦添市": {"hall": "浦添市役所", "address": "沖縄県浦添市安波茶一丁目1番1号", "tel": "098-876-1234", "hours": "平日 8:30〜12:00・13:00〜17:15", "hours_note": "12:00〜13:00は一部窓口のみ対応", "source_url": "https://www.city.urasoe.lg.jp/doc/65a7787f6e33864cca664826/"},
    "糸満市": {"hall": "糸満市役所", "address": "沖縄県糸満市潮崎町1丁目1番地", "tel": "098-840-8111", "hours": "平日 8:30〜12:00・13:00〜17:15", "hours_note": "一部窓口は昼休みも対応(お昼窓口)", "source_url": "https://www.city.itoman.lg.jp/life/6/27/151/"},
    "豊見城市": {"hall": "豊見城市役所", "address": "沖縄県豊見城市宜保一丁目1番地1", "tel": "098-850-0024", "hours": "平日 8:30〜17:15", "hours_note": "", "source_url": "https://www.city.tomigusuku.lg.jp/soshiki/15/1001/gyomuannai/9/1/1356.html"},
    "南城市": {"hall": "南城市役所", "address": "沖縄県南城市佐敷字新里1870番地", "tel": "098-917-5309", "hours": "平日 8:30〜12:00・13:00〜17:15", "hours_note": "昼休み(12:00〜13:00)は閉庁", "source_url": "https://www.city.nanjo.okinawa.jp/shisei/introduction/contact_list/"},
    "沖縄市": {"hall": "沖縄市役所", "address": "沖縄県沖縄市仲宗根町26番1号", "tel": "098-939-1212", "hours": "平日 8:30〜12:00・13:00〜17:15", "hours_note": "12:00〜13:00は一部窓口のみ対応", "source_url": "https://www.city.okinawa.okinawa.jp/k010-003/kurashi/todokedeshoumei/oshirase/5687.html"},
    "うるま市": {"hall": "うるま市役所(本庁舎)", "address": "沖縄県うるま市みどり町一丁目1番1号", "tel": "098-974-3111", "hours": "平日 8:30〜17:15", "hours_note": "", "source_url": "https://www.city.uruma.lg.jp/1001001000/shisetsu/p000001.html"},
    "名護市": {"hall": "名護市役所", "address": "沖縄県名護市港一丁目1番1号", "tel": "0980-53-1212", "hours": "平日 8:30〜17:15", "hours_note": "", "source_url": "https://www.city.nago.okinawa.jp/about/access/"},
    "宮古島市": {"hall": "宮古島市役所", "address": "沖縄県宮古島市平良字西里1140番地", "tel": "0980-72-3751", "hours": "要確認", "hours_note": "", "source_url": "https://www.city.miyakojima.lg.jp/soshiki/shityo/soumubu/soumu/"},
    "石垣市": {"hall": "石垣市役所", "address": "沖縄県石垣市字真栄里672番地", "tel": "0980-82-9911", "hours": "平日 8:30〜17:15", "hours_note": "12:00〜13:00は証明書発行業務のみの窓口あり", "source_url": "https://www.city.ishigaki.okinawa.jp/soshiki/shimin/5/4552.html"},
    "西原町": {"hall": "西原町役場", "address": "沖縄県中頭郡西原町字与那城140番地の1", "tel": "098-945-5011", "hours": "平日 8:30〜17:15", "hours_note": "昼休み(12:00〜13:00)は証明書発行等のみ", "source_url": "https://www.town.nishihara.okinawa.jp/soshiki/2/1057.html"},
    "与那原町": {"hall": "与那原町役場", "address": "沖縄県島尻郡与那原町字上与那原16番地", "tel": "098-945-2201", "hours": "平日 8:30〜17:15", "hours_note": "窓口受付は9:00〜16:30の案内あり", "source_url": "https://www.town.yonabaru.okinawa.jp/life/1/4/26/"},
    "南風原町": {"hall": "南風原町役場", "address": "沖縄県島尻郡南風原町字兼城686番地", "tel": "098-889-4415", "hours": "平日 8:30〜17:15", "hours_note": "", "source_url": "https://www.town.haebaru.lg.jp/soshiki/5/2133.html"},
    "八重瀬町": {"hall": "八重瀬町役場", "address": "沖縄県島尻郡八重瀬町字東風平1188番地", "tel": "098-998-2200", "hours": "平日 8:30〜17:15", "hours_note": "", "source_url": "https://www.town.yaese.lg.jp/docs/2014031200658/"},
    "北谷町": {"hall": "北谷町役場", "address": "沖縄県中頭郡北谷町桑江一丁目1番1号", "tel": "098-936-1234", "hours": "平日 8:30〜12:00・13:00〜17:15", "hours_note": "", "source_url": "https://www.chatan.jp/shisetsu/gyosei/chatancho-yakuba/index.html"},
    "嘉手納町": {"hall": "嘉手納町役場", "address": "沖縄県中頭郡嘉手納町字嘉手納588番地", "tel": "098-956-1111", "hours": "平日 8:30〜12:00・13:00〜17:15", "hours_note": "", "source_url": "https://www.town.kadena.okinawa.jp/ReceptionTime.html"},
    "読谷村": {"hall": "読谷村役場", "address": "沖縄県中頭郡読谷村字座喜味2901番地", "tel": "098-982-9200", "hours": "平日 8:30〜12:00・13:00〜17:15", "hours_note": "", "source_url": "https://www.vill.yomitan.okinawa.jp/gyosei_joho/yakuba_madoguchi/index.html"},
    "北中城村": {"hall": "北中城村役場", "address": "沖縄県中頭郡北中城村字喜舎場426番地2", "tel": "098-935-2233", "hours": "平日 8:30〜12:00・13:00〜17:15", "hours_note": "", "source_url": "https://www.vill.kitanakagusuku.lg.jp/kakuka/soumu/jouhou/319.html"},
    "中城村": {"hall": "中城村役場", "address": "沖縄県中頭郡中城村字当間585番地1", "tel": "098-895-2131", "hours": "平日 8:30〜17:15", "hours_note": "昼休み12:00〜13:00", "source_url": "https://www.vill.nakagusuku.okinawa.jp/overview/access/"},
    "金武町": {"hall": "金武町役場", "address": "沖縄県国頭郡金武町字金武1番地", "tel": "098-968-2111", "hours": "要確認", "hours_note": "届出窓口の受付は8:30〜11:30・13:00〜16:30の案内あり", "source_url": "https://www.town.kin.okinawa.jp/gyoseijoho/yakusho_madoguchiannai/index.html"},
    "恩納村": {"hall": "恩納村役場", "address": "沖縄県国頭郡恩納村字恩納2451番地", "tel": "098-966-1200", "hours": "平日 8:30〜17:15", "hours_note": "", "source_url": "https://www.vill.onna.okinawa.jp/sp/politics/office/"},
    "宜野座村": {"hall": "宜野座村役場", "address": "沖縄県国頭郡宜野座村字宜野座296番地", "tel": "098-968-5111", "hours": "平日 8:30〜17:15", "hours_note": "12:00〜13:00は窓口を閉める部署あり", "source_url": "https://www.vill.ginoza.okinawa.jp/"},
    "本部町": {"hall": "本部町役場", "address": "沖縄県国頭郡本部町字東5番地", "tel": "0980-47-2101", "hours": "要確認", "hours_note": "", "source_url": "https://www.town.motobu.okinawa.jp/doc/2025103100011/"},
    "今帰仁村": {"hall": "今帰仁村役場", "address": "沖縄県国頭郡今帰仁村字仲宗根219番地", "tel": "0980-56-2101", "hours": "要確認", "hours_note": "", "source_url": "https://www.nakijin.jp/"},
    "大宜味村": {"hall": "大宜味村役場", "address": "沖縄県国頭郡大宜味村字大兼久157番地", "tel": "0980-44-3003", "hours": "平日 8:30〜17:15", "hours_note": "", "source_url": "https://www.vill.ogimi.okinawa.jp/"},
    "東村": {"hall": "東村役場", "address": "沖縄県国頭郡東村字平良804番地", "tel": "0980-43-2201", "hours": "開庁日 8:30〜17:15", "hours_note": "", "source_url": "https://www.vill.higashi.okinawa.jp/gyoseijoho/yakusho_madoguchiannai/index.html"},
    "国頭村": {"hall": "国頭村役場", "address": "沖縄県国頭郡国頭村字辺土名121番地", "tel": "0980-41-2101", "hours": "平日 8:30〜17:15", "hours_note": "", "source_url": "https://www.vill.kunigami.okinawa.jp/"},
    "伊江村": {"hall": "伊江村役場", "address": "沖縄県国頭郡伊江村字東江前38番地", "tel": "0980-49-2001", "hours": "要確認", "hours_note": "", "source_url": "https://www.iejima.org/"},
    "伊平屋村": {"hall": "伊平屋村役場", "address": "沖縄県島尻郡伊平屋村字我喜屋251番地", "tel": "0980-46-2001", "hours": "平日 8:30〜12:00・13:00〜17:15", "hours_note": "昼休み(12:00〜13:00)は閉庁", "source_url": "https://www.vill.iheya.okinawa.jp/soshiki/2.html"},
    "伊是名村": {"hall": "伊是名村役場", "address": "沖縄県島尻郡伊是名村字仲田1687番地22", "tel": "0980-45-2001", "hours": "要確認", "hours_note": "", "source_url": "https://vill.izena.okinawa.jp/"},
    "久米島町": {"hall": "久米島町役場", "address": "沖縄県島尻郡久米島町字比嘉2870番地", "tel": "098-985-7121", "hours": "平日 8:30〜17:15", "hours_note": "", "source_url": "https://www.town.kumejima.okinawa.jp/docs/2017071200015/"},
    "渡嘉敷村": {"hall": "渡嘉敷村役場", "address": "沖縄県島尻郡渡嘉敷村字渡嘉敷183番地", "tel": "098-987-2321", "hours": "平日 8:30〜17:15", "hours_note": "", "source_url": "https://www.vill.tokashiki.okinawa.jp/gyoseijoho/tokashikisonyakubanitsuite/index.html"},
    "座間味村": {"hall": "座間味村役場", "address": "沖縄県島尻郡座間味村字座間味109番地", "tel": "098-987-2311", "hours": "要確認", "hours_note": "", "source_url": "https://www.vill.zamami.okinawa.jp/"},
    "粟国村": {"hall": "粟国村役場", "address": "沖縄県島尻郡粟国村字東483番地", "tel": "098-988-2016", "hours": "要確認", "hours_note": "", "source_url": "https://www.vill.aguni.okinawa.jp/10/67.html"},
    "渡名喜村": {"hall": "渡名喜村役場", "address": "沖縄県島尻郡渡名喜村1917番地3", "tel": "098-989-2002", "hours": "要確認", "hours_note": "", "source_url": "https://vill.tonaki.okinawa.jp/"},
    "南大東村": {"hall": "南大東村役場", "address": "沖縄県島尻郡南大東村字南144番地1", "tel": "09802-2-2001", "hours": "平日 8:15〜17:00", "hours_note": "", "source_url": "https://www.vill.minamidaito.okinawa.jp/life/5/25/113/"},
    "北大東村": {"hall": "北大東村役場", "address": "沖縄県島尻郡北大東村字中野218番地", "tel": "09802-3-4001", "hours": "平日 8:15〜17:00", "hours_note": "", "source_url": "https://vill.kitadaito.okinawa.jp/"},
    "多良間村": {"hall": "多良間村役場", "address": "沖縄県宮古郡多良間村字仲筋99番地2", "tel": "0980-79-2011", "hours": "平日 8:30〜17:15", "hours_note": "", "source_url": "https://www.vill.tarama.okinawa.jp/contact/"},
    "竹富町": {"hall": "竹富町役場", "address": "沖縄県石垣市美崎町11番地1", "tel": "0980-82-6191", "hours": "平日 8:30〜17:15", "hours_note": "役場は石垣島(石垣市美崎町)にあります", "source_url": "https://www.town.taketomi.lg.jp/administration/yakuba/"},
    "与那国町": {"hall": "与那国町役場", "address": "沖縄県八重山郡与那国町字与那国129番地", "tel": "0980-87-2241", "hours": "要確認", "hours_note": "", "source_url": "https://www.town.yonaguni.okinawa.jp/docs/2018080700015/"},
    "沖縄県": {"hall": "沖縄県庁", "address": "沖縄県那覇市泉崎1丁目2番2号", "tel": "098-866-2333", "hours": "平日 8:30〜17:15", "hours_note": "", "source_url": "https://www.pref.okinawa.jp/kensei/kencho/1014074/index.html"},
}


def get(area):
    """area名(市町村名 or 沖縄県)の窓口情報を返す。無ければ None(全国制度など)。"""
    return MADOGUCHI.get(area)


if __name__ == "__main__":
    assert len(MADOGUCHI) == 42, len(MADOGUCHI)
    assert get("那覇市")["tel"] == "098-867-0111"
    assert get("竹富町")["hours_note"]  # 石垣島所在の注記
    assert get("全国") is None
    print("fg_madoguchi self-test OK:", len(MADOGUCHI), "件")
