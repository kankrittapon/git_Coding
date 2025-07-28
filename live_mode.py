import json
from pathlib import Path
from playwright.sync_api import sync_playwright
import shutil

def load_config(path='user_config.json'):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_user_data_dir_and_executable(username, browser, profile_name):
    # Logic สำหรับ Chrome: สร้างโฟลเดอร์ชั่วคราวและคัดลอกโปรไฟล์
    if browser == 'chrome':
        base_chrome_user_data_dir = Path(f"C:/Users/{username}/AppData/Local/Google/Chrome/User Data")
        
        # กำหนดชื่อโฟลเดอร์ชั่วคราว ไม่มี timestamp เพื่อให้ง่ายต่อการจัดการ
        temp_user_data_dir = Path(f"./playwright_chrome_user_data_{profile_name}")
        
        # ตรวจสอบว่าโฟลเดอร์โปรไฟล์ต้นฉบับมีอยู่จริง
        source_profile_path = base_chrome_user_data_dir / profile_name
        if not source_profile_path.is_dir():
            raise ValueError(f"ไม่พบโปรไฟล์ Chrome '{profile_name}' ที่พาธ: {source_profile_path}")
        
        # ลบโฟลเดอร์ชั่วคราวเก่าออกก่อนเพื่อความสะอาด
        if temp_user_data_dir.exists():
            shutil.rmtree(temp_user_data_dir)
            print(f"🗑️ ลบโฟลเดอร์ชั่วคราวเก่า: {temp_user_data_dir}")

        # คัดลอกโปรไฟล์ไปยังโฟลเดอร์ชั่วคราว
        shutil.copytree(source_profile_path, temp_user_data_dir)
        print(f"📂 คัดลอกโปรไฟล์ '{profile_name}' ไปยัง: {temp_user_data_dir}")

        executable = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        return str(temp_user_data_dir), executable

    # Logic สำหรับ Edge: ใช้พาธโปรไฟล์โดยตรง
    elif browser == 'edge':
        base = Path(f"C:/Users/{username}/AppData/Local/Microsoft/Edge/User Data/{profile_name}")
        executable = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        return str(base), executable
    else:
        raise ValueError("Browser ต้องเป็น chrome หรือ edge")

def run_browser_for_user(user_config):
    username = user_config['username']
    browser_name = user_config['browser'].lower()
    profile_name = user_config.get('profile_name', 'Default')

    user_data_dir, executable_path = get_user_data_dir_and_executable(username, browser_name, profile_name)

    # ใช้บล็อก try...finally เพื่อให้แน่ใจว่าโฟลเดอร์ชั่วคราวถูกลบเสมอ
    try:
        with sync_playwright() as p:
            args_list = [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check"
            ]
            
            browser_context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                executable_path=executable_path,
                headless=False,
                args=args_list,
            )

            # ใช้แท็บแรกที่เบราว์เซอร์เปิดขึ้นมา
            if len(browser_context.pages) > 0:
                page = browser_context.pages[0]
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    print("⚠️ แท็บเริ่มต้นโหลดไม่ทันเวลา, ลองดำเนินการต่อ...")
                    pass
            else:
                page = browser_context.new_page()

            page.goto("https://popmartth.rocket-booking.app/booking")
            page.wait_for_load_state("networkidle")
            print(f"✅ เปิด browser สำหรับ {username} ({browser_name}, โปรไฟล์: {profile_name}) เรียบร้อย")
            input("กด Enter เพื่อปิด browser ...")
            browser_context.close()

    finally:
        # ลบโฟลเดอร์ชั่วคราวสำหรับ Chrome เท่านั้น และตรวจสอบว่าโฟลเดอร์นั้นมีอยู่จริง
        if browser_name == 'chrome' and Path(user_data_dir).exists():
            shutil.rmtree(user_data_dir)
            print(f"🗑️ ลบโฟลเดอร์ชั่วคราว: {user_data_dir}")

def run_live_mode_for_user(username, browser, profile_name):
    config = load_config()
    users = config.get('users', [])
    matched_users = [
        u for u in users if u['username'] == username and u['browser'] == browser and u['profile_name'] == profile_name
    ]

    if not matched_users:
        print("❌ ไม่พบ config ที่ตรงกับข้อมูลที่ระบุ")
        return

    run_browser_for_user(matched_users[0])