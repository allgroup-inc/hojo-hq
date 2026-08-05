# LINE会話ボット(会社情報収集) — 議事20260730 議題1「併用で採用」の実装

> ✅ **v1.2 稼働中(2026-07-30 実機テスト合格)** / 🔜 **v1.4 準備済み(下のコード)・貼り替え待ち**
> v1.3の追加点: 会話の最後に**内容確認ステップ**(復唱→「はい」で記録)。雑談や質問文が会社名として台帳に誤記録されるのを防ぐ(議事_20260731 論点1)。
> **v1.4の追加点(2026-08-04 小柳さん決裁・相談転換③)**: 「相談」を含むメッセージの**一次受付**。自動で (a)お客様へ受付返信 (b)**小柳さんのLINEへ即時通知** (c)台帳へ経路`line-consult`で記録(P列にメッセージ本文)。フローは「ボット一次対応→小柳さん確認→嶺井さんへつなぐ→訪問」。ADMIN_USER_IDは貼り替え後に技術部がActionsから自動設定する(手作業不要)
> 実装済み機能: ①会話収集(3問+確認→台帳 経路line-chat) ②サイトフォーム一括送信の自動解析(line-form) ③通常メッセージへの受付返信(Default一律応答はOFF・ボットが代役) ④diag遠隔診断(SHARED_TOKEN必須・healthcheckが毎朝死活監視) ⑤相談一次受付(v1.4)
> セットアップのハマりどころ: (a)LINEの「検証」ボタンはGASの302仕様で必ず失敗するが実動作は正常 (b)コード更新は「デプロイ→デプロイを管理→本番デプロイ(AKfycbx6SYv…)→✏️→**新バージョン**→デプロイ」で反映(「新しいデプロイ」はURLが変わるので使わない) (c)UrlFetchApp等の新権限追加時はGoogle再承認が必要。承認ポップアップがブロックされ無反応になったら、script.google.comのポップアップ許可+myaccount.google.com/connectionsで旧承認を削除→エディタで▷実行→「外部サービスへの接続」を含めて許可

## v1.4への更新手順(小柳さん・5分)

1. スプレッドシート「ミカタ企業台帳」→ 拡張機能 → Apps Script
2. エディタで **Ctrl+A → Delete** → 下の完全版コードを貼り付け → **Ctrl+S**
3. **「デプロイ」→「デプロイを管理」→ 本番デプロイ(IDがAKfycbx6SYv…のもの)を選択 → ✏️ → バージョン「新バージョン」→ デプロイ**
4. LINEで `【会社情報登録】`→3問→**確認画面→「はい」**→台帳に行が増えれば完了
5. 貼り替えたら「v1.4貼った」と一言ください → 技術部がADMIN_USER_IDを自動設定し、「相談」と送って小柳さんのLINEに通知が届くまで確認します
6. (相談返信用) LINE公式アカウントの設定で「チャット」がONになっているか確認。ONならスマホのLINE公式アカウントアプリからお客様へ直接返信できます

## コード(完全版 v1.4・コード.gsをこれで置き換え)

