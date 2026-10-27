import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const cti = require("../glow-ma/src/ctiContent.js");

test("mapCallTypeToInteractionType: PV発信(2)は電話", () => {
  assert.equal(cti.mapCallTypeToInteractionType(2), "電話");
});

test("mapCallTypeToInteractionType: PD発信(3)は電話", () => {
  assert.equal(cti.mapCallTypeToInteractionType("3"), "電話");
});

test("mapCallTypeToInteractionType: 着信(1)は入電", () => {
  assert.equal(cti.mapCallTypeToInteractionType(1), "入電");
});

test("mapCallTypeToInteractionType: 内線(0)はnull", () => {
  assert.equal(cti.mapCallTypeToInteractionType(0), null);
});

test("mapCallTypeToInteractionType: 未知の値はnull", () => {
  assert.equal(cti.mapCallTypeToInteractionType(9), null);
});

test("flattenBlueBeanCalls: dataの各entryのcallsを1次元に展開し、内線(call_type=0)を除外する", () => {
  const response = {
    result: "OK",
    data: [
      {
        master: { name: "テスト商事" },
        calls: [
          { group_callid: "g1", call_type: 2, phone: "0980000001" },
          { group_callid: "g2", call_type: 0, phone: "0980000002" }
        ]
      },
      {
        master: { name: "サンプル工業" },
        calls: [{ group_callid: "g3", call_type: 1, phone: "0980000003" }]
      }
    ]
  };
  const flattened = cti.flattenBlueBeanCalls(response);
  assert.equal(flattened.length, 2);
  assert.deepEqual(flattened.map((c) => c.group_callid), ["g1", "g3"]);
});

test("flattenBlueBeanCalls: resultがOK以外なら空配列", () => {
  assert.deepEqual(cti.flattenBlueBeanCalls({ result: "ERROR", code: "E002" }), []);
});

test("flattenBlueBeanCalls: レスポンスがnull/undefinedでも空配列", () => {
  assert.deepEqual(cti.flattenBlueBeanCalls(null), []);
  assert.deepEqual(cti.flattenBlueBeanCalls(undefined), []);
});

test("flattenBlueBeanCalls: dataが無い場合は空配列", () => {
  assert.deepEqual(cti.flattenBlueBeanCalls({ result: "OK" }), []);
});

const COMPANIES = [
  { "企業ID": "C001", "会社名": "テスト商事", "電話番号": "098-000-0001", "携帯番号": "" },
  { "企業ID": "C002", "会社名": "サンプル工業", "電話番号": "", "携帯番号": "090-1234-5678" },
  { "企業ID": "C003", "会社名": "共有電話商事A", "電話番号": "098-999-9999", "携帯番号": "" },
  { "企業ID": "C004", "会社名": "共有電話商事B", "電話番号": "098-999-9999", "携帯番号": "" }
];

test("matchCompanyByPhone: 電話番号列で一致する企業を返す(記号は無視)", () => {
  const matched = cti.matchCompanyByPhone(COMPANIES, "0980000001");
  assert.equal(matched["企業ID"], "C001");
});

test("matchCompanyByPhone: 携帯番号列でも一致する", () => {
  const matched = cti.matchCompanyByPhone(COMPANIES, "09012345678");
  assert.equal(matched["企業ID"], "C002");
});

test("matchCompanyByPhone: 一致する企業が無ければnull", () => {
  assert.equal(cti.matchCompanyByPhone(COMPANIES, "0000000000"), null);
});

test("matchCompanyByPhone: 同一電話番号を複数企業が持つ場合は誤記載防止のためnull", () => {
  assert.equal(cti.matchCompanyByPhone(COMPANIES, "0989999999"), null);
});

test("matchCompanyByPhone: 空文字・未定義の電話番号はnull", () => {
  assert.equal(cti.matchCompanyByPhone(COMPANIES, ""), null);
  assert.equal(cti.matchCompanyByPhone(COMPANIES, undefined), null);
});

