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
    driver.execute_script(
        "arguments[0].scrollIntoView({block:'center'});", el
    )
    driver.execute_script("arguments[0].click();", el)


def visible(el) -> bool:
    try:
        return el.is_displayed()
    except Exception:
        return False


def click_continue_with_email(driver, wait):
    """
    Click the auth provider button for
    'メールアドレスで続ける / ログイン'
    (NOT Google / Apple).
    """
    candidates = wait.until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, ".v-btn.v-btn--block.bg-white")
        )
    )

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
            js_click(driver, el)
            time.sleep(1.5)
            return

    raise RuntimeError("Could not find メールアドレスで続ける / ログイン button.")


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
        wait.until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(1)

        # 2) Open auth modal (try header "登録/ログイン", but don't hard-fail if UI changed)
        def open_login_entrypoint():
            # Strategy A: click any visible button/link with 登録 or ログイン text
            try:
                candidates = driver.find_elements(
                    By.XPATH,
                    "//*[self::a or self::button or @role='button']"
                    "[contains(normalize-space(.),'ログイン') or contains(normalize-space(.),'登録')]",
                )
                for el in candidates:
                    if visible(el):
                        js_click(driver, el)
                        time.sleep(1.5)
                        return True
            except Exception:
                pass

            # Strategy B: old selector (label span) but click a clickable ancestor like open_fincs.py
            try:
                labels = driver.find_elements(By.CSS_SELECTOR, ".title-text.text-truncate")
                for label in labels:
                    if not visible(label):
                        continue
                    if ("ログイン" not in (label.text or "")) and ("登録" not in (label.text or "")):
                        continue
                    clickable = None
                    xpath_clickable = (
                        "./ancestor-or-self::*[self::a or self::button or @role='button' or @onclick][1]"
                    )
                    parents = label.find_elements(By.XPATH, xpath_clickable)
                    if parents:
                        clickable = parents[0]
                    else:
                        fallback = label.find_elements(
                            By.XPATH, "./ancestor-or-self::div[1] | ./ancestor-or-self::li[1]"
                        )
                        if fallback:
                            clickable = fallback[0]
                    if clickable:
                        js_click(driver, clickable)
                        time.sleep(1.5)
                        return True
            except Exception:
                pass

            # Strategy C: direct login URL fallback (site sometimes routes auth here)
            try:
                driver.get("https://fincs.jp/login")
                wait.until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                time.sleep(1.0)
                return True
            except Exception:
                return False

        open_login_entrypoint()

        # 3) Click "メールアドレスで続ける"
        click_continue_with_email(driver, wait)

        # =========================================================
        # 4) LOGIN FORM (VUETIFY-SAFE, PLACEHOLDER-BASED)
        # =========================================================

        # Don't assume Vuetify renders a visible v-dialog/v-overlay here (it may route to a page).
        # Instead, wait for the actual login inputs to exist.
        email_input_xpath = "//input[@type='text' and contains(@placeholder,'メールアドレス')]"
        password_input_xpath = "//input[@type='password' and contains(@placeholder,'パスワード')]"
        wait.until(
            lambda d: d.find_elements(By.XPATH, email_input_xpath)
            and d.find_elements(By.XPATH, password_input_xpath)
        )
        time.sleep(0.2)

        def fill_input(xpath: str, value: str):
            el = wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
            js_click(driver, el)
            time.sleep(0.1)
            try:
                el.clear()
            except Exception:
                # Vuetify inputs sometimes don't clear properly; fall back to select-all delete
                el.send_keys("\ue009" + "a")  # CTRL + A
                el.send_keys("\ue003")  # BACKSPACE
            el.send_keys(value)

        # ---- Email: must be <input type="text"> ----
        fill_input(email_input_xpath, EMAIL)

        # ---- Password: must be <input type="password"> ----
        fill_input(password_input_xpath, PASSWORD)

        # ---- Login button (wait until actually enabled + clickable) ----
        login_btn_xpath = (
            "//button[@type='submit' and contains(@class,'v-btn') "
            "and contains(@class,'v-btn--block') "
            "and contains(@class,'bg-main-01') "
            "and .//span[contains(@class,'v-btn__content') and normalize-space()='ログイン']]"
        )

        wait.until(lambda d: d.find_element(By.XPATH, login_btn_xpath))
        wait.until(
            lambda d: (
                (btn := d.find_element(By.XPATH, login_btn_xpath)).is_enabled()
                and btn.get_attribute("disabled") is None
                and "v-btn--disabled" not in (btn.get_attribute("class") or "")
            )
        )
        login_btn = wait.until(EC.element_to_be_clickable((By.XPATH, login_btn_xpath)))
        js_click(driver, login_btn)
        time.sleep(3)

        # =========================================================
        # 5) AFTER LOGIN: click "この講座のトークページへ" if present
        # =========================================================
        talk_btn_xpath = (
            "//button[contains(@class,'v-btn') and contains(@class,'v-btn--block') "
            "and .//span[contains(@class,'v-btn__content') "
            "and contains(normalize-space(.),'この講座のトークページへ')]]"
        )

        try:
            # Wait a bit for the post-login page to render
            talk_wait = WebDriverWait(driver, 20)
            talk_btn = talk_wait.until(EC.presence_of_element_located((By.XPATH, talk_btn_xpath)))
            talk_btn = talk_wait.until(EC.element_to_be_clickable((By.XPATH, talk_btn_xpath)))
            js_click(driver, talk_btn)
            time.sleep(2)
            print("Clicked: この講座のトークページへ")
            print("URL after click:", driver.current_url)
        except Exception:
            # Not all accounts/pages show this CTA; keep script usable.
            pass

        # =========================================================

        print("Login submitted successfully.")
        print("URL:", driver.current_url)
        print("Title:", driver.title)

        input("If login is successful, press ENTER to close...")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
