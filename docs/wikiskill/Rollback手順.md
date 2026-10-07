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
# 対象 commit は wikiskill-phase1-v1 タグが指すマージコミット
git revert -m 1 $(git rev-list -n1 wikiskill-phase1-v1)
git push -u origin rollback/wikiskill-phase1     # PR を作り、小柳さんの決裁後にマージ
```

- 対象 commit は `git rev-list -n1 wikiskill-phase1-v1`(タグがマージコミットを指す)。例: `git revert -m 1 $(git rev-list -n1 wikiskill-phase1-v1)`。
- 実演記録(本番 main 非接触): `docs/wikiskill/Phase1受け入れ記録.md` の「Rollback 実演」
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

## Phase 2(Knowledge Wiki)の止め方・戻し方

Phase 2(Wiki の抽出・検証・`[Wiki]` 注入)を、軽い方法から順に止める・戻す手順。導入の議事は `docs/議事/議事_20261007_WikiSkill_Phase2導入.md`。Phase 1 の 1〜4(上の各節)は Phase 2 でもそのまま使える。

**Rollback 条件(どれか1つでも起きたら止める)**

| 条件 | 内容 | 最初の手 |
|---|---|---|
| RB1 | 検証器の偽陰性で、誤った知識が approved に入った | `wiki.off` → 該当 Wiki の revert → 検証器に負例を追加 |
| RB2 | private 由来のテキストが候補(PR・ブランチを含む)に出た | `wiki.off` + 抽出 workflow の無効化 → 失敗台帳 → 履歴の扱いは議事で決める |
| RB3 | Bootstrap の `slow`(500ms 超。`.claude/experience/_audit.log`)が週3回 | `wiki.off` → 原因調査 |
| RB4 | `python3 scripts/baseline_debt.py --compare` が REGRESSION | 該当 PR を revert |
| RB5 | Decision と矛盾する Wiki が注入された(`needs_review` の取りこぼし) | `wiki.off` → 検証器に矛盾の負例を追加 |

### P1. 部分停止: `[Wiki]` だけ止める(守り部・単独可・数秒)

```bash
touch .claude/wiki.off      # 止める(git に入らない。この作業コピーだけ)
rm .claude/wiki.off         # 再開する
```

- `.claude/wiki.off` が止めるのは `[Wiki]` の注入だけ。Decision・失敗台帳・再発防止・Skill・Experience の記録と注入は動き続ける。
- 全部止めるときは Phase 1 の 1(`.claude/memory.off` または `HOJO_MEMORY_OFF=1`)。`memory.off` は記録も注入も止める。
- `.claude/wiki.off` はローカルの作業コピー用。クラウドセッションは作業コピーが毎回新しく、Bootstrap の注入は SessionStart(段1)と最初の指示(段2)で1回ずつ、どちらもセッションの中で最初のコマンドを打つより先に走るので、`touch .claude/wiki.off` は間に合わない。クラウドの緊急停止は、環境の設定に `HOJO_MEMORY_OFF=1` を入れる(記録も注入も全部止まる)か、該当の Wiki・Phase 2 を revert する(P2・P4)。
- 確認: `python3 scripts/memory_bootstrap.py query "Wiki"` の `[Wiki]` の節が `- 該当なし` になる。

### P2. Wiki 1件を戻す(誤った知識が1件だけのとき)

承認済みの Wiki 1件が誤っているだけなら、仕組みは止めずにその1件だけを外す。

1. `git revert <その Wiki を昇格した commit>`(または PR のマージコミットなら `git revert -m 1 <マージコミット>`)。revert した結果、ファイルは `docs/wiki/` 直下から消える。
2. 消さずに残したいときは、`docs/wiki/_archive/` へ移し、`review_status: superseded` と `superseded_by` を書く(`docs/wikiskill/Wiki昇格手順.md` の第5項)。ただし後継のページが無いときは superseded にできない(V09・V15)ので、`docs/wiki/_candidates/` へ戻して `review_status: rejected` と `rejected_reason` を書き、承認のキーを外す(2026-10-07 の受け入れ試験用 Wiki はこの方法で退役した)。後継の無い退役専用の状態は Phase 3 の課題。
3. 昇格は小柳さんがマージした PR なので、revert の PR も小柳さんの決裁後にマージする。急ぐときは P1 で `[Wiki]` を先に止める。

### P3. 抽出ワークフローを止める

- GitHub の Actions 画面で `knowledge-extract` ワークフローを無効化する(Disable workflow)。実行は手動(`workflow_dispatch`)のみなので、これで抽出は完全に止まる。cron は無い(Gate G2)。
- 抽出が作った `wiki-candidates/<RUN_ID>` ブランチの PR は、マージせずにクローズする。ブランチの push の時点で公開されているので、RB2(private 由来のテキスト)のときは、PR のクローズだけでなくブランチの削除と履歴の扱いを議事で決める。
- ローカルで抽出を走らせない(`python3 scripts/knowledge_extract.py` を実行しない)。`--break-stale-lock` は鍵を外すだけのコマンドではなく、抽出そのものを実行する(最大10件の候補をローカルに書く)ので、止めたいときには使わない。
- 古くなった鍵(`.claude/locks/knowledge-extract.lock`)が後の実行を止めているときは、`python3 scripts/knowledge_extract.py --dry-run --break-stale-lock`(何も書かない)で外すか、動いている実行が無いことを確かめてから鍵のファイルを手で削除する。鍵が効くのはローカルだけで、Actions の実行環境は毎回新しい checkout なので鍵は残らない。

### P4. 正式 Rollback: Phase 2 全体を元に戻す(PR 全体の revert)

```bash
git fetch origin main
git switch -c rollback/wikiskill-phase2 origin/main
# 対象 commit は wikiskill-phase2-v1 タグが指すマージコミット(Task 9 のマージ後に追記)
git revert -m 1 <マージコミット: Task 9 のマージ後に追記>
git push -u origin rollback/wikiskill-phase2     # PR を作り、小柳さんの決裁後にマージ
```

- タグ `wikiskill-phase2-v1` は小柳さんの最終承認の後に付く。付いた後は `git revert -m 1 $(git rev-list -n1 wikiskill-phase2-v1)` でも同じ commit を指せる。
- revert で戻るもの: 検証・抽出・Bootstrap の `[Wiki]`・CI のステップ・workflow・CODEOWNERS・文書。Phase 1(記録と `[D]` などの注入)は戻らない(Phase 1 の戻し方は上の 2)。
- **`docs/wiki/` に承認済みの Wiki が入った後は、revert でそれらも消える**。残すかどうかは別途議事で決める(消す前に `_archive/` へ移すこともできる)。
- GitHub の branch protection(G1。Code Owners の承認必須)は小柳さんの GitHub 設定で、revert では戻らない。外すかどうかは小柳さんが決める。

### P5. 記録(48時間以内)

停止や Rollback をしたら、Phase 1 の 3 と同じく48時間以内に次をやる(Decision 7)。

1. 議事を作る: `docs/議事/` に `議事_YYYYMMDD_WikiSkill_Phase2緊急停止.md`(YYYYMMDD は停止した日。ウタガイ役の反対理由も記録する)。
2. 失敗台帳に1行足す: `docs/失敗台帳.md`。
3. 小柳さんの Decision Gate で、再開・Rollback の確定・部分停止にとどめるかを決めてもらう。決裁までは P1 または P3 の停止状態を保つ。
