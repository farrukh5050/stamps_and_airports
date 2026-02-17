from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import time
import csv


def wait_for_element(driver, by, value, timeout=20, click=True):
    """
    Waits for presence, optionally clicks. Returns the element (or None on timeout).
    """
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        if click:
            el.click()
    except TimeoutException:
        print(f"Timeout waiting for element by {by} with value {value}")


def auto_find_scroll_container(driver):
    """
    Try to find the actual scroll container used by the virtualized list.
    Returns (container_element_or_None, use_window_bool).
    """
    candidates = [
        ".cdk-virtual-scroll-viewport",
        "[class*='virtual-scroll']",
        ".gvs-body",
        "div[style*='overflow: auto']",
        "div[style*='overflow: scroll']",
    ]
    for sel in candidates:
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            try:
                h = driver.execute_script("return arguments[0].scrollHeight", el)
                c = driver.execute_script("return arguments[0].clientHeight", el)
                if h and c and h > c:
                    return el, False
            except Exception:
                continue
    return None, True  # fall back to window scrolling


def harvest_visible_pairs(driver):
    out = []
    rows = driver.find_elements(By.CSS_SELECTOR, "gvs-body-row[data-key]")
    for r in rows:
        try:
            dk = r.get_attribute("data-key")
            if not dk:
                continue

            try:
                title = r.find_element(
                    By.CSS_SELECTOR,
                    "gvs-body-cell:first-of-type .gvs-text-elipsis[title]"
                ).get_attribute("title")
            except Exception:
                title = r.find_element(
                    By.CSS_SELECTOR,
                    "gvs-body-cell:first-of-type .gvs-text-elipsis"
                ).text

            out.append((dk, title))

        except StaleElementReferenceException:
            continue
        except Exception:
            continue

    return out



def scroll_step(driver, container, use_window):
    if use_window:
        driver.execute_script(
            "window.scrollBy(0, Math.floor(window.innerHeight*0.85));"
        )
    else:
        driver.execute_script(
            "arguments[0].scrollTop = arguments[0].scrollTop + Math.floor(arguments[0].clientHeight*0.85);",
            container,
        )


def get_all_driver_pairs_virtual(driver, max_steps=1000, idle_limit=5, pause=0.35):
    """
    Walks through the entire virtualized list:
    - Collects {'title': ..., 'data_key': ...} across all rows.
    - Stops after `idle_limit` consecutive scrolls add no new keys or `max_steps`.
    """

    container, use_window = auto_find_scroll_container(driver)
    seen = set()
    results = []
    idle = 0

    for _ in range(max_steps):
        new_here = 0
        for dk, title in harvest_visible_pairs(driver):
            if dk not in seen:
                seen.add(dk)
                results.append({"title": title, "data_key": dk})
                new_here += 1

        if new_here == 0:
            idle += 1
            if idle >= idle_limit:
                break
        else:
            idle = 0

        scroll_step(driver, container, use_window)
        time.sleep(pause)

    return results


def save_to_csv(records, path="drivers.csv"):
    if not records:
        print("Nothing to save.")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "data_key"])
        w.writeheader()
        w.writerows(records)
    print(f"✅ Saved {len(records)} rows to {path}")


def login_to_ghost():
    # Set up the WebDriver (make sure you have the correct driver installed and in PATH)
    driver = webdriver.Chrome()  # or webdriver.Firefox(), etc.

    # Open the login page
    driver.get("https://portal.autocab365.com/#/login")
    time.sleep(3)  # Wait for the page to load

    # Locate the username and password fields (update selectors as needed)
    companyid_input = driver.find_element(By.ID, "input-companyid")
    username_input = driver.find_element(By.ID, "input-credentials-username")
    password_input = driver.find_element(By.ID, "input-credentials-password")

    # Enter your credentials
    companyid_input.send_keys("3162")
    driver.find_element(By.XPATH, "//div[1]/button[2]").click()  # Switch login mode
    time.sleep(1)
    username_input.send_keys("farakh")
    password_input.send_keys("4Thmarch")

    # Submit the form (update selector if needed)
    wait_for_element(driver, By.XPATH, "//form/div[2]/button", click=True)

    # goto Account V2
    wait_for_element(driver, By.XPATH, "//div/div/div[1]/div/div[4]", click=True)

    # wait for visibility of Drivers Button
    wait_for_element(
        driver, By.XPATH, "//processor/div/div[1]/div[1]/div[3]", click=True
    )

    # Click search button to load all drivers
    wait_for_element(
        driver, By.XPATH, "//filter-dockets-overlay/div/div[3]/div/button", click=True
    )

    return driver


def close_driver(driver):
    try:
        driver.quit()
        print("✅WebDriver closed.")
    except Exception:
        print("WebDriver closing encountered an issue.")


if __name__ == "__main__":
    driver = login_to_ghost()

    # WAIT FOR ALL THE DRIVERS TO LOAD
    print("Waiting for driver rows to appear...")
    wait_for_element(
        driver, By.CSS_SELECTOR, "gvs-body-row[data-key]", timeout=100, click=False
    )
    print("Driver rows appeared, starting harvest...")

    # Harvest across the full virtualized list
    pairs = get_all_driver_pairs_virtual(
        driver, max_steps=1200, idle_limit=6, pause=0.3
    )
    print(f"Collected {len(pairs)} driver entries.")
    # Preview first few
    for r in pairs[:10]:
        print(r)

    # Optional: save
    save_to_csv(pairs, "drivers.csv")

    close_driver(driver)