const MATCHED_COMPANY = COMPANIES[0];
const COMPLETED_OUTBOUND_CALL = {
  group_callid: "g100", call_type: 2, phone: "0980000001",
  operator_name: "山田", start_date: "2026-08-19 10:00:00", end_date: "2026-08-19 10:05:00",
  call_status: "完了", note: "見積送付済み"
};

test("shouldRecordInteractionLog: 一意マッチ+完了+取得対象種別ならtrue", () => {
  assert.equal(cti.shouldRecordInteractionLog(COMPLETED_OUTBOUND_CALL, MATCHED_COMPANY), true);
});

test("shouldRecordInteractionLog: 未マッチならfalse", () => {
  assert.equal(cti.shouldRecordInteractionLog(COMPLETED_OUTBOUND_CALL, null), false);
});

test("shouldRecordInteractionLog: 通話ステータスがキャンセルならfalse", () => {
  const call = Object.assign({}, COMPLETED_OUTBOUND_CALL, { call_status: "キャンセル" });
  assert.equal(cti.shouldRecordInteractionLog(call, MATCHED_COMPANY), false);
});

test("shouldRecordInteractionLog: 内線(call_type=0)ならfalse", () => {
  const call = Object.assign({}, COMPLETED_OUTBOUND_CALL, { call_type: 0 });
  assert.equal(cti.shouldRecordInteractionLog(call, MATCHED_COMPANY), false);
});

test("buildCallLogRow: マッチ+完了の場合は「記録済み」でHEADERS順の配列を返す", () => {
  const row = cti.buildCallLogRow("CTI-g100", COMPLETED_OUTBOUND_CALL, MATCHED_COMPANY);
  assert.deepEqual(row, [
    "CTI-g100", "g100", "2026-08-19 10:00:00", "電話", "0980000001",
    "C001", "テスト商事", "山田", "完了", "見積送付済み", "記録済み"
  ]);
});

test("buildCallLogRow: 未マッチの場合は企業ID・企業名が空欄、「未記録」", () => {
  const row = cti.buildCallLogRow("CTI-g200", COMPLETED_OUTBOUND_CALL, null);
  assert.equal(row[5], "");
  assert.equal(row[6], "");
  assert.equal(row[10], "未記録");
});

test("buildCallLogRow: キャンセル通話は種別は算出されるが「未記録」", () => {
  const call = Object.assign({}, COMPLETED_OUTBOUND_CALL, { call_status: "キャンセル" });
  const row = cti.buildCallLogRow("CTI-g300", call, MATCHED_COMPANY);
  assert.equal(row[3], "電話");
  assert.equal(row[10], "未記録");
});

test("buildInteractionLogRowForCall: 自動記録対象なら対応履歴ログ用の配列を返す", () => {
  const row = cti.buildInteractionLogRowForCall("H-abc123", COMPLETED_OUTBOUND_CALL, MATCHED_COMPANY);
  assert.equal(row[0], "H-abc123");
  assert.equal(row[1], "C001");
  assert.equal(row[2], "2026-08-19");
  assert.equal(row[3], "システム(CTI自動記録)");
  assert.equal(row[4], "電話");
  assert.equal(row[5], "未接触");
  assert.match(row[6], /CTI自動記録.*山田.*見積送付済み/);
  assert.equal(row[7], "");
});

test("buildInteractionLogRowForCall: 自動記録対象外(未マッチ)ならnull", () => {
  assert.equal(cti.buildInteractionLogRowForCall("H-abc123", COMPLETED_OUTBOUND_CALL, null), null);
});

test("buildInteractionLogRowForCall: 自動記録対象外(キャンセル)ならnull", () => {
  const call = Object.assign({}, COMPLETED_OUTBOUND_CALL, { call_status: "キャンセル" });
  assert.equal(cti.buildInteractionLogRowForCall("H-abc123", call, MATCHED_COMPANY), null);
});

