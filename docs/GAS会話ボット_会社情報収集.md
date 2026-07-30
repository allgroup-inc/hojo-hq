# LINE会話ボット(会社情報収集) — 議事20260730 議題1「併用で採用」の実装

> ✅ **v1.2 稼働確認済み(2026-07-30 小柳さん実機テスト合格)**。
> 実装済み機能: ①会話収集(3問→台帳 経路line-chat) ②サイトフォーム一括送信の自動解析(経路line-form) ③通常メッセージへの受付返信(Default一律応答はOFFに変更済み・ボットが代役) ④diag遠隔診断(SHARED_TOKEN必須)。
> セットアップ時のハマりどころ: (a)LINEの「検証」ボタンはGASの302仕様で必ず失敗するが実動作は正常 (b)コード更新は「デプロイを管理→本番デプロイ(AKfycbx6SYv…)→✏️→新バージョン」で反映(新しいデプロイはURLが変わるので使わない) (c)UrlFetchApp追加時はGoogle再承認が必要。承認ポップアップがChromeにブロックされて無反応になることがある→script.google.comのポップアップ許可+myaccount.google.com/connectionsで旧承認を削除→エディタで▷実行→「外部サービスへの接続」を含めて許可。

目的: LINEトーク内で「会社名→代表者名→所在地」を会話形式で聞き取り、**企業台帳へ自動記録**する。
サイトのフォームは併用で残す(GA4で両者の完了率を並走比較)。

構成: LINE Webhook → 既存のGAS Webアプリ(台帳と同じプロジェクト・同じURL) → スプレッドシート「ミカタ企業台帳」

- 既存の台帳受信(診断POST)と**1つのdoPostに同居**させる(events配列があればLINE Webhook、tokenがあれば診断POST)
- 会話の途中状態はCacheService(30分)に保持。途中で「やめる」で中断可能
- 制約メモ: GASはHTTPヘッダーを読めないためLINE署名検証は不可(GASボットの一般的制約)。URLは秘匿運用+宛先チェックで代替

## セットアップ(小柳さん・約10分)

1. スプレッドシート「ミカタ企業台帳」→ 拡張機能 → Apps Script
2. コードを下の**完全版**でまるごと置き換え → 💾保存
3. 左メニュー⚙「プロジェクトの設定」→ スクリプト プロパティに追加:
   - `LINE_CHANNEL_ACCESS_TOKEN` = LINE Developersの「Messaging API設定」タブ最下部のチャネルアクセストークン(長期)を再コピー
   - (既存の `SHARED_TOKEN` はそのまま残す)
4. 右上「デプロイ」→「**デプロイを管理**」→ ✏️編集 → バージョン「**新バージョン**」→ デプロイ
   (**URLは変わらない**のでGitHub Secretsの変更は不要)
5. LINE Developers → 沖縄企業のミカタ(Messaging APIチャネル) → 「Messaging API設定」タブ:
   - Webhook URL = GASのウェブアプリURL(`https://script.google.com/macros/s/…/exec`)を貼る → 「検証」で成功を確認
   - 「**Webhookの利用**」を **ON**
6. LINE公式アカウント管理(manager.line.biz) → 自動応答 → 応答メッセージ:
   - 「会社情報登録」のキーワード応答を **OFF**(ボットと二重返信になるため。他の応答はそのまま)
7. テスト: 自分のLINEから `【会社情報登録】` と送信 → ボットの質問に答えて、台帳に1行増えれば完成

## コード(完全版・コード.gsをこれで置き換え)

