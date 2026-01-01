# 文件名: login_script.py
# 作用: 自动登录 ClawCloud Run（GitHub + 2FA）+ Telegram 通知（零第三方依赖）

import os
import urllib.request
import urllib.parse
import pyotp
from playwright.sync_api import sync_playwright


def tg_notify(message):
    bot_token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")

    if not bot_token or not chat_id:
        print("⚠️ Telegram 未配置，跳过通知")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"⚠️ Telegram 通知失败: {e}")


def run_login():
    username = os.environ.get("GH_USERNAME")
    password = os.environ.get("GH_PASSWORD")
    totp_secret = os.environ.get("GH_2FA_SECRET")

    if not username or not password:
        msg = "❌ 必须设置 GH_USERNAME 和 GH_PASSWORD"
        print(msg)
        tg_notify(msg)
        return

    tg_notify("🚀 *ClawCloud 自动登录开始*")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        page.goto("https://ap-northeast-1.run.claw.cloud/")
        page.wait_for_load_state("networkidle")

        # GitHub 登录按钮
        try:
            page.locator("button:has-text('GitHub')").click(timeout=10000)
        except:
            pass

        # GitHub 登录页
        try:
            page.wait_for_url(lambda url: "github.com" in url, timeout=15000)
            if "login" in page.url:
                page.fill("#login_field", username)
                page.fill("#password", password)
                page.click("input[name='commit']")
        except:
            pass

        # 2FA
        page.wait_for_timeout(3000)
        if "two-factor" in page.url or page.locator("#app_totp").count() > 0:
            if not totp_secret:
                msg = "🚨 登录失败：缺少 GH_2FA_SECRET"
                print(msg)
                tg_notify(msg)
                exit(1)

            token = pyotp.TOTP(totp_secret).now()
            page.fill("#app_totp", token)

        # 授权
        page.wait_for_timeout(3000)
        if "authorize" in page.url.lower():
            try:
                page.click("button:has-text('Authorize')")
            except:
                pass

        # 等待跳转
        page.wait_for_timeout(20000)
        final_url = page.url
        page.screenshot(path="login_result.png")

        success = (
            "github.com" not in final_url and
            "signin" not in final_url
        )

        if success:
            msg = f"🎉 *ClawCloud 登录成功*\n`{final_url}`"
            print("🎉 登录成功")
            tg_notify(msg)
        else:
            msg = "❌ *ClawCloud 登录失败*，请查看截图"
            print("😭 登录失败")
            tg_notify(msg)
            exit(1)

        browser.close()


if __name__ == "__main__":
    run_login()