```javascript
/**
 * ミカタ企業台帳 受信エンドポイント(統合版 v1.4)
 * ① 診断ページ(LIFF)からのPOST → 台帳に1行追記
 * ② LINE Webhook(会話ボット) → 会社名/代表者名/所在地を聞き取り、確認の上で台帳に追記
 * ③ サイトのフォーム一括送信(【会社情報登録】+3行)も解析して台帳に自動記録
 * ④ 通常メッセージへの受付返信もボットが担当(Default一律応答はOFFにする)
 * ⑤ diag: 技術部の遠隔診断用(SHARED_TOKEN必須)
 * ⑥ 相談一次受付(v1.4): 「相談」を含むメッセージ → 受付返信+管理者へ即時通知+台帳記録
 *    (2026-08-04 小柳さん決裁: ボット一次対応 → 小柳さん確認 → 嶺井さんへつなぐ → 訪問)
 */
const SHEET_NAME = '台帳';
const HEADERS = [
  '受信日時', 'LINEユーザーID', 'LINE表示名',
  '会社名', '代表者名', '所在地',
  '市町村', '業種', '従業員数', '経営テーマ', '10年後',
  'マッチ件数', '承継シグナル', '融資シグナル', '経路',
];
const CONV_TTL_SEC = 1800;
const RECEIPT_MSG =
  'メッセージを受け取りました🌺\n' +
  '内容を確認のうえ、担当より1営業日以内にご連絡いたします。\n\n' +
  '補助金や経営のことで聞きたいことがあれば、「相談」と一言送ってください。無料で、売り込みもしません。';
const CONSULT_MSG =
  'ご相談を受け付けました🌺\n' +
  '担当が内容を確認して、1営業日以内にこのLINEへ返信します。\n\n' +
  'よろしければ、聞きたいことを続けて送っておいてください。' +
  '(例: 「設備を入れ替えたいが使える制度はあるか」など)\n\n' +
  '※相談は無料です。申請の代行はできませんが、準備の進め方のご案内や、合う専門家のご紹介までお手伝いします。';

function doPost(e) {
  let body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (_) {
    return json_({ ok: false, error: 'bad json' });
  }
  if (body.diag === 'linetoken') return diagLineToken_(body);
  if (body.diag === 'setprop') return diagSetProp_(body);
  if (Array.isArray(body.events)) return handleLineWebhook_(body);
  return handleLedgerPost_(body);
}

/* 技術部の遠隔設定用(SHARED_TOKEN必須)。ADMIN_USER_ID等をチャットに出さずに登録する */
function diagSetProp_(body) {
  const props = PropertiesService.getScriptProperties();
  if (body.token !== props.getProperty('SHARED_TOKEN')) {
    return json_({ ok: false, error: 'unauthorized' });
  }
  if (!body.key || body.key === 'SHARED_TOKEN') {
    return json_({ ok: false, error: 'bad key' });
  }
  props.setProperty(String(body.key), String(body.value || ''));
  return json_({ ok: true, key: String(body.key) });
}

/* ---------- 診断用(技術部が遠隔で叩く。healthcheckの死活監視にも使用) ---------- */
function diagLineToken_(body) {
  const props = PropertiesService.getScriptProperties();
  if (body.token !== props.getProperty('SHARED_TOKEN')) {
    return json_({ ok: false, error: 'unauthorized' });
  }
  const t = props.getProperty('LINE_CHANNEL_ACCESS_TOKEN') || '';
  const res = UrlFetchApp.fetch('https://api.line.me/v2/bot/info', {
    headers: { Authorization: 'Bearer ' + t },
    muteHttpExceptions: true,
  });
  return json_({ ok: true, tokenLen: t.length, status: res.getResponseCode(), info: res.getContentText() });
}

/* ---------- ① 診断POST ---------- */
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
  const full = String(text || '');
  const t = full.trim();

  // ③ サイトのフォーム一括送信(【会社情報登録】+会社名/代表者名/所在地の行)
  if (/^【会社情報登録】\s*\n/.test(full)) {
    const company = (full.match(/会社名[：:]\s*(.+)/) || [])[1] || '';
    const ceo = (full.match(/代表者名[：:]\s*(.+)/) || [])[1] || '';
    const city = (full.match(/所在地[：:]\s*(.+)/) || [])[1] || '';
    const profile = getProfile_(userId);
    getSheet_().appendRow([
      new Date(), userId, profile.displayName || '',
      company.trim(), ceo.trim(), city.trim(),
      city.trim(), '', '', '', '', 0, '', '', 'line-form',
    ]);
    reply_(replyToken,
      '登録ありがとうございます!✅\n' +
      (company.trim() || '貴社') + ' 様の情報を承りました。\n\n' +
      '貴社が使える可能性のある制度が出たら、締切の約1か月前からLINEでお知らせします🌺\n' +
      '専門家に相談したい時は【専門家相談】と送ってください。');
    return;
  }

  // 会話トリガー(トリガー語のみの送信)
  if (/^【?会社情報登録】?$/.test(t)) {
    cache.put(key, JSON.stringify({ step: 'company' }), CONV_TTL_SEC);
    reply_(replyToken,
      'ありがとうございます!3つだけ教えてください😊\n\n' +
      '① まず「会社名」をお願いします(例: 株式会社◯◯)\n\n' +
      '※途中でやめる場合は「やめる」と送ってください');
    return;
  }

  if (raw) {
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
      // v1.3: すぐ記録せず、内容を復唱して確認を取る(雑談等の誤記録防止)
      st.city = t; st.step = 'confirm';
      cache.put(key, JSON.stringify(st), CONV_TTL_SEC);
      reply_(replyToken,
        '内容の確認です😊\n\n' +
        '会社名：' + st.company + '\n' +
        '代表者名：' + st.ceo + '\n' +
        '所在地：' + st.city + '\n\n' +
        'この内容でよろしければ「はい」、\n直す場合は「やり直す」と送ってください');
    } else if (st.step === 'confirm') {
      if (t === 'はい' || t === 'ハイ' || t === 'OK' || t === 'ok') {
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
      } else if (t === 'やり直す' || t === 'やりなおす' || t === 'やり直し') {
        cache.put(key, JSON.stringify({ step: 'company' }), CONV_TTL_SEC);
        reply_(replyToken, 'では最初からどうぞ😊\n\n① まず「会社名」をお願いします');
      } else {
        reply_(replyToken, '「はい」または「やり直す」でお答えください😊\n(登録をやめる場合は「やめる」)');
      }
    }
    return;
  }

  // キーワード応答(専門家相談・事業承継相談)は管理画面の自動応答が返信する。
  // v1.4: 返信は任せるが、小柳さんへの通知と台帳記録はこちらで行う
  if (/^【?(専門家相談|事業承継相談)】?$/.test(t)) {
    recordConsult_(userId, t, null);
    return;
  }

  // ⑥ 相談一次受付(v1.4): 「相談」を含むメッセージは相談として受け付ける
  if (/相談/.test(t)) {
    recordConsult_(userId, t, replyToken);
    return;
  }

  // ⑥' 相談モード中(受付から6時間)の続きのメッセージも、そのまま小柳さんへ転送する
  if (cache.get('consult_' + userId)) {
    notifyAdmin_('📞【相談の続き】\nお名前: ' + (getProfile_(userId).displayName || '') + '\n内容: ' + t);
    reply_(replyToken, '承りました。担当からの返信をお待ちください🌺');
    return;
  }

  // ④ 通常メッセージ: 受付返信(Default一律応答の代役)。
  reply_(replyToken, RECEIPT_MSG);
}

/* ⑥ 相談の一次受付: 受付返信+小柳さんへ即時通知+台帳に経路line-consultで記録 */
function recordConsult_(userId, text, replyToken) {
  const profile = getProfile_(userId);
  const name = profile.displayName || '(表示名なし)';
  // 相談モード(6時間): この間の続きのメッセージも管理者へ転送する
  CacheService.getScriptCache().put('consult_' + userId, '1', 21600);
  // 台帳16列目(P列)に相談メッセージ本文を残す(相談件数のKPI集計にも使う)
  getSheet_().appendRow([
    new Date(), userId, name,
    '', '', '', '', '', '', '', '', 0, '', '', 'line-consult', text,
  ]);
  if (replyToken) reply_(replyToken, CONSULT_MSG);
  notifyAdmin_(
    '📞【相談の一次受付】\n' +
    'お名前: ' + name + '\n' +
    '内容: ' + text + '\n\n' +
    '台帳に記録済み(経路line-consult)。\n' +
    '返信はLINE公式アカウントアプリのチャットから。対応後、必要なら嶺井さんへおつなぎください。');
}

/* 管理者(小柳さん)のLINEへプッシュ通知。ADMIN_USER_ID未設定時は静かにスキップ */
function notifyAdmin_(text) {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('LINE_CHANNEL_ACCESS_TOKEN');
  const admin = props.getProperty('ADMIN_USER_ID');
  if (!token || !admin) return;
  UrlFetchApp.fetch('https://api.line.me/v2/bot/message/push', {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token },
    payload: JSON.stringify({ to: admin, messages: [{ type: 'text', text: text }] }),
    muteHttpExceptions: true,
  });
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
