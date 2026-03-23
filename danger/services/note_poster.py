"""note.com 自動投稿サービス — Playwright"""
import json
import logging
import os
import time

logger = logging.getLogger(__name__)

COOKIES_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "output", "note_cookies.json")


def _ensure_output_dir() -> None:
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "..", "output"), exist_ok=True)


def _login(page) -> bool:
    """note.comにログイン"""
    email = os.getenv("NOTE_EMAIL")
    password = os.getenv("NOTE_PASSWORD")
    if not email or not password:
        logger.error("NOTE_EMAIL / NOTE_PASSWORD が未設定")
        return False

    page.goto("https://note.com/login")
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # メールアドレス入力
    email_input = page.locator('input[placeholder*="mail@example"]')
    if email_input.count() == 0:
        email_input = page.locator('input').first
    email_input.fill(email)

    # パスワード入力
    pw_input = page.locator('input[type="password"]')
    pw_input.fill(password)
    time.sleep(1)

    # ログインボタン
    page.locator('button:has-text("ログイン")').last.click()
    page.wait_for_load_state("networkidle")
    time.sleep(5)

    # ログイン成功確認（投稿ボタンの存在で判定）
    if page.locator('button:has-text("投稿"), a:has-text("投稿")').count() > 0:
        # Cookie保存
        cookies = page.context.cookies()
        os.makedirs(os.path.dirname(COOKIES_PATH), exist_ok=True)
        with open(COOKIES_PATH, "w") as f:
            json.dump(cookies, f)
        logger.info("note.comログイン成功")
        return True

    # フォロー中ページなどに遷移していればOK
    if "note.com" in page.url and "login" not in page.url:
        cookies = page.context.cookies()
        os.makedirs(os.path.dirname(COOKIES_PATH), exist_ok=True)
        with open(COOKIES_PATH, "w") as f:
            json.dump(cookies, f)
        logger.info("note.comログイン成功")
        return True

    logger.error("ログイン失敗")
    return False


def _restore_cookies(context) -> bool:
    """保存済みCookieを復元"""
    if not os.path.exists(COOKIES_PATH):
        return False
    try:
        with open(COOKIES_PATH, "r") as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        return True
    except Exception:
        return False


THUMBNAIL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "banner_kiken_ninki_uma.png")


