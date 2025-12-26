import os
import time
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def js_click(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    driver.execute_script("arguments[0].click();", el)


def visible(el) -> bool:
    try:
        return el.is_displayed()
    except Exception:
        return False


def click_continue_with_email(driver, wait):
    """
    Click the auth provider button for 'メールアドレスで続ける / ログイン'
    (not Google / Apple).
    """
    candidates = wait.until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, ".v-btn.v-btn--block.bg-white")
        )
    )

    target = None
    for el in candidates:
        if not visible(el):
            continue
        txt = (
            driver.execute_script(
                "return (arguments[0].innerText || '').trim();", el
            )
            or ""
        ).strip()
        if "メール" in txt and ("続ける" in txt or "ログイン" in txt):
            target = el
            break

    if not target:
        print("DEBUG: visible provider buttons:")
        for el in candidates:
            if visible(el):
                txt = (
                    driver.execute_script(
                        "return (arguments[0].innerText || '').trim();", el
                    )
                    or ""
                ).strip()
                print("-", txt)
        raise RuntimeError(
            "Could not find the 'メールアドレスで続ける / ログイン' provider button."
        )

    js_click(driver, target)
    time.sleep(1.5)


def main():
    # ---- Load credentials ----
    load_dotenv()
    EMAIL = os.getenv("FINCS_EMAIL")
    PASSWORD = os.getenv("FINCS_PASSWORD")
    if not EMAIL or not PASSWORD:
        raise RuntimeError("FINCS_EMAIL / FINCS_PASSWORD not found in .env")

    # ---- Browser setup ----
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1400,900")
    # options.add_argument("--headless=new")  # enable later on VPS

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )
    wait = WebDriverWait(driver, 60)

    try:
        # 1) Open fincs.jp
        driver.get("https://fincs.jp/")
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(1)

        # 2) Click header "登録 / ログイン"
        labels = driver.find_elements(By.CSS_SELECTOR, ".title-text.text-truncate")
        login_label = None
        for el in labels:
            if visible(el) and ("ログイン" in (el.text or "") or "登録" in (el.text or "")):
                login_label = el
                break
        if not login_label:
            raise RuntimeError("Header '登録/ログイン' not found.")
        js_click(driver, login_label)
        time.sleep(1.5)

        # 3) Click "メールアドレスで続ける"
        click_continue_with_email(driver, wait)

        # =========================================================
        # 4) LOGIN FORM (UPDATED — exactly as requested)
        # =========================================================

        # Email / Password inputs
        email_input = wait.until(
            EC.presence_of_element_located((By.ID, "input-0"))
        )
        password_input = wait.until(
            EC.presence_of_element_located((By.ID, "input-2"))
        )

        email_input.click()
        email_input.clear()
        email_input.send_keys(EMAIL)

        password_input.click()
        password_input.clear()
        password_input.send_keys(PASSWORD)

        # Login button (initially disabled)
        login_btn = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//button[contains(@class,'v-btn') "
                    "and contains(@class,'v-btn--block') "
                    "and contains(@class,'bg-main-01') "
                    "and .//span[contains(@class,'v-btn__content') "
                    "and normalize-space()='ログイン']]",
                )
            )
        )

        # Wait until button becomes enabled (Vuetify behavior)
        wait.until(
            lambda d: (
                login_btn.is_enabled()
                and login_btn.get_attribute("disabled") is None
                and "v-btn--disabled"
                not in (login_btn.get_attribute("class") or "")
            )
        )

        js_click(driver, login_btn)
        time.sleep(3)

        # =========================================================

        print("Login submitted successfully.")
        print("URL:", driver.current_url)
        print("Title:", driver.title)

        input("If login is successful, press ENTER to close...")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
