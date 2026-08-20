/* アポ管理台帳 Web Appの許可リスト照合・スタッフ役割の絞り込みロジック
 * ブラウザ相当のGAS(global.ApoAccess)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/apo_kanri_access.test.mjs で検証される。
 *
 * 個人Gmail運用(Workspaceドメインなし)のため、Web Appのアクセス設定だけでは
 * 利用者を限定できない。ApoRunner.gs が Session.getActiveUser().getEmail() で
 * 取得した実際のアクセス者のメールアドレスを、ここで「スタッフ」タブの登録
 * メールアドレスと照合する(glow-ma 三名体制レビュー2026-08-09と同方式)。
 */
(function (global) {
  "use strict";

  function normalizeEmail_(email) {
    return String(email || "").trim().toLowerCase();
  }

  function isAllowedEmail(email, staffRows) {
    var target = normalizeEmail_(email);
    if (!target) return false;
    return (staffRows || []).some(function (staff) {
      return normalizeEmail_(staff.email) === target;
    });
  }

  function resolveStaffName(email, staffRows) {
    var target = normalizeEmail_(email);
    var match = (staffRows || []).filter(function (staff) {
      return normalizeEmail_(staff.email) === target;
    })[0];
    return match && match.name ? match.name : "不明";
  }

  function listByRoles_(staffRows, roles) {
    return (staffRows || [])
      .filter(function (staff) { return roles.indexOf(staff.role) !== -1; })
      .map(function (staff) { return staff.name; });
  }

  // フォームの「担当営業」選択肢: 役割が営業・両方のスタッフ
  function listSalesStaff(staffRows) {
    return listByRoles_(staffRows, ["営業", "両方"]);
  }

  // フォームの「アポ入れ担当」選択肢: 役割がアポ入れ・両方のスタッフ
  function listSetterStaff(staffRows) {
    return listByRoles_(staffRows, ["アポ入れ", "両方"]);
  }

  function findStaffByName(name, staffRows) {
    var match = (staffRows || []).filter(function (staff) {
      return staff.name === name;
    })[0];
    return match || null;
  }

  function buildAccessDeniedHtml() {
    return "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">" +
      "<style>body{font-family:-apple-system,BlinkMacSystemFont,\"Hiragino Sans\"," +
      "\"Noto Sans JP\",Meiryo,sans-serif;padding:3rem 2rem;text-align:center;color:#11202c}" +
      "h1{font-size:1.15rem;margin:0 0 0.75rem}p{color:#4a5a66;line-height:1.7}</style></head>" +
      "<body><h1>アクセス権がありません</h1>" +
      "<p>このページを利用できるのは許可されたスタッフのみです。<br>" +
      "心当たりがある場合は管理者に確認してください。</p></body></html>";
  }

  var api = {
    isAllowedEmail: isAllowedEmail,
    resolveStaffName: resolveStaffName,
    listSalesStaff: listSalesStaff,
    listSetterStaff: listSetterStaff,
    findStaffByName: findStaffByName,
    buildAccessDeniedHtml: buildAccessDeniedHtml
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.ApoAccess = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
