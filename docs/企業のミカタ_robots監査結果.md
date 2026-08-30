# 企業のミカタ robots.txt 自動監査結果

最終実行: 2026-08-31 08:16 JST / 実行: GitHub Actions(mikata-audit.yml)/ スクリプト: scripts/audit_sources_mikata.py

> これは機械による事実確認。**収集可否の最終判定は、利用規約審査と合わせて守り部が docs/守り部審査記録.md で行う。**
> ○=代表パス許可 / ×=不可(手動運用へ) / ?=手動確認要

| ソース | ドメイン | HTTP | 機械判定 | 印 |
|---|---|---|---|---|
| 沖縄県(産業振興) | www.pref.okinawa.lg.jp | 404 | robots.txt なし(RFC 9309上、クロール制限の指定なし) | ○ |
| 沖縄県産業振興公社 | okinawa-ric.jp | 200 | 代表パス /service/subsidy.html は許可範囲 | ○ |
| 那覇市(企業支援) | www.city.naha.okinawa.jp | 200 | 代表パス /business/kigyouricchi/kigyoushien/index.html は許可範囲 | ○ |

## robots.txt 抜粋(先頭800字)

### 沖縄県(産業振興) (www.pref.okinawa.lg.jp)
```
(空/取得なし)
```

### 沖縄県産業振興公社 (okinawa-ric.jp)
```
User-agent: *
Disallow: /.shared/
Disallow: /.service/
Disallow: /.preview/
Disallow: /.not-found/

Sitemap: https://okinawa-ric.jp/sitemap.xml


```

### 那覇市(企業支援) (www.city.naha.okinawa.jp)
```
User-agent: *
Disallow: /mlmainte/
Disallow: /mldata/
Disallow: /bousaidata/
```
