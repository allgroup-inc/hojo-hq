# フクギイロ robots.txt 自動監査結果

最終実行: 2026-07-22 22:48 JST / 実行: GitHub Actions(fukugiiro-audit.yml)/ スクリプト: scripts/audit_sources_fukugiiro.py

> これは機械による事実確認。**収集可否の最終判定は、利用規約審査と合わせて守り部が docs/守り部審査記録.md で行う。**
> ○=代表パス許可 / ×=不可(手動運用へ) / ?=手動確認要

| ソース | ドメイン | HTTP | 機械判定 | 印 |
|---|---|---|---|---|
| こども家庭庁 | www.cfa.go.jp | 200 | 代表パス /policies/ は許可範囲 | ○ |
| 厚生労働省 | www.mhlw.go.jp | 200 | 代表パス /stf/ は許可範囲 | ○ |
| 協会けんぽ | www.kyoukaikenpo.or.jp | 404 | robots.txt なし(RFC 9309上、クロール制限の指定なし) | ○ |
| 文部科学省 | www.mext.go.jp | 404 | robots.txt なし(RFC 9309上、クロール制限の指定なし) | ○ |
| JASSO | www.jasso.go.jp | 200 | 代表パス /shogakukin/ は許可範囲 | ○ |
| 国土交通省 | www.mlit.go.jp | 404 | robots.txt なし(RFC 9309上、クロール制限の指定なし) | ○ |
| 内閣府 | www.cao.go.jp | 404 | robots.txt なし(RFC 9309上、クロール制限の指定なし) | ○ |
| 内閣府防災 | www.bousai.go.jp | 404 | robots.txt なし(RFC 9309上、クロール制限の指定なし) | ○ |
| 全国社会福祉協議会 | www.shakyo.or.jp | 404 | robots.txt なし(RFC 9309上、クロール制限の指定なし) | ○ |
| 那覇市 | www.city.naha.okinawa.jp | 200 | 代表パス /kurashitetuduki/ は許可範囲 | ○ |
| 沖縄市 | www.city.okinawa.okinawa.jp | 404 | robots.txt なし(RFC 9309上、クロール制限の指定なし) | ○ |
| うるま市 | www.city.uruma.lg.jp | 404 | robots.txt なし(RFC 9309上、クロール制限の指定なし) | ○ |
| 浦添市 | www.city.urasoe.lg.jp | 404 | robots.txt なし(RFC 9309上、クロール制限の指定なし) | ○ |
| 宜野湾市 | www.city.ginowan.lg.jp | 404 | robots.txt なし(RFC 9309上、クロール制限の指定なし) | ○ |

## robots.txt 抜粋(先頭800字)

### こども家庭庁 (www.cfa.go.jp)
```
#
# robots.txt
#
# This file is to prevent the crawling and indexing of certain parts
# of your site by web crawlers and spiders run by sites like Yahoo!
# and Google. By telling these "robots" where not to go on your site,
# you save bandwidth and server resources.
#
# This file will be ignored unless it is at the root of your host:
# Used:    http://example.com/robots.txt
# Ignored: http://example.com/site/robots.txt
#
# For more information about the robots.txt standard, see:
# http://www.robotstxt.org/robotstxt.html

User-agent: *
# CSS, JS, Images
Allow: /core/*.css$
Allow: /core/*.css?
Allow: /core/*.js$
Allow: /core/*.js?
Allow: /core/*.gif
Allow: /core/*.jpg
Allow: /core/*.jpeg
Allow: /core/*.png
Allow: /core/*.svg
Allow: /profiles/*.css$
Allow: /profiles/*.css?
Allow: /profiles/*.
```

### 厚生労働省 (www.mhlw.go.jp)
```
# 
# robots.txt for http://www.mhlw.go.jp/
# 
User-agent: *        
Disallow: /cgi-bin/   
Disallow: /images/	
Disallow: /topics/bukyoku/iyaku/kaisyu/00-1-010.html
```

### 協会けんぽ (www.kyoukaikenpo.or.jp)
```
(空/取得なし)
```

### 文部科学省 (www.mext.go.jp)
```
(空/取得なし)
```

### JASSO (www.jasso.go.jp)
```
<!DOCTYPE html>
<html lang="ja">
	<head>
		<meta charset="utf-8">
		<meta http-equiv="X-UA-Compatible" content="ie=edge">
		<meta name="viewport" content="width=device-width, initial-scale=1.0">
		<meta name="format-detection" content="telephone=no">
		<title>独立行政法人日本学生支援機構 | JASSO</title>
		<meta name="description" content="独立行政法人日本学生支援機構（JASSO）の公式ホームページです。">
		<meta name="keywords" content="">
		<meta name="probobot" content="noindex">
		<meta property="og:title" content="独立行政法人日本学生支援機構">
		<meta property="og:description" content="独立行政法人日本学生支援機構（JASSO）の公式ホームページです。">
		<meta property="og:url" content="https://www.jasso.go.jp/index.html">
		<meta property="og:image" content="https://www.jasso.go.jp/assets/images/common/ogp_ja_logo.jpg">
		<link rel="stylesheet" href="/assets
```

### 国土交通省 (www.mlit.go.jp)
```
(空/取得なし)
```

### 内閣府 (www.cao.go.jp)
```
(空/取得なし)
```

### 内閣府防災 (www.bousai.go.jp)
```
(空/取得なし)
```

### 全国社会福祉協議会 (www.shakyo.or.jp)
```
(空/取得なし)
```

### 那覇市 (www.city.naha.okinawa.jp)
```
User-agent: *
Disallow: /mlmainte/
Disallow: /mldata/
Disallow: /bousaidata/
```

### 沖縄市 (www.city.okinawa.okinawa.jp)
```
(空/取得なし)
```

### うるま市 (www.city.uruma.lg.jp)
```
(空/取得なし)
```

### 浦添市 (www.city.urasoe.lg.jp)
```
(空/取得なし)
```

### 宜野湾市 (www.city.ginowan.lg.jp)
```
(空/取得なし)
```
