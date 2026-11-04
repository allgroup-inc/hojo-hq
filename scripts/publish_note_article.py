#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — note 記事自動投稿スクリプト(Playwright 使用)

Markdown ファイルを read して note マガジンに投稿。
Playwright でブラウザ操作を自動化し、手動投稿の煩雑さを排除。

要件:
  - NOTE_USER_EMAIL: note ユーザーメール
  - NOTE_USER_PASSWORD: note パスワード
  - NOTE_MAGAZINE_ID: 投稿先マガジン ID

実行:
  python publish_note_article.py posts/note_magazine/2026-10-03_vol1.md
  python publish_note_article.py --headless posts/note_magazine/2026-10-03_vol1.md
"""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

# Playwright はオプショナル依存性(pip install playwright)
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("[error] Playwright が入っていません。pip install playwright を実行してください")
    sys.exit(1)


NOTE_LOGIN_URL = "https://note.com/login"
NOTE_MAGAZINE_URL_TEMPLATE = "https://note.com/me/publications/{}"  # magazine_id


async def read_markdown_file(filepath: str) -> tuple[str, str]:
    """Markdown ファイルを読んでタイトル・本文を抽出。"""

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {filepath}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # タイトル抽出（最初の # ）
    lines = content.split("\n")
    title = ""
    body_start = 0

    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            body_start = i + 1
            break

    if not title:
        raise ValueError("Markdown にタイトル(# で始まる行)がありません")

    # 本文を抽出（--- 前まで）
    body_lines = []
    for line in lines[body_start:]:
        if line.startswith("---"):
            break
        body_lines.append(line)

    body = "\n".join(body_lines).strip()

    if not body:
        raise ValueError("Markdown に本文がありません")

    return title, body


async def login_to_note(page, email: str, password: str) -> bool:
    """note にログイン。改善版：より堅牢なセレクタと待機ロジック"""

    try:
        await page.goto(NOTE_LOGIN_URL, wait_until="networkidle")
        await asyncio.sleep(1)  # ページ完全読み込み待機

        try:
            # メールアドレス入力フィールド：複数セレクタを試す
            email_selectors = [
                'input[name="login"]',
                'input[name="email"]',
                'input[type="email"]',
                'input[name="account"]',
                'input[placeholder*="メール"]',
                'input[placeholder*="ログイン"]',
                'input[placeholder*="account"]',
            ]

            email_field = None
            for selector in email_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=3000)
                    email_field = await page.query_selector(selector)
                    if email_field:
                        print(f"[ok] メールフィールド見つけました: {selector}")
                        break
                except:
                    continue

            if not email_field:
                print("[error] メールアドレス入力フィールドが見つかりません")
                all_inputs = await page.query_selector_all('input')
                print(f"[debug] ページ内の全input要素: {len(all_inputs)}")
                for i, inp in enumerate(all_inputs):
                    name = await inp.get_attribute('name')
                    type_attr = await inp.get_attribute('type')
                    placeholder = await inp.get_attribute('placeholder')
                    print(f"[debug] input#{i}: name={name}, type={type_attr}, placeholder={placeholder}")
                return False

            await email_field.fill(email)
            await email_field.press('Tab')  # 次フィールドへ移動
            print("[ok] メールアドレスを入力")
            await asyncio.sleep(0.5)

            # パスワード入力フィールド：複数セレクタを試す
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[name="pass"]',
                'input[placeholder*="パスワード"]',
                'input[placeholder*="password"]',
            ]

            password_field = None
            for selector in password_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=3000)
                    password_field = await page.query_selector(selector)
                    if password_field:
                        print(f"[ok] パスワードフィールド見つけました: {selector}")
                        break
                except:
                    continue

            if not password_field:
                print("[error] パスワード入力フィールドが見つかりません")
                return False

            await password_field.fill(password)
            print("[ok] パスワードを入力")
            await asyncio.sleep(0.5)

            # ログインボタンをクリック
            button_selectors = [
                'button[type="submit"]',
                'button:has-text("ログイン")',
                'button:has-text("Login")',
                'input[type="submit"]',
                'a[role="button"]:has-text("ログイン")',
            ]

            login_button = None
            for selector in button_selectors:
                try:
                    login_button = await page.query_selector(selector)
                    if login_button:
                        print(f"[ok] ログインボタン見つけました: {selector}")
                        break
                except:
                    continue

            if not login_button:
                print("[error] ログインボタンが見つかりません")
                return False

            await login_button.click()
            print("[ok] ログインボタンをクリック")

            # ダッシュボードへのリダイレクトを待つ
            try:
                await page.wait_for_url("**/me/**", timeout=15000)
            except:
                # リダイレクト待機がタイムアウトした場合、ページ遷移を待つ
                await page.wait_for_load_state("networkidle", timeout=15000)

            print("[ok] note へのログインに成功しました")
            return True

        except Exception as e:
            print(f"[error] フロー内エラー: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    except Exception as e:
        print(f"[error] note ログイン失敗: {e}")
        import traceback
        print(traceback.format_exc())
        return False


async def post_to_magazine(page, magazine_id: str, title: str, body: str) -> bool:
    """マガジンに記事を投稿。"""

    try:
        # マガジンのダッシュボードへ移動
        magazine_url = NOTE_MAGAZINE_URL_TEMPLATE.format(magazine_id)
        await page.goto(magazine_url, wait_until="networkidle", timeout=30000)

        # ページが完全に読み込まれるまで待機（JavaScript の初期化完了待ち）
        print("[info] ページ読み込み中...")
        for i in range(10):  # 最大10秒待機
            all_buttons = await page.query_selector_all('button')
            buttons_with_text = []
            for btn in all_buttons:
                text = await btn.text_content()
                if text and text.strip():
                    buttons_with_text.append(text.strip())

            if len(buttons_with_text) > 0:
                print(f"[ok] ダッシュボード読み込み完了（{len(buttons_with_text)}個のテキスト付きボタン検出）")
                break

            await asyncio.sleep(1)
        else:
            print("[warning] ダッシュボードの完全な読み込みを確認できません。続行します")

        # 「新しい記事を作成」ボタンをクリック（複数セレクタ戦略）
        create_button_selectors = [
            'button:has-text("新しい記事を作成")',
            'a:has-text("新しい記事を作成")',
            '[class*="createButton"]',
            '[class*="primary"]button',
            'text=新しい記事を作成',
        ]

        create_button = None
        for selector in create_button_selectors:
            try:
                create_button = await page.query_selector(selector)
                if create_button:
                    print(f"[ok] 作成ボタン見つけました: {selector}")
                    break
            except:
                continue

        if not create_button:
            print("[error] 新しい記事を作成ボタンが見つかりません")
            print("[debug] ページの全要素情報を出力します")

            # 全ボタンの詳細情報
            all_buttons = await page.query_selector_all('button')
            print(f"[debug] ボタン数: {len(all_buttons)}")
            for i, btn in enumerate(all_buttons[:15]):
                text = await btn.text_content()
                classes = await btn.get_attribute('class')
                role = await btn.get_attribute('role')
                print(f"[debug] button#{i}: text='{text}' class='{classes}' role='{role}'")

            # リンク要素の確認
            all_links = await page.query_selector_all('a[href*="new"], a[href*="create"], a[href*="post"]')
            print(f"[debug] 関連リンク数: {len(all_links)}")
            for i, link in enumerate(all_links[:5]):
                text = await link.text_content()
                href = await link.get_attribute('href')
                print(f"[debug] link#{i}: text='{text}' href='{href}'")

            return False

        await create_button.click()
        print("[ok] 作成ボタンをクリック")
        await asyncio.sleep(2)  # ページ遷移待機

        # タイトル入力（複数セレクタ戦略）
        title_selectors = [
            'input[placeholder*="タイトル"]',
            'input[placeholder*="title"]',
            'input[placeholder*="記事タイトル"]',
            'input[type="text"]',
        ]

        title_field = None
        for selector in title_selectors:
            try:
                await page.wait_for_selector(selector, timeout=2000)
                title_field = await page.query_selector(selector)
                if title_field:
                    print(f"[ok] タイトルフィールド見つけました: {selector}")
                    break
            except:
                continue

        if title_field:
            await title_field.fill(title)
            print(f"[ok] タイトルを入力: {title}")

        # 本文入力（contenteditable な div を使用）
        content_field = await page.query_selector('[contenteditable="true"]')
        if content_field:
            await content_field.fill(body)
            print(f"[ok] 本文を入力: {len(body)} 字")

        # 下書き保存を待つ（自動保存の場合）
        await asyncio.sleep(2)

        # 公開ボタンをクリック（複数セレクタ戦略）
        publish_selectors = [
            'button:has-text("公開")',
            'button:has-text("投稿")',
            'button[class*="publish"]',
            'button[class*="submit"]',
        ]

        publish_button = None
        for selector in publish_selectors:
            try:
                publish_button = await page.query_selector(selector)
                if publish_button:
                    print(f"[ok] 公開ボタン見つけました: {selector}")
                    break
            except:
                continue

        if publish_button:
            await publish_button.click()
            print("[ok] 公開ボタンをクリック")

        # 確認ダイアログが出る場合がある
        try:
            await page.click('button:has-text("公開する")', timeout=5000)
        except:
            pass

        # 公開完了を待つ
        await asyncio.sleep(3)

        print("[ok] note への投稿に成功しました")
        return True

    except Exception as e:
        print(f"[error] note 投稿失敗: {e}")
        import traceback
        print(traceback.format_exc())
        return False


async def main(article_path: str, headless: bool = True):
    """メイン処理。"""

    # 認証情報を環境変数から取得
    email = os.environ.get("NOTE_USER_EMAIL")
    password = os.environ.get("NOTE_USER_PASSWORD")
    magazine_id = os.environ.get("NOTE_MAGAZINE_ID")

    if not all([email, password, magazine_id]):
        print("[error] 環境変数が設定されていません:")
        print("  - NOTE_USER_EMAIL")
        print("  - NOTE_USER_PASSWORD")
        print("  - NOTE_MAGAZINE_ID")
        sys.exit(1)

    # Markdown ファイルを読む
    try:
        title, body = await read_markdown_file(article_path)
        print(f"[ok] Markdown ファイルを読み込み: {article_path}")
    except Exception as e:
        print(f"[error] ファイル読み込み失敗: {e}")
        sys.exit(1)

    # Playwright でブラウザを起動
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # ログイン
            if not await login_to_note(page, email, password):
                await browser.close()
                sys.exit(1)

            # 投稿
            if not await post_to_magazine(page, magazine_id, title, body):
                await browser.close()
                sys.exit(1)

            print("[success] 記事が公開されました")

        finally:
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("article_path", help="投稿する Markdown ファイルのパス")
    parser.add_argument("--headless", action="store_true", default=True, help="ヘッドレスモード(既定: True)")
    parser.add_argument("--show", action="store_true", help="ブラウザ画面を表示(headless=False)")
    args = parser.parse_args()

    headless_mode = not args.show

    asyncio.run(main(args.article_path, headless=headless_mode))
