/* GLOW企業リレーション台帳 対面連携(Slack DM)のメッセージ組み立てロジック
 * ブラウザ相当のGAS(global.GlowShareContent)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_shareContent.test.mjs で検証される。
 *
 * 2026-08-07 glow-ma-triangle-review確定(論点: 企業情報のSlack DM即時連携機能):
 * - 連絡不要(DNC)企業でも社内共有自体は禁止しない(DNCは対外接触の制限)。
 *   ただし誤解を防ぐため、メッセージ先頭に必ず警告を入れる
 * - 関係メモは機微な私的情報を含み得るため、全文ではなく先頭
 *   RELATION_MEMO_MAX_LENGTH 文字に切り詰めて送る(全文はスプレッドシート側で確認する運用)
 * - 「誰が連携したか」を可視化して抑止力にするため、送信者(Session.getActiveUser().getEmail())を
 *   メッセージ本文に必ず含める
 */
(function (global) {
  "use strict";

  var RELATION_MEMO_MAX_LENGTH = 100;

  function truncate(text, maxLength) {
    var value = String(text || "");
    if (value.length <= maxLength) return value;
    return value.slice(0, maxLength) + "…";
  }

  /**
   * 住所からGoogleマップの検索リンクを組み立てる。住所が空なら空文字列を返す。
   */
  function buildMapsUrl(address) {
    if (!address) return "";
    return "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(address);
  }

  /**
   * Slack DMで送る企業情報メッセージを組み立てる。
   * options.note: 対面中の状況を伝える一言メモ(任意)
   * options.senderEmail: 連携を実行した本人のメールアドレス(Session.getActiveUser().getEmail())
   */
  function buildShareMessage(record, options) {
    options = options || {};
    var lines = [];
    lines.push("【企業連携】" + (record["会社名"] || "(社名未登録)") +
      "(" + (record["業種"] || "業種不明") + "・" + (record["ランク"] || "-") + "ランク)");

    if (record["連絡不要"] === true) {
      lines.push("⚠ この企業は「連絡不要」(架電禁止)に設定されています。社内共有のみにとどめ、本人への再架電はしないでください。");
    }

    lines.push("現在ステージ: " + (record["現在ステージ"] || "未設定"));

    var mapsUrl = buildMapsUrl(record["所在地"]);
    if (mapsUrl) {
      lines.push("地図: " + mapsUrl);
    }

    if (record["電話番号"]) lines.push("電話番号(代表): " + record["電話番号"]);
    if (record["携帯番号"]) lines.push("携帯番号(窓口直通): " + record["携帯番号"]);
    if (record["窓口担当者名"]) lines.push("窓口担当者名: " + record["窓口担当者名"]);

    if (record["関係メモ"]) {
      lines.push("関係メモ: " + truncate(record["関係メモ"], RELATION_MEMO_MAX_LENGTH));
    }

    if (options.note) {
      lines.push("");
      lines.push("今の状況: " + options.note);
    }

    lines.push("");
    lines.push("送信者: " + (options.senderEmail || "不明"));

    return lines.join("\n");
  }

  var api = {
    RELATION_MEMO_MAX_LENGTH: RELATION_MEMO_MAX_LENGTH,
    buildMapsUrl: buildMapsUrl,
    buildShareMessage: buildShareMessage
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowShareContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
