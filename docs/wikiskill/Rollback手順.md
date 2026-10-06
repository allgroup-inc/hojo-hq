# WikiSkill Phase 1 Rollback手順

WikiSkill Phase 1(Experience の記録 + Memory Bootstrap)を止める・戻すための手順。上から順に、軽い方法から並べている。迷ったら 1(緊急停止)を先にやり、落ち着いてから 2 以降を決める。

- 実行できる人: 守り部は 1 を単独で実行してよい(小柳さんの事前承認は不要)。2・4 は小柳さんの決裁後に行う。
- 既存の superpowers の SessionStart hook(`.claude/hooks/superpowers-session-start.sh`)は、どの手順でも触らない・影響も受けない。
- 全体の索引(Task 7 で作成): `docs/wikiskill/README.md`
- Task 9(PR・マージ・タグ)に進む条件: repo-scope の Experience 検査(自己点検・本体)と Decision 検査(議事の必須項目)が緑で、置き場所の検査は Baseline の9件(`docs/wikiskill/baseline-debt.json`)だけが赤のままであること。repo-scope の Experience 検査と Decision 検査は、置き場所の検査が赤でも走る(`if: !cancelled()`)。

## 1. 緊急停止(守り部・単独可・数秒)

全 hook を無効にする。コードも設定も変えない。

```bash
# 停止(このリポジトリのこの作業コピーで有効。git 管理外のファイル)
touch .claude/memory.off

# 恒久化したいとき: 環境変数を環境(シェル・クラウド環境の設定)に入れる
export HOJO_MEMORY_OFF=1
```

- 停止スイッチは2つで、どちらか一方で効く。
  - ファイル `.claude/memory.off`(リポジトリ直下からの相対パス。`.gitignore` 済みなので commit されず、別の作業コピーには引き継がれない)
  - 環境変数 `HOJO_MEMORY_OFF`(空・`0`・`false`・`no`・`off` 以外ならオン。大文字小文字・前後の空白は無視)
- 効き方: `.claude/hooks/wikiskill-hook.sh` が Python を起動する前に判定し、`{}` を出して exit 0 する。Python が壊れていても止まる。Experience の記録も Memory Bootstrap の注入も、どちらも止まる。
- **クラウドセッション**は作業コピーが毎回新しくなるので、各セッションで `touch .claude/memory.off` を実行する。全セッションに効かせたいときは `HOJO_MEMORY_OFF=1` を環境側に設定する。
- 再開: `rm .claude/memory.off`(環境変数も外す)。
- 確認: **出力が `{}` であることだけでは、停止の証明にならない**(停止していなくても、中身の空の入力なら `{}` が出る)。次の手順で「記録が作られないこと」を確かめる。

```bash
ls .claude/memory.off                                   # ファイルがあること(環境変数で止めているときは、このコマンドは不要で、下の hook 実行の前に HOJO_MEMORY_OFF=1 を付ける)
before=$(cat .claude/experience/_audit.log 2>/dev/null | wc -l)
echo '{"session_id":"rollback-check","hook_event_name":"SessionStart","source":"startup"}' \
  | .claude/hooks/wikiskill-hook.sh SessionStart        # 出力は {} になる(これだけでは証明にならない)
ls .claude/experience/*/session-rollback-check.jsonl 2>/dev/null   # 何も表示されなければ OK(記録が作られていない)
after=$(cat .claude/experience/_audit.log 2>/dev/null | wc -l)
[ "$before" = "$after" ] && echo "audit 増加なし" || echo "audit が増えた: 要確認"
```

  - 判定: `session-rollback-check.jsonl` が作られず、`_audit.log` の行数も増えていなければ、停止している。
  - `session-rollback-check.jsonl` が表示されたら停止していない。確認用に作られた記録なので `rm .claude/experience/*/session-rollback-check.jsonl` で消し、`.claude/memory.off` の場所(リポジトリ直下の `.claude/`)と環境変数を見直す。

## 2. 正式 Rollback(Git)

仕組みごと元に戻す。settings.json の hook 登録・hooks・scripts・docs・CI のステップが一括で戻る。

```bash
git fetch origin main
git switch -c rollback/wikiskill-phase1 origin/main
# <wikiskill-phase1-v1 のマージコミット> は、マージ後に実際のハッシュを書き入れる(Task 9 で記入)
git revert -m 1 <wikiskill-phase1-v1 のマージコミット>
git push -u origin rollback/wikiskill-phase1     # PR を作り、小柳さんの決裁後にマージ
```

