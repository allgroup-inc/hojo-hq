# moradou.jp を公開するための手順

もらいわすれ堂（株式会社フクギイロ）を独自ドメイン `moradou.jp` で公開するための、
**小柳さんの操作手順**です。ここに置いてあるファイルは、そのとき使います。

決裁は 2026-08-28 に済んでいます（moradou.jp 採用・年額3,000円前後承認）。
経緯: `docs/議事_20260828_独自ドメインmoradou.md` / `docs/議事_20260923_独自ドメイン配信範囲.md`

---

## 自動化できなかったもの（先に正直に）

**手順1（ドメイン取得）は、AIでは代行できません。** 理由は2つあります。

- **お金がかかる**（年額3,000円前後）。決済手段は小柳さんのものです
- **.jp ドメインは登録者の氏名・住所・電話番号の登録が必須**で、これは正確な実在情報でなければなりません。こちらで作ることはできません

手順1が終わらないと手順3（DNS）も始められません。ここは構造的に人の手が要ります。

一方、**当初あった「トークン発行」と「Secrets登録」は設計を変えて無くしました**。
hojo-hq は Public リポジトリなので、配信先が自分で読みに来れば越境トークンは要りません。
公開リポジトリのCIに長期の書き込みトークンを置かずに済むので、安全面でも良くなっています。

**残りは3つ。うちAIが代行できないのは手順1だけです。**

---

## 手順1: moradou.jp を取得する（10分・年額3,000円前後）

お名前.com、ムームードメイン、Xserverドメインなど、どこでも構いません。

- 2026-09-23 時点で **`moradou.jp` は空いています**（確認済み）
- 登録者情報は株式会社フクギイロの正式な情報で登録してください
- **Whois代行（登録者情報公開代行）を付けてください。** 付けないと登録者の住所・電話番号が誰でも見られる状態で公開されます
- 自動更新をONにしてください。切れるとサイトが丸ごと落ちます

## 手順2: 配信先リポジトリを作る（3分）

1. https://github.com/organizations/allgroup-inc/repositories/new を開く
2. Repository name: **`moradou`**
3. **Public** を選ぶ（Privateだと無料プランでGitHub Pagesが使えません）
4. **「Add a README file」にチェック**（最初のコミットを作るために必要です）
5. Create repository

続けて、組み立て用のファイルを1つ置きます。

6. できたリポジトリで **Add file → Create new file**
7. ファイル名の欄に次をそのまま貼る（`/` を打つと階層になります）:
   `.github/workflows/build.yml`
8. 本文に、このフォルダの **`.github/workflows/build.yml` の中身を全部コピーして貼る**
9. Commit changes

最後に公開設定です。

10. そのリポジトリの **Settings → Pages**
11. Source: **Deploy from a branch** / Branch: **main** / フォルダ: **/ (root)** → Save
12. Custom domain に **`moradou.jp`** と入れて Save
    （手順3のDNSがまだなら「DNS check unsuccessful」と出ますが、それで構いません。DNSが通れば自動で緑になります）
13. DNSが通ったあとで **Enforce HTTPS** にチェック（証明書の発行に数分〜数十分かかります）

> なぜAIが代行できないか: このアカウントのGitHub App権限ではリポジトリを作れません
> （実際に試すと `403 Resource not accessible by integration` になります）。

## 手順3: DNSを設定する（5分・手順1の取得先の管理画面で）

`moradou.jp` の **Aレコードを4本**追加します。ホスト名（サブドメイン）は空欄、または `@` です。

```
185.199.108.153
185.199.109.153
185.199.110.153
185.199.111.153
```

`www.moradou.jp` も使いたい場合は、あわせて **CNAME** を1本:

```
www  →  allgroup-inc.github.io
```

> **IPv6（AAAAレコード）について**: GitHub Pages はIPv6にも対応していますが、
> アドレスをここに書き写すと誤りが残るおそれがあるため載せていません。
> 設定するときは GitHub の公式ページの値をそのままコピーしてください:
> https://docs.github.com/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site
> （IPv4のAレコード4本だけでもサイトは正しく表示されます。AAAAは任意です）

---

## 終わったら

チャットで「できた」と一言ください。こちらで次を進めます。

- 表示確認（470ページ・沖縄版と山梨版・LINE導線）
- 旧URL（github.io）側から新URLへの案内と canonical の付け替え
- GA4のストリームURL、Search Console、LINE・Instagramのプロフィールリンクの差し替え

**canonical の切り替えはDNS開通と表示確認の後にやります。**
先に切り替えると、まだ開いていないドメインを正規URLとして検索エンジンに教えてしまうためです。

## 公開が始まったあとの動き

`allgroup-inc/moradou` の `build.yml` が、hojo-hq の収集cron（03/09/15/21時 JST）の
30分後に自動で走り、最新の内容を組み立て直します。**手作業は要りません。**

- 中身は hojo-hq の `site/` から `scripts/deploy_moradou.py` が生成します
- 旧URLの書き換え漏れ・別ブランド（沖縄企業のミカタ）の混入があればビルドが止まり、
  **前回の正しい内容が公開されたまま残ります**（壊れたものは出ません）
- `moradou` リポジトリを直接編集しないでください。次の配信で上書きされます
- すぐ反映したいときは、`moradou` の Actions → build → Run workflow
