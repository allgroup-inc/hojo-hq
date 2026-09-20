/**
 * GLOW企業リレーション台帳: 台帳の自動バックアップ
 *
 * 背景(2026-09-03 運用点検で判明):
 * 3,212社の会社名・代表者名・電話番号・住所と、全対応履歴が入った台帳が、
 * Drive上にただ1ファイルだけ存在し、バックアップが1つも無い状態だった。
 * スプレッドシートの版履歴は「誰かが編集した」場合の巻き戻しには使えるが、
 * ファイルごと消えた場合・アカウントに問題が起きた場合には何も残らない。
 *
 * また、この台帳はスクリプトから全行を書き直す処理(ImportRunner.gs の
 * writeCompanyRecords_ 等)を持っている。取り込み用の列マッピングを間違えたまま
 * 実行すれば、3,212行が一度に壊れる。壊れたことに数日気づかない可能性があるため、
 * 世代を持ったバックアップが要る。
 *
 * 方針:
 *   - 日次メンテナンス(runDailyMaintenance)の最初に実行する。
 *     その日の変更を加える前の状態を残すため、必ず他のステップより先。
 *   - 世代は BACKUP_GENERATIONS 件だけ残し、古いものはゴミ箱へ移す。
 *     完全削除はしない(誤ってバックアップを消す事故から復帰できるようにするため)。
 *   - 保存先フォルダは名前で探し、無ければ作る(スクリプトプロパティの設定を
 *     人間に頼むと、設定されないまま動かない期間が生まれるため)。
 *
 * 注意: バックアップにも個人情報が丸ごと入る。保存先フォルダを共有しないこと。
 */

/** バックアップの保存先フォルダ名。 */
var BACKUP_FOLDER_NAME = "GLOW台帳バックアップ";

/** 残す世代数。日次実行なので、およそ2週間分さかのぼれる。 */
var BACKUP_GENERATIONS = 14;

/** バックアップファイル名の接頭辞(古い世代を見分けるのに使う)。 */
var BACKUP_FILE_PREFIX = "GLOW企業リレーション台帳_バックアップ_";

/**
 * 台帳を複製し、古い世代をゴミ箱へ移す。
 * 冪等ではない(実行するたびに1世代増える)が、世代数の上限で頭打ちになる。
 */
function backupLedger() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var folder = findOrCreateBackupFolder_();
  var stamp = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd_HHmm");
  var copyName = BACKUP_FILE_PREFIX + stamp;

  DriveApp.getFileById(ss.getId()).makeCopy(copyName, folder);
  Logger.log("台帳をバックアップしました: " + copyName);

  pruneOldBackups_(folder);
}

function findOrCreateBackupFolder_() {
  var found = DriveApp.getFoldersByName(BACKUP_FOLDER_NAME);
  if (found.hasNext()) return found.next();
  Logger.log("バックアップ用フォルダが無いため作成します: " + BACKUP_FOLDER_NAME);
  return DriveApp.createFolder(BACKUP_FOLDER_NAME);
}

/**
 * 世代数を超えた古いバックアップをゴミ箱へ移す。
 * 作成日時の新しい順に BACKUP_GENERATIONS 件を残す。
 * 接頭辞が一致するファイルだけを対象にし、フォルダに置かれた他のファイルには触れない。
 */
function pruneOldBackups_(folder) {
  var backups = [];
  var files = folder.getFiles();
  while (files.hasNext()) {
    var file = files.next();
    if (file.getName().indexOf(BACKUP_FILE_PREFIX) !== 0) continue;
    backups.push({ file: file, createdAt: file.getDateCreated().getTime() });
  }
  if (backups.length <= BACKUP_GENERATIONS) return;

  backups.sort(function (a, b) { return b.createdAt - a.createdAt; });
  backups.slice(BACKUP_GENERATIONS).forEach(function (entry) {
    entry.file.setTrashed(true);
    Logger.log("古いバックアップをゴミ箱へ移しました: " + entry.file.getName());
  });
}