- マージコミットは `wikiskill-phase1-v1` タグが指す(`git rev-parse wikiskill-phase1-v1^{commit}`)。ハッシュの確定はマージ後(Task 9)なので、この文書の `<...>` の部分はそのときに実際の値へ置き換える。
- **Experience の JSONL(`.claude/experience/YYYY-MM/session-*.jsonl`。commit 後の続きの `session-*.part<N>.jsonl` を含む)は revert で消えない**。履歴に残る。消すかどうかは別途議事で決める。

## 3. 記録(48時間以内)

停止や Rollback をしたら、48時間以内に次をやる。

1. 議事を作る: `docs/議事_YYYYMMDD_WikiSkill緊急停止.md`(YYYYMMDD は停止した日)。先頭の frontmatter は `docs/wikiskill/議事frontmatterテンプレート.md` の形に必ず従う(ウタガイ役の反対理由も記録する。`docs/三名体制運営規程.md` 参照)。
2. 失敗台帳に1行足す: `docs/失敗台帳.md`。
3. 小柳さんの Decision Gate で正式判断を受ける(Decision 7)。再開するか、Rollback を確定するか、部分停止にとどめるかを決めてもらう。決裁までは 1 の停止状態を保つ。

## 4. 部分停止

全体は止めず、片方だけ止める。`.claude/settings.json` の `hooks` から該当エントリを削除する(commit して反映)。`.claude/hooks/wikiskill-hook.sh <イベント名>` を呼ぶエントリが対象で、イベントは `SessionStart` / `UserPromptSubmit` / `PostToolUse` / `SessionEnd` の4つ。

| 止めるもの | 削除するエントリ |
|---|---|
| Bootstrap(過去の決定の注入)だけ | `UserPromptSubmit` のエントリ全体 と、`SessionStart` の **2本目**(`wikiskill-hook.sh SessionStart` のエントリ) |
| Experience(記録)だけ | `PostToolUse` のエントリ全体 と、`SessionEnd` のエントリ全体 |

- `SessionStart` の1本目(`superpowers-session-start.sh`)は**必ず残す**。
- `SessionStart` の wikiskill エントリは1回の呼び出しで「記録の開始」と「Bootstrap 段1」の両方を行う。そのため Bootstrap 停止でこれを消すと、セッション開始の記録も止まる(`PostToolUse` / `SessionEnd` は動き続ける)。逆に Experience だけ止める場合も、`SessionStart` が残るので開始記録と段1の注入は続く。
- 一時的にやるだけなら、settings.json を触らず 1 の緊急停止で全停止する方が安全。

## 運用(サイズ監視と Archive)

Experience は Git が正本。増えすぎを防ぐため、サイズ監視と、180日を過ぎた月の gzip 化(原本は gzip の中に全行残る)を `scripts/experience_archive.py` で行う。

```bash
python3 scripts/experience_archive.py --check                      # 合計サイズ。exit 0=正常 / 1=3MB以上 / 2=10MB以上
python3 scripts/experience_archive.py --archive --dry-run          # 固める対象を表示するだけ(何も変えない)
python3 scripts/experience_archive.py --archive                    # 実行。archive/YYYY-MM.jsonl.gz ができ、元の月フォルダが消える
git add .claude/experience && git commit -m "chore(wikiskill): Experienceの古い月をgzip化"
```

- 対象は「月フォルダ YYYY-MM の翌月1日から180日以上たった月」。`_local/`・`_audit.log`・`archive/` は対象外。
- 固めた結果を読み戻して原本と一致を確かめてから元のファイルを消す。想定外のファイルがある・同名の gz が既にあって内容が原本と合わない場合は、何も消さずにエラーで止まる(`_audit.log` に1行残る)。
- 元フォルダの削除だけが失敗した場合(gz は検証済み)は、エラーに残りのファイルが出る。同じコマンドを再実行すると、gz が原本の全行を含むことを確かめた上で後始末を完了する。
- `--dry-run` は、実行すると見送りになる月を `見送り(理由)` で先に表示する(見送りが出た月より後の月は `未実行`。実際の実行もそこで止まる)。
- Phase 1 の CI は `--check` を呼ばない(守り部が見る。将来は月次 Routine)。実行は手動。