test("parseCdrCsv: V10形式(Group_CallId・要約あり)を読み、発信は着信先を相手の番号にする。内線と見出しは除く", () => {
  const csv = [
    "Group_CallId,種類,発信元,着信先,外線番号,総時間,通話時間,状態,発着信時間,オペレータ,オプション,録音ファイル名,文字起こし,要約",
    'G100,2,1001,0989111111,0980000000,120,95,SUCCESS,2026-10-26 10:00:00,福田,,rec1.wav,"もしもし、\nこんにちは","後継者の相談。来月再訪"',
    "G101,0,1001,1002,,10,5,SUCCESS,2026-10-26 10:05:00,福田,,,,",
    "G102,1,0989222222,1001,0980000000,30,0,CANCEL,2026-10-26 11:00:00,福田,,,,",
  ].join("\r\n");
  const calls = cti.parseCdrCsv(csv);
  assert.equal(calls.length, 2);
  assert.equal(calls[0].group_callid, "G100");
  assert.equal(calls[0].phone, "0989111111");
  assert.equal(calls[0].call_status, "完了");
  assert.equal(calls[0].operator_name, "福田");
  assert.match(calls[0].note, /通話時間 95/);
  assert.match(calls[0].note, /後継者の相談/);
  assert.equal(calls[1].phone, "0989222222", "着信は発信元が相手");
  assert.equal(calls[1].call_status, "キャンセル");
});

test("parseCdrCsv: V8形式(11列・IDなし)は日時と番号から重複しないIDを作る", () => {
  const csv = "2,1001,098-911-1111,0980000000,60,40,SUCCESS,2026-10-26 09:00:00,福田,,rec.wav\n";
  const calls = cti.parseCdrCsv(csv);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].group_callid, "CDR-20261026090000-0989111111");
  assert.equal(calls[0].phone, "098-911-1111");
  assert.equal(cti.shouldRecordInteractionLog(calls[0], { "企業ID": "C1" }), true);
});

test("parseCsv: 引用符の中のカンマ・改行・二重引用符を正しく扱う", () => {
  assert.deepEqual(cti.parseCsv('a,"b,c","d\n""e"""\nx,y'), [["a", "b,c", 'd\n"e"'], ["x", "y"]]);
  assert.deepEqual(cti.parseCsv(""), []);
});

test("buildPhoneIndex/matchCompanyByPhoneIndex: matchCompanyByPhone と同じ結果(一意なら企業、複数ならnull)", () => {
  const companies = [
    { "企業ID": "C1", "電話番号": "098-911-1111", "携帯番号": "" },
    { "企業ID": "C2", "電話番号": "098-922-2222", "携帯番号": "090-1111-2222" },
    { "企業ID": "C3", "電話番号": "098-922-2222", "携帯番号": "" },
  ];
  const index = cti.buildPhoneIndex(companies);
  for (const phone of ["0989111111", "098-922-2222", "09011112222", "0000", ""]) {
    assert.deepEqual(cti.matchCompanyByPhoneIndex(index, phone), cti.matchCompanyByPhone(companies, phone), phone);
  }
  assert.equal(cti.matchCompanyByPhoneIndex(index, "0989111111")["企業ID"], "C1");
  assert.equal(cti.matchCompanyByPhoneIndex(index, "098-922-2222"), null);
});

test("filterCallsByOperators: スタッフの氏名(空白は無視)と一致するオペレーターの通話だけ残す。許可が空なら何も残さない", () => {
  const calls = [
    { operator_name: "福田　貴史(glow01)" },
    { operator_name: "山田　花子(ext001)" },
    { operator_name: "福田貴史" },
    { operator_name: "" },
  ];
  const kept = cti.filterCallsByOperators(calls, ["福田　貴史", "小柳 健"]);
  assert.equal(kept.length, 2);
  assert.ok(kept.every((c) => c.operator_name.startsWith("福田")));
  assert.equal(cti.filterCallsByOperators(calls, []).length, 0);
  assert.equal(cti.operatorPersonName("佐藤　一郎(ext004)"), "佐藤一郎");
});