```javascript
/**
 * ミカタ企業台帳 受信エンドポイント(統合版)
 * ① 診断ページ(LIFF)からのPOST → 台帳に1行追記
 * ② LINE Webhook(会話ボット) → 会社名/代表者名/所在地を聞き取り台帳に追記
 */
const SHEET_NAME = '台帳';
const HEADERS = [
  '受信日時', 'LINEユーザーID', 'LINE表示名',
  '会社名', '代表者名', '所在地',
  '市町村', '業種', '従業員数', '経営テーマ', '10年後',
  'マッチ件数', '承継シグナル', '融資シグナル', '経路',
];
const CONV_TTL_SEC = 1800; // 会話の途中状態は30分保持

function doPost(e) {
  let body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (_) {
    return json_({ ok: false, error: 'bad json' });
  }
  if (Array.isArray(body.events)) return handleLineWebhook_(body);
  return handleLedgerPost_(body);
}

/* ---------- ① 診断POST(既存機能・変更なし) ---------- */
function handleLedgerPost_(body) {
  const props = PropertiesService.getScriptProperties();
  const expected = props.getProperty('SHARED_TOKEN');
  if (!expected || body.token !== expected) {
    return json_({ ok: false, error: 'unauthorized' });
  }
  const a = body.answers || {};
  const themes = Array.isArray(a.themes) ? a.themes : [];
  const shokei = themes.includes('shokei') ||
    ['hikitsugi', 'joto'].includes(a.future) ? '●' : '';
  const yushi = themes.includes('shikin') ? '●' : '';
  getSheet_().appendRow([
    new Date(), String(body.userId || ''), String(body.displayName || ''),
    String(body.company || ''), String(body.ceo || ''), String(body.address || ''),
    String(a.area || ''), String(a.biz || ''), String(a.emp || ''),
    themes.join(','), String(a.future || ''),
    Number(body.matchedCount || 0), shokei, yushi,
    String(body.source || 'diagnosis'),
  ]);
  return json_({ ok: true });
}

/* ---------- ② LINE会話ボット ---------- */
function handleLineWebhook_(body) {
  (body.events || []).forEach(function (ev) {
    try {
      if (ev.type === 'message' && ev.message && ev.message.type === 'text') {
        routeMessage_(ev.source.userId, ev.message.text, ev.replyToken);
      }
    } catch (err) { /* 1件の失敗で全体を落とさない */ }
  });
  return json_({ ok: true });
}

function routeMessage_(userId, text, replyToken) {
  if (!userId) return;
  const cache = CacheService.getScriptCache();
  const key = 'conv_' + userId;
  const raw = cache.get(key);
  const t = String(text || '').trim();

  // トリガー: 【会社情報登録】(あいさつ文・リッチメニューのoaMessageと同じ語)
  if (/^【?会社情報登録】?$/.test(t)) {
    cache.put(key, JSON.stringify({ step: 'company' }), CONV_TTL_SEC);
    reply_(replyToken,
      'ありがとうございます!3つだけ教えてください😊\n\n' +
      '① まず「会社名」をお願いします(例: 株式会社◯◯)\n\n' +
      '※途中でやめる場合は「やめる」と送ってください');
    return;
  }

  if (!raw) return; // 会話中でなければ何もしない(既存のキーワード自動応答に任せる)

  if (t === 'やめる' || t === 'キャンセル') {
    cache.remove(key);
    reply_(replyToken, '中断しました。また登録する時は【会社情報登録】と送ってください🌺');
    return;
  }

  const st = JSON.parse(raw);
  if (st.step === 'company') {
    st.company = t; st.step = 'ceo';
    cache.put(key, JSON.stringify(st), CONV_TTL_SEC);
    reply_(replyToken, '② 次に「代表者名」をお願いします');
  } else if (st.step === 'ceo') {
    st.ceo = t; st.step = 'city';
    cache.put(key, JSON.stringify(st), CONV_TTL_SEC);
    reply_(replyToken, '③ 最後に「所在地の市町村」をお願いします(例: 那覇市)');
  } else if (st.step === 'city') {
    st.city = t;
    cache.remove(key);
    const profile = getProfile_(userId);
    getSheet_().appendRow([
      new Date(), userId, profile.displayName || '',
      st.company || '', st.ceo || '', st.city || '',
      st.city || '', '', '', '', '', 0, '', '', 'line-chat',
    ]);
    reply_(replyToken,
      '登録ありがとうございます!✅\n' +
      st.company + ' 様の情報を承りました。\n\n' +
      '貴社が使える可能性のある制度が出たら、締切の約1か月前からLINEでお知らせします🌺\n' +
      '専門家に相談したい時は【専門家相談】と送ってください。');
  }
}

function reply_(replyToken, text) {
  const token = PropertiesService.getScriptProperties()
    .getProperty('LINE_CHANNEL_ACCESS_TOKEN');
  if (!token || !replyToken) return;
  UrlFetchApp.fetch('https://api.line.me/v2/bot/message/reply', {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token },
    payload: JSON.stringify({ replyToken: replyToken, messages: [{ type: 'text', text: text }] }),
    muteHttpExceptions: true,
  });
}

function getProfile_(userId) {
  try {
    const token = PropertiesService.getScriptProperties()
      .getProperty('LINE_CHANNEL_ACCESS_TOKEN');
    const res = UrlFetchApp.fetch('https://api.line.me/v2/bot/profile/' + userId, {
      headers: { Authorization: 'Bearer ' + token },
      muteHttpExceptions: true,
    });
    return JSON.parse(res.getContentText());
  } catch (_) { return {}; }
}

/* ---------- 共通 ---------- */
function getSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(HEADERS);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
```

## 法務メモ
- 聞き取るのは会社名・代表者名・市町村のみ(サイトフォームと同一項目)。台帳は非公開を維持
- あいさつメッセージ・診断ページに利用目的は明示済み(制度案内・締切アラート・関連サービスのご案内)
