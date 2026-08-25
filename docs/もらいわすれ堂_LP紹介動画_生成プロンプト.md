# もらいわすれ堂 LP紹介動画 生成プロンプト(v1)

作成: 2026-08-25 / 用途: LPをゆっくり紹介し、最後に虹のロゴが自ら描かれて「もらいわすれ堂」で完結する動画。
AI動画生成(Veo 3 / Sora 2 / Runway 等)にそのまま貼れる形で用意。

**完成版あり(2026-08-25)**: このプロンプトのマスター構成をLP実素材で実装した
無音・テロップ入りのMP4(60秒・9:16・1080×1920)を `video/lp-film-60s/` で
レンダリングできる(構成HTML・再現手順は同ディレクトリのREADME参照)。
AI生成版を作るときも、ラストの虹ロゴカットは同ディレクトリの実装
(公式ロゴSVGのstroke-dasharrayアニメ)を使うのが最も正確。

## 前提(ブランド仕様・必ず守る)

- ロゴ: 「虹と朝日(おはなのひざし)」(docs/もらいわすれ堂_ロゴガイドv1.md)
  - 虹3色: 外=珊瑚 #D2694A / 中=陽 #F2C14E / 内=海 #6FAEA4
  - 朝日: 花びら状のひざし #F5CE6E + 中心 #F2C14E
  - ワードマーク: 「もらいわすれ堂」しっぽり明朝 SemiBold・#B9502F
  - タグライン: 「あなたが受け取るまで、いっしょに。」(#6FAEA4)
- 背景基調: 漆喰 #FFFBF4 / 本文墨 #1F2A2E
- トーン: やさしい日本語・断定しない(「〜かもしれません」)・主語は「あなた」
- **注意: AI動画生成は日本語の文字を正しく描けない**。テロップ・ロゴ・ワードマークは
  生成映像の上に編集(CapCut等)で重ねるか、LPの実物 `site/fukugiiro/index.html` S7シーンの
  stroke-dasharrayアニメ(虹が自分で描かれる)を画面収録して合成するのが確実。
  プロンプト内の日本語テロップ指定は「タイミングと内容のガイド」として扱う。

---

## A. マスタープロンプト(全60秒・一括指定型のツール用)

```
沖縄の暮らしをやさしく描く60秒のブランドムービー。実写風シネマティック、
ドキュメンタリー調のあたたかい色調。カメラはすべてスローで、固定またはごく
ゆっくりのドリー。ナレーションは落ち着いた女性の声で、ゆっくり、間を大切に。
BGMは三線の音色を含む静かなアコースティック。

[0-8秒] 夜の沖縄本島を高台から望む。集落の窓明かりがひとつひとつ灯っている。
月と星、流れ星がひとつ。カメラはゆっくり前進。
テロップ「146万人が、住んでいるのが沖縄です。」

[8-15秒] 未明の空の下、赤瓦屋根とシーサーのシルエット。縁側で三線を弾く人の影。
テロップ「出会いを大事にし、伝統を紡ぐのが沖縄です。」

[15-22秒] 夜明け前の浜辺。数人が力を合わせて一艘の舟を押すシルエット(ゆいまーる)。
テロップ「困ったときは、助け合うのが沖縄です。」

[22-28秒] 朝焼けの海。水平線から朝日が昇り、海鳥が飛ぶ。ハイビスカスの影が手前に揺れる。
テロップ「なにより、美しいのが沖縄です。」

[28-38秒] 静かな室内。食卓に置かれた市役所からの封筒と、スマホを持つ手元のクローズアップ。
ナレーション「そんな沖縄に、いま、まだ眠っている“ささえ”があります。国や県、市町村の
給付金や手当が、『知らなかった』というだけで届かないまま終わることがあるんです。」

[38-50秒] スマホ画面をゆっくり操作する手元。やわらかい漆喰色(#FFFBF4)の画面に
朱色(#B9502F)のボタン。ナレーション「もらいわすれ堂は、確認できた制度だけを掲載する
沖縄の県民向けサイト。3分の診断で、あなたの世帯の“もらい忘れ”がわかるかもしれません。
無料で、匿名で、登録もいりません。」

[50-60秒] 画面全体が漆喰色 #FFFBF4 にゆっくり明転。中央に、細い筆で描くように
虹のアーチが左から右へ自分で描かれていく。外から 珊瑚色 #D2694A、陽の黄色 #F2C14E、
海の緑 #6FAEA4 の3本。描き終わると虹の右肩に、花びらのような朝日(#F5CE6E の8つの
花弁と #F2C14E の中心)がぽっ、と咲くように現れる。
ロゴが完成したら、その下にタグライン「とどけ、沖縄のみらいへ。」がふわりと浮かび、
最後に明朝体・赤瓦色(#B9502F)のワードマーク「もらいわすれ堂」が現れて静止。
そのまま2秒ホールドして終わり。ナレーション「あなたが受け取るまで、いっしょに。
もらいわすれ堂です。」
```

---

## B. シーン別プロンプト(Veo 3 / Sora 2 など8秒前後×7カット用)

各カットを個別生成→編集でつなぐ場合。英語の方が精度が出るモデル向けに英語版を併記。
文字は入れず(絵だけ生成し)、テロップは編集で重ねること。

### カット1: 夜の集落(8秒)
```
A slow cinematic aerial-like shot over an Okinawan island town at night, seen from a
hillside. Hundreds of warm window lights glowing one by one across the village, a full
moon, stars, one shooting star. Gentle forward dolly, documentary warmth, no text.
```

### カット2: 三線と赤瓦(8秒)
```
Pre-dawn indigo sky. Silhouette of a traditional Okinawan red-tile roof with a shisa
statue, and a person playing the sanshin on a porch. Stars twinkle. Static camera,
quiet, nostalgic, cinematic. No text.
```

### カット3: ゆいまーる(8秒)
```
Before sunrise on an Okinawan beach, silhouettes of several villagers pushing one small
wooden boat together toward the sea. Cooperative, warm human moment. Slow lateral dolly,
cinematic, no text.
```

### カット4: 朝焼けの海(6秒)
```
Sunrise over the East China Sea from an Okinawan beach. The sun climbs above the horizon,
seabirds cross the orange sky, a hibiscus silhouette sways in the foreground. Very slow
push-in, breathtaking and warm. No text.
```

### カット5: 眠っているささえ(10秒)
```
Quiet morning interior of an Okinawan home. Close-up of an unopened envelope from a city
office on a wooden dining table, soft window light. Cut to elderly hands and younger
hands looking at a smartphone together. Warm, gentle, documentary style. No text.
```

### カット6: サイトを使う手元(10秒)
```
Close-up of hands slowly using a smartphone. The screen shows a soft ivory-white (#FFFBF4)
website with vermilion (#B9502F) rounded buttons and simple friendly layout. The person
taps calmly, then smiles slightly off-screen. Shallow depth of field, warm light. No text.
```
※画面の中身は生成に任せず、実LPの画面収録を後から合成する方が正確。

### カット7(ラスト): 虹のロゴ完成 → 「もらいわすれ堂」(10秒)
```
On a plain warm ivory background (#FFFBF4), a rainbow arch draws itself from left to
right as if painted by an invisible brush: three clean arcs, outer coral #D2694A, middle
sun-yellow #F2C14E, inner sea-green #6FAEA4, with soft rounded line ends. When the arcs
complete, a small flower-like morning sun blooms at the upper right of the rainbow:
eight petal dots in #F5CE6E around a #F2C14E center, appearing with a gentle pop and
soft glow. Minimal, flat vector animation style, slow and calm, 2 seconds of stillness
at the end. No text (wordmark added in editing).
```
編集で重ねる文字(この順で):
1. ロゴ完成直後: 「とどけ、沖縄のみらいへ。」(しっぽり明朝・墨 #1F2A2E)
2. 最後: **「もらいわすれ堂」**(しっぽり明朝 SemiBold・#B9502F)→ このワードマークで静止して終わる
3. 小さく添える: 「あなたが受け取るまで、いっしょに。」(#6FAEA4)

> 最も確実な方法: LP実物の S7 ビジョンシーン(虹が stroke-dasharray で自分を描くSVG)を
> ブラウザで画面収録し、そのままラストカットに使う。色・形・比率が公式ロゴと完全一致する。

---

## C. ナレーション原稿(60秒・ゆっくり読み)

> 146万人が、住んでいるのが沖縄です。
> 出会いを大事にし、伝統を紡ぐのが沖縄です。
> 困ったときは、助け合うのが沖縄です。
> なにより、美しいのが沖縄です。
>
> そんな沖縄に、いま。まだ眠っている“ささえ”があります。
> 国や県、市町村が用意した給付金や手当が——
> 「知らなかった」というだけで、届かないまま終わることがあるんです。
>
> もらいわすれ堂は、確認できた制度だけを掲載する、沖縄の県民向けサイトです。
> 3分の診断で、あなたの世帯の“もらい忘れ”が見つかるかもしれません。
> 無料で、匿名で、登録もいりません。
>
> あなたが受け取るまで、いっしょに。
> ——もらいわすれ堂です。

※文言はLP実物(site/fukugiiro/index.html フィルム部)と正確性ルールに準拠。
「必ずもらえる」等の断定表現は使わない。

## D. 仕様メモ

- 長さ: 60秒(SNS用は 30秒短縮版=カット1・4・5・7 で再編集可)
- 画角: 9:16(Instagram Reels / LINE VOOM)を基本。YouTube用に16:9も書き出し
- 字幕: 全編テロップ必須(85%が無音視聴)
- 音: 三線を含む静かなアコースティック+波音。ラストのロゴ完成時に小さな鈴の音
- 配信文面に落とすときは出荷ゲート(scripts/shipping_gate.py)・締切表現ルールに従う
