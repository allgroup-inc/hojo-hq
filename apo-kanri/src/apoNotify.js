/* アポ管理台帳 Slack通知文面ビルダー
 * ブラウザ相当のGAS(global.ApoNotify)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/apo_kanri_notify.test.mjs で検証される。
 *
 * 通知は5種限定(新規・変更・キャンセル・申込・遅れそう)。リマインダー等は作らない
 * (設計書 三名体制裁定④: 通知過多で肝心の遅延通知が埋もれるのを防ぐ)。
 * 文面は通知一覧のプレビューで読み切れるよう、1行目に結論を置く。
 */
(function (global) {
  "use strict";

  function formatMention(slackUserId, fallbackName) {
    if (slackUserId) return "<@" + slackUserId + ">";
    return String(fallbackName || "担当者") + "さん";
  }

  function describeSlot_(apo) {
    return apo["日付"] + " " + apo["開始時刻"] + "〜(" + (apo["所要分"] || 60) + "分)";
  }

  function describePlace_(apo) {
    var place = apo["場所またはURL"] ? " @" + apo["場所またはURL"] : "";
    return apo["形式"] + place;
  }

  function buildNewAppointmentMessage(apo, mention) {
    return "📅 新規アポ " + describeSlot_(apo) + " " + apo["顧客名"] + "様\n" +
      "・" + describePlace_(apo) + " / 温度感: " + apo["温度感"] + "\n" +
      "・担当営業: " + mention + "(アポ入れ: " + apo["アポ入れ担当"] + ")";
  }

  function buildChangeMessage(apo, diff, mention) {
    return "🔁 アポ変更 " + apo["顧客名"] + "様(" + describeSlot_(apo) + ")\n" +
      "・変更: " + diff + "\n" +
      "・担当営業: " + mention;
  }

  // reason は「顧客都合」「自社都合」。未指定でも文面が壊れないようにする。
  function buildCancelMessage(apo, reason, mention) {
    var label = reason ? "差し戻し(" + reason + ")" : "差し戻し";
    return "❌ " + label + " " + apo["顧客名"] + "様(" + describeSlot_(apo) + ")\n" +
      "・担当営業: " + mention + "(アポ入れ: " + apo["アポ入れ担当"] + ")";
  }

  function buildSignupMessage(apo, mention) {
    return "🎉 申込 " + apo["顧客名"] + "様!\n" +
      "・" + describeSlot_(apo) + " / 担当営業: " + mention;
  }

  /**
   * 遅れそう通知。targets は ApoCore.buildDelayTargets の戻り値(時刻順)。
   * mentionResolver(アポ入れ担当名) → メンション文字列。
   * 後続アポの時刻は変更しない(通知のみ・判断は人間)。
   */
  function buildDelayMessage(salesName, minutes, targets, mentionResolver) {
    var head = "⏰ " + salesName + "さん +" + minutes + "分遅れ見込み";
    if (!targets || targets.length === 0) {
      return head + "\n・本日このあとに影響するアポはありません";
    }
    var lines = targets.map(function (apo) {
      return "・" + apo["開始時刻"] + " " + apo["顧客名"] + "様 → " +
        mentionResolver(apo["アポ入れ担当"]) + " 調整要否の確認をお願いします";
    });
    return head + "(影響しうる後続アポ " + targets.length + "件)\n" + lines.join("\n");
  }

  var MAX_SUBSTITUTE_LINES = 5;

  function mapsSearchUrl_(place) {
    return "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(place);
  }

  // Slackのリンク記法 <URL|表示名> は & < > がメタ文字、| はラベル区切り。
  // 自由入力の場所名をそのまま入れると記法が壊れるためエスケープする(2026-08-17レビュー指摘#9)
  function escSlackLabel_(text) {
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/\|/g, "¦");
  }

  function describeAdjacent_(label, record) {
    if (!record) return null;
    var place = record["場所またはURL"] || "";
    var placeText;
    if (record["形式"] === "オンライン" || /^https?:\/\//.test(place)) {
      placeText = "オンライン";
    } else if (place) {
      // 地図はリンクを開くだけで、位置情報は取得しない
      placeText = "<" + mapsSearchUrl_(place) + "|" + escSlackLabel_(place) + ">";
    } else {
      placeText = "場所未記入";
    }
    return label + " " + record["開始時刻"] + " " + placeText;
  }

  /**
   * キャンセル通知に付ける代打候補セクション(GPSレス版)。
   * candidates は ApoCore.buildSubstituteCandidates の戻り値。表示は最大5名。
   * どの候補に行ってもらうかの判断・連絡は人間が行う(自動アサインはしない)。
   */
  function buildSubstituteSection(candidates) {
    var head = "🧭 代打候補(この時間が空いている営業・前後の場所つき):";
    if (!candidates || candidates.length === 0) {
      return head + "\n・この時間が空いている営業がいません";
    }
    var lines = candidates.slice(0, MAX_SUBSTITUTE_LINES).map(function (candidate) {
      var parts = [
        describeAdjacent_("直前", candidate.before),
        describeAdjacent_("直後", candidate.after)
      ].filter(Boolean);
      var context = parts.length ? parts.join(" / ") : "この日の他アポなし";
      return "・" + candidate.owner + ": " + context;
    });
    return head + "\n" + lines.join("\n");
  }

  var api = {
    formatMention: formatMention,
    buildSubstituteSection: buildSubstituteSection,
    buildNewAppointmentMessage: buildNewAppointmentMessage,
    buildChangeMessage: buildChangeMessage,
    buildCancelMessage: buildCancelMessage,
    buildSignupMessage: buildSignupMessage,
    buildDelayMessage: buildDelayMessage
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.ApoNotify = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
