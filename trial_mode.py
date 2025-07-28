import json
from pathlib import Path
from playwright.sync_api import sync_playwright
import booking_scripts.site_pmrocket as pmrocket
import booking_scripts.site_ithitec as ithitec

TRIAL_SITES = {
    "1": ("https://popmart.ithitec.com/", ithitec.booking),
    "2": ("https://pmrocketbotautoq.web.app/", pmrocket.booking)
}

BROWSERS = {
    "1": "chrome",
    "2": "edge"
}

def load_branch_list():
    branch_path = Path("branch/config.json")
    if not branch_path.exists():
        print("❌ ไม่พบไฟล์ branch/config.json")
        return []
    with open(branch_path, "r", encoding="utf-8") as f:
        branches = json.load(f)
    return branches

def choose_branch():
    branches = load_branch_list()
    if not branches:
        return None
    print("\n🏢 เลือกสาขา (Branch):")
    for i, b in enumerate(branches):
        print(f"{i+1}. {b}")
    while True:
        try:
            choice = int(input("กรุณาเลือกหมายเลขสาขา: "))
            if 1 <= choice <= len(branches):
                return branches[choice - 1]
            else:
                print("❌ เลือกหมายเลขไม่ถูกต้อง")
        except ValueError:
            print("❌ กรุณาใส่ตัวเลข")
def choose_day():
    while True:
        try:
            day = int(input("เลือกวัน (1-31): "))
            if 1 <= day <= 31:
                return day
            else:
                print("❌ เลือกวันไม่ถูกต้อง")
        except ValueError:
            print("❌ กรุณาใส่ตัวเลข")
def load_time_list():
    time_path = Path("branch/time.json")
    if not time_path.exists():
        print("❌ ไม่พบไฟล์ branch/time.json")
        return []
    with open(time_path, "r", encoding="utf-8") as f:
        times = json.load(f)
    return times

def choose_time():
    times = load_time_list()
    if not times:
        print("❌ รายการเวลาโหลดไม่สำเร็จ")
        return None

    print("\n⏰ เลือกเวลาจากรายการนี้:")
    for i, t in enumerate(times, 1):
        print(f"{i}. {t}")
    while True:
        try:
            choice = int(input("กรุณาเลือกหมายเลขเวลา: "))
            if 1 <= choice <= len(times):
                return times[choice - 1]  # คืนค่าเวลาที่เลือก (string)
            else:
                print("❌ เลือกหมายเลขไม่ถูกต้อง")
        except ValueError:
            print("❌ กรุณาใส่ตัวเลข")

def start_trial_mode(username: str):
    print(f"\n🧪 Trial Mode for {username}")

    print("\n🔸 Select website:")
    for key, (url, _) in TRIAL_SITES.items():
        print(f"{key}. {url}")
    site_choice = input("Enter site number: ").strip()
    site = TRIAL_SITES.get(site_choice)

    if not site:
        print("❌ Invalid site selection.")
        return

    site_url, booking_func = site

    print("\n🔹 Select browser:")
    print("1. Chrome")
    print("2. Edge")
    browser_choice = input("Enter browser number: ").strip()
    browser_name = BROWSERS.get(browser_choice)

    if not browser_name:
        print("❌ Invalid browser selection.")
        return

    branch = choose_branch()
    if branch is None:
        print("❌ ไม่สามารถโหลดรายชื่อสาขาได้")
        return

    day = choose_day()
    time_str = choose_time()
    if time_str is None:
        print("❌ เลือกเวลาไม่ถูกต้อง")
        return

    try:
        with sync_playwright() as p:
            browser_type = getattr(p, "chromium")

            if browser_name == "chrome":
                browser = browser_type.launch(headless=False, channel="chrome")
            elif browser_name == "edge":
                browser = browser_type.launch(headless=False, channel="msedge")

            page = browser.new_page()
            page.goto(site_url)
            print(f"🌐 Opened {site_url} in {browser_name.capitalize()}")

            # เรียกฟังก์ชัน booking พร้อมส่งค่า branch, day, time
            booking_func(page, branch, day, time_str)

            input("🕹️ Press Enter to close browser...")
            browser.close()

    except Exception as e:
        print(f"❌ Error: {e}")
