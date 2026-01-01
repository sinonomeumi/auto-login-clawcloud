# 文件名: login_script.py
# 作用: 自动登录 ClawCloud Run，支持 GitHub 账号密码 + 2FA 自动验证 + Telegram 通知

import os
import time
import requests
import pyotp
from playwright.sync_api import sync_playwright


def tg_notify(message):
    """发送 Telegram 通知"""
    bot_token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")

    if not bot_token or not chat_id:
        print("⚠️ Telegram 未配置，跳过通知")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"⚠️ Telegram 通知失败: {e}")


def run_login():
    # 1. 获取环境变量中的敏感信息
    username = os.environ.get("GH_USERNAME")
    password = os.environ.get("GH_PASSWORD")
    totp_secret = os.environ.get("GH_2FA_SECRET")

    if not username or not password:
        msg = "❌ *错误*: 必须设置 GH_USERNAME 和 GH_PASSWORD"
        print(msg)
        tg_notify(msg)
        return

    tg_notify("🚀 *ClawCloud 自动登录任务开始*")

    print("🚀 [Step 1] 启动浏览器...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        # 2. 访问 ClawCloud 登录页
        target_url = "https://ap-northeast-1.run.claw.cloud/"
        print(f"🌐 [Step 2] 正在访问: {target_url}")
        page.goto(target_url)
        page.wait_for_load_state("networkidle")

        # 3. 点击 GitHub 登录按钮
        print("🔍 [Step 3] 寻找 GitHub 按钮...")
        try:
            login_button = page.locator("button:has-text('GitHub')")
            login_button.wait_for(state="visible", timeout=10000)
            login_button.click()
            print("✅ GitHub 按钮已点击")
        except Exception as e:
            print(f"⚠️ 未找到 GitHub 按钮: {e}")

        # 4. GitHub 登录
        print("⏳ [Step 4] 等待跳转 GitHub...")
        try:
            page.wait_for_url(lambda url: "github.com" in url, timeout=15000)

            if "login" in page.url:
                print("🔒 输入 GitHub 账号密码...")
                page.fill("#login_field", username)
                page.fill("#password", password)
                page.click("input[name='commit']")
        except Exception as e:
            print(f"ℹ️ 跳过账号密码步骤: {e}")

        # 5. 处理 2FA
        page.wait_for_timeout(3000)
        if "two-factor" in page.url or page.locator("#app_totp").count() > 0:
            print("🔐 检测到 GitHub 2FA")

            if not totp_secret:
                msg = "🚨 *登录失败*\n❌ 检测到 GitHub 2FA，但未配置 GH_2FA_SECRET"
                print(msg)
                tg_notify(msg)
                exit(1)

            try:
                totp = pyotp.TOTP(totp_secret)
                token = totp.now()
                page.fill("#app_totp", token)
                print("✅ 2FA 验证码已填写")
            except Exception as e:
                msg = f"❌ *2FA 验证失败*\n{e}"
                print(msg)
                tg_notify(msg)
                exit(1)

        # 6. 授权页面
        page.wait_for_timeout(3000)
        if "authorize" in page.url.lower():
            print("⚠️ 检测到授权页面，尝试点击 Authorize")
            try:
                page.click("button:has-text('Authorize')", timeout=5000)
            except:
                pass

        # 7. 等待最终跳转
        print("⏳ [Step 6] 等待跳转回 ClawCloud...")
        page.wait_for_timeout(20000)

        final_url = page.url
        print(f"📍 最终 URL: {final_url}")

        page.screenshot(path="login_result.png")
        print("📸 已保存截图 login_result.png")

        # 8. 判断是否成功
        is_success = False
        if page.get_by_text("App Launchpad").count() > 0:
            is_success = True
        elif "console" in final_url or "private-team" in final_url:
            is_success = True
        elif "github.com" not in final_url:
            is_success = True

        if is_success:
            msg = (
                "🎉 *ClawCloud 登录成功*\n"
                f"📍 `{final_url}`"
            )
            print("🎉 登录成功")
            tg_notify(msg)
        else:
            msg = (
                "❌ *ClawCloud 登录失败*\n"
                "📸 请查看 login_result.png"
            )
            print("😭 登录失败")
            tg_notify(msg)
            exit(1)

        browser.close()


if __name__ == "__main__":
    run_login()