def post_to_note(
    title: str,
    body_md: str,
    price: int = 0,
    publish: bool = True,
    free_body: str = "",
    paid_body: str = "",
    thumbnail: str = "",
) -> dict:
    """note.comに記事を投稿

    Args:
        title: 記事タイトル
        body_md: 本文（Markdown）— free_body/paid_body未指定時に使用
        price: 0=無料, 980等=有料
        publish: True=公開, False=下書き保存
        free_body: 無料部分（有料記事の場合、ここまでが無料プレビュー）
        paid_body: 有料部分（有料ラインの後に表示される部分）

    Returns:
        {"status": "ok", "url": "..."} or {"status": "error", "message": "..."}
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "error", "message": "playwright未インストール"}

    if not title.strip():
        return {"status": "error", "message": "タイトルが空です"}

    if price > 0 and free_body and paid_body:
        content = f"{free_body}\n\n{paid_body}"
    elif body_md:
        content = body_md
    else:
        return {"status": "error", "message": "本文が空です"}

    content = content.strip()
    if not content:
        return {"status": "error", "message": "本文が空です"}

    _ensure_output_dir()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # Cookie復元を試みる
            if _restore_cookies(context):
                page.goto("https://note.com/dashboard")
                page.wait_for_load_state("networkidle")
                time.sleep(3)
                if page.locator('button:has-text("投稿"), a:has-text("投稿")').count() == 0:
                    logger.info("Cookie期限切れ、再ログイン")
                    if not _login(page):
                        browser.close()
                        return {"status": "error", "message": "ログイン失敗"}
            else:
                if not _login(page):
                    browser.close()
                    return {"status": "error", "message": "ログイン失敗"}

            # 新規記事作成ページへ
            page.goto("https://note.com/notes/new")
            page.wait_for_load_state("networkidle")
            time.sleep(3)

            # AIと相談ポップアップを閉じる
            close_btn = page.locator('button:has-text("×"), [aria-label="閉じる"]')
            if close_btn.count() > 0:
                close_btn.first.click()
                time.sleep(1)

            # タイトル入力
            page.wait_for_selector("textarea", timeout=15000)
            title_area = page.locator("textarea")
            if title_area.count() == 0:
                browser.close()
                return {"status": "error", "message": "タイトル入力欄が見つからない"}

            title_area.click()
            title_area.fill(title)
            time.sleep(1)

            # 本文入力（ProseMirrorエディタ）
            page.wait_for_selector(".ProseMirror", timeout=15000)
            body_area = page.locator(".ProseMirror")
            if body_area.count() == 0:
                browser.close()
                return {"status": "error", "message": "本文入力欄が見つからない"}

            body_area.click()
            time.sleep(0.5)

            # 段落ごとに入力
            for line in content.split("\n"):
                if line.strip():
                    page.keyboard.type(line, delay=3)
                page.keyboard.press("Enter")
                time.sleep(0.05)

            time.sleep(2)

            if not publish:
                # 下書き保存
                draft_btn = page.locator('button:has-text("下書き保存")')
                if draft_btn.count() > 0:
                    draft_btn.click()
                    time.sleep(3)
                article_url = page.url
                logger.info(f"note下書き保存: {article_url}")
                browser.close()
                return {"status": "ok", "url": article_url, "draft": True}

            # 「公開に進む」ボタン
            publish_step_btn = page.locator('button:has-text("公開に進む")')
            if publish_step_btn.count() == 0:
                browser.close()
                return {"status": "error", "message": "「公開に進む」ボタンが見つからない"}

            publish_step_btn.click()
            time.sleep(3)

            # サムネイル（みだし画像）設定
            thumb = thumbnail or THUMBNAIL_PATH
            if thumb and os.path.exists(thumb):
                try:
                    file_input = page.locator('input[type="file"]')
                    if file_input.count() > 0:
                        file_input.set_input_files(thumb)
                        time.sleep(5)
                        # トリミングダイアログが出たら「適用」
                        apply_btn = page.locator('button:has-text("適用"), button:has-text("完了"), button:has-text("OK")')
                        if apply_btn.count() > 0:
                            apply_btn.first.click()
                            time.sleep(3)
                        logger.info(f"サムネイル設定完了: {os.path.basename(thumb)}")
                    else:
                        logger.warning("サムネイル用file inputが見つからない")
                except Exception as e:
                    logger.warning(f"サムネイル設定スキップ: {e}")

            # 公開設定画面のスクリーンショット（デバッグ用）
            page.screenshot(path="output/note_publish_step.png")

            # 有料設定
            if price > 0:
                # 「有料」ラジオボタンをクリック
                paid_radio = page.locator('text=有料')
                if paid_radio.count() > 0:
                    paid_radio.click()
                    time.sleep(2)

                    # 金額入力欄
                    price_input = page.locator('input[type="number"], input[type="text"]').last
                    if price_input.count() > 0:
                        price_input.fill(str(price))
                        time.sleep(1)

            # 有料の場合は「有料エリア設定」→ ライン位置確認 →「投稿する」
            if price > 0:
                paid_area_btn = page.locator('button:has-text("有料エリア設定")')
                if paid_area_btn.count() > 0:
                    paid_area_btn.click()
                    time.sleep(3)

                    # 有料ラインを無料部分の末尾に配置
                    # 無料部分の段落数を数えて、その直後の「ラインをこの場所に変更」をクリック
                    if free_body:
                        free_lines = [l for l in free_body.split("\n") if l.strip()]
                        target_idx = len(free_lines)  # 無料部分の行数

                        move_btns = page.locator('button:has-text("ラインをこの場所に変更")')
                        btn_count = move_btns.count()
                        if btn_count > 0:
                            click_idx = min(target_idx, btn_count - 1)
                            move_btns.nth(click_idx).click()
                            time.sleep(2)
                        else:
                            logger.warning("有料ラインの移動ボタンが見つからないため既定位置で投稿します")
                    else:
                        # free_body未指定: デフォルト位置（最初のラインのまま）
                        pass

                    # 「投稿する」ボタン
                    submit_btn = page.locator('button:has-text("投稿する")')
                    if submit_btn.count() > 0:
                        submit_btn.click()
                        time.sleep(8)
                        article_url = page.url
                        logger.info(f"note有料記事公開成功: {article_url}")
                        browser.close()
                        return {"status": "ok", "url": article_url}
                    else:
                        page.screenshot(path="output/note_submit_error.png")
                        browser.close()
                        return {"status": "error", "message": "投稿ボタンが見つからない"}
                else:
                    page.screenshot(path="output/note_submit_error.png")
                    browser.close()
                    return {"status": "error", "message": "有料エリア設定ボタンが見つからない"}

            # 無料の場合は「投稿する」
            submit_btn = page.locator('button:has-text("投稿する")')
            if submit_btn.count() > 0:
                submit_btn.last.click()
                time.sleep(8)
                article_url = page.url
                logger.info(f"note記事公開成功: {article_url}")
                browser.close()
                return {"status": "ok", "url": article_url}
            else:
                page.screenshot(path="output/note_submit_error.png")
                browser.close()
                return {"status": "error", "message": "投稿ボタンが見つからない"}

    except Exception as e:
        logger.exception("note投稿エラー")
        return {"status": "error", "message": str(e)}
