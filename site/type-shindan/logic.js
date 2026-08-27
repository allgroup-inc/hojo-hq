/* タイプ診断 汎用エンジン(ケンショウ対象)
 * - データ(data.js)とエンジン(本ファイル)を分離した仕組み化の中核。
 *   AXES/QUESTIONS/TYPES の形式を満たすデータなら、別の診断(世帯版など)にもそのまま使える。
 * - ブラウザ(window.TypeShindan)/Node(module.exports)両対応のUMD形式。
 *   Node側は tests/type-shindan.test.mjs で検証される(CI必須)。
 */
(function (global) {
  "use strict";

  // データの整合性検査。ページ表示前とテストの両方で使う。
  // 前提: 各軸の質問数は奇数(同点を出さないため)。タイプは全組み合わせぶん定義されている。
  function validateConfig(config) {
    var errors = [];
    if (!config || !Array.isArray(config.AXES) || !Array.isArray(config.QUESTIONS) || !config.TYPES) {
      return { valid: false, errors: ["config の形式が不正です"] };
    }
    var letterOwner = {};
    config.AXES.forEach(function (ax) {
      if (!ax.id || !Array.isArray(ax.letters) || ax.letters.length !== 2) {
        errors.push("軸 " + (ax.id || "?") + " は letters を2つ持つ必要があります");
        return;
      }
      ax.letters.forEach(function (L) {
        if (letterOwner[L]) errors.push("記号 " + L + " が複数の軸で使われています");
        letterOwner[L] = ax.id;
      });
    });
    var perAxis = {};
    config.QUESTIONS.forEach(function (q, i) {
      var ax = config.AXES.filter(function (a) { return a.id === q.axis; })[0];
      if (!ax) { errors.push("質問" + (i + 1) + " の axis が未定義: " + q.axis); return; }
      perAxis[q.axis] = (perAxis[q.axis] || 0) + 1;
      if (!Array.isArray(q.options) || q.options.length !== 2) {
        errors.push("質問" + (i + 1) + " は選択肢を2つ持つ必要があります");
        return;
      }
      var letters = q.options.map(function (o) { return o.letter; }).sort();
      if (letters.join(",") !== ax.letters.slice().sort().join(",")) {
        errors.push("質問" + (i + 1) + " の選択肢の記号が軸 " + q.axis + " と一致しません");
      }
    });
    config.AXES.forEach(function (ax) {
      var n = perAxis[ax.id] || 0;
      if (n === 0) errors.push("軸 " + ax.id + " の質問がありません");
      if (n % 2 === 0 && n > 0) errors.push("軸 " + ax.id + " の質問数が偶数です(同点が起こり得ます)");
    });
    var expected = allCodes(config);
    expected.forEach(function (code) {
      if (!config.TYPES[code]) errors.push("タイプ " + code + " が未定義です");
    });
    Object.keys(config.TYPES).forEach(function (code) {
      if (expected.indexOf(code) === -1) errors.push("タイプ " + code + " は到達不能なコードです");
    });
    return { valid: errors.length === 0, errors: errors };
  }

  // 全タイプコード(軸の記号の直積)を軸の定義順で列挙する
  function allCodes(config) {
    var codes = [""];
    config.AXES.forEach(function (ax) {
      var next = [];
      codes.forEach(function (c) {
        ax.letters.forEach(function (L) { next.push(c + L); });
      });
      codes = next;
    });
    return codes;
  }

  // answers: 質問ごとに選んだ記号の配列(例: ["A","M","A", ...] 長さ=質問数)
  function resolve(config, answers) {
    if (!Array.isArray(answers) || answers.length !== config.QUESTIONS.length) {
      return { error: "回答数が一致しません(" + config.QUESTIONS.length + "問必要)" };
    }
    var counts = {};
    for (var i = 0; i < config.QUESTIONS.length; i++) {
      var q = config.QUESTIONS[i];
      var ok = q.options.some(function (o) { return o.letter === answers[i]; });
      if (!ok) return { error: "質問" + (i + 1) + " の回答が選択肢にありません: " + answers[i] };
      counts[answers[i]] = (counts[answers[i]] || 0) + 1;
    }
    var code = config.AXES.map(function (ax) {
      var a = counts[ax.letters[0]] || 0;
      var b = counts[ax.letters[1]] || 0;
      return a >= b ? ax.letters[0] : ax.letters[1];
    }).join("");
    return { code: code, counts: counts, type: config.TYPES[code] };
  }

  // 指定コードになる回答例を作る(テスト・eval用)
  function answersFor(config, code) {
    var byAxis = {};
    config.AXES.forEach(function (ax, i) { byAxis[ax.id] = code[i]; });
    return config.QUESTIONS.map(function (q) { return byAxis[q.axis]; });
  }

  var api = { validateConfig: validateConfig, allCodes: allCodes, resolve: resolve, answersFor: answersFor };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.TypeShindan = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
