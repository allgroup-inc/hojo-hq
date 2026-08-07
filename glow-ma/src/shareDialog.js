/* GLOW企業リレーション台帳 対面連携(Slack DM)のスタッフ選択ダイアログHTML組み立て
 * ブラウザ相当のGAS(global.GlowShareDialog)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_shareDialog.test.mjs で検証される。
 *
 * ShareRunner.gs の showShareDialog がこの関数の戻り値を
 * HtmlService.createHtmlOutput に渡してモーダルダイアログとして表示する。
 * google.script.run 経由で ShareRunner.gs の shareCompanyWithStaff を呼び出す。
 */
(function (global) {
  "use strict";

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  var BASE_STYLE = [
    "*{box-sizing:border-box}",
    "body{margin:0;padding:1.25rem;",
    "font-family:-apple-system,BlinkMacSystemFont,\"Hiragino Sans\",\"Hiragino Kaku Gothic ProN\",\"Noto Sans JP\",Meiryo,sans-serif;",
    "color:#1f2933;background:#fff;font-size:0.9rem}",
    "h2{margin:0 0 0.75rem;font-size:1.02rem}",
    ".empty{color:#5c6773;line-height:1.7}",
    "fieldset{border:1px solid #d8dbe0;border-radius:0.4rem;margin:0 0 0.9rem;padding:0.6rem 0.8rem;",
    "max-height:9rem;overflow-y:auto}",
    "legend{font-size:0.78rem;color:#5c6773;padding:0 0.3rem}",
    "label.staff-row{display:flex;align-items:center;gap:0.5rem;padding:0.25rem 0;cursor:pointer}",
    "textarea{width:100%;min-height:4rem;padding:0.5rem;border:1px solid #d8dbe0;border-radius:0.4rem;",
    "font:inherit;resize:vertical;margin-bottom:0.9rem}",
    "button{padding:0.55rem 1.4rem;border:0;border-radius:0.4rem;background:#33475b;color:#fff;",
    "font:inherit;font-weight:700;cursor:pointer}",
    "button:disabled{opacity:0.5;cursor:default}",
    ".status{margin-top:0.75rem;font-size:0.82rem;line-height:1.6;white-space:pre-wrap}",
    ".status.error{color:#b3261e}",
    ".status.ok{color:#0a7a3d}"
  ].join("");

  /**
   * companyName/companyId: 連携対象の企業。staffList: [{name, slackUserId}, ...]
   * (「有効」列がtrueのスタッフのみを呼び出し側で絞り込んで渡すこと)
   */
  function buildStaffSelectionHtml(companyName, companyId, staffList) {
    var safeCompanyName = escapeHtml(companyName || "(社名未登録)");
    var safeCompanyId = escapeHtml(companyId || "");
    var list = staffList || [];

    if (list.length === 0) {
      return "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\"><style>" + BASE_STYLE + "</style></head>" +
        "<body><h2>" + safeCompanyName + " を連携</h2>" +
        "<p class=\"empty\">連携できるスタッフが登録されていません。「スタッフ」タブに氏名とSlack User IDを登録し、" +
        "「有効」列にチェックを入れてください。</p></body></html>";
    }

    var checkboxes = list.map(function (staff) {
      var safeName = escapeHtml(staff.name);
      var safeSlackId = escapeHtml(staff.slackUserId);
      return "<label class=\"staff-row\"><input type=\"checkbox\" value=\"" + safeSlackId + "\">" + safeName + "</label>";
    }).join("");

    return "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\"><style>" + BASE_STYLE + "</style></head>" +
      "<body>" +
      "<h2>" + safeCompanyName + " を連携</h2>" +
      "<fieldset><legend>連携先スタッフ(複数選択可)</legend>" + checkboxes + "</fieldset>" +
      "<textarea id=\"note\" placeholder=\"今の状況を一言(任意。例: 後継者の話をしています)\"></textarea>" +
      "<button id=\"sendBtn\">連携する</button>" +
      "<div class=\"status\" id=\"status\"></div>" +
      "<script>" +
      "var COMPANY_ID = " + JSON.stringify(String(companyId || "")) + ";" +
      "document.getElementById('sendBtn').addEventListener('click', function(){" +
      "var ids = Array.prototype.slice.call(document.querySelectorAll('input[type=checkbox]:checked')).map(function(el){return el.value;});" +
      "if(ids.length === 0){ setStatus('連携先を1人以上選択してください。', 'error'); return; }" +
      "var note = document.getElementById('note').value;" +
      "var btn = document.getElementById('sendBtn'); btn.disabled = true;" +
      "setStatus('送信しています…', '');" +
      "google.script.run.withSuccessHandler(function(result){" +
      "btn.disabled = false; setStatus(result, 'ok');" +
      "}).withFailureHandler(function(error){" +
      "btn.disabled = false; setStatus('送信に失敗しました: ' + (error && error.message ? error.message : error), 'error');" +
      "}).shareCompanyWithStaff(COMPANY_ID, ids, note);" +
      "});" +
      "function setStatus(text, cls){" +
      "var el = document.getElementById('status'); el.textContent = text; el.className = 'status' + (cls ? ' ' + cls : '');" +
      "}" +
      "<\/script>" +
      "</body></html>";
  }

  var api = {
    buildStaffSelectionHtml: buildStaffSelectionHtml
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowShareDialog = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
