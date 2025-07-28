import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
import shutil

# import ฟังก์ชัน booking กับ load_config จาก site_rocketbooking.py
from booking_scripts.site_rocketbooking import booking, load_config as load_site_config

def load_config(path='user_config.json'):
    """
    โหลดไฟล์ user_config.json
    """
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_user_data_dir_and_executable(username, browser, profile_name):
    """
    กำหนดพาธ User Data และ Executable ของเบราว์เซอร์
    ใช้ os.path.expanduser('~') เพื่อให้พาธยืดหยุ่นกับ username ของคอมพิวเตอร์
    """
    home_dir = Path(os.path.expanduser('~')) # C:\Users\<CurrentUsername>

    if browser == 'chrome':
        base_chrome_user_data_dir = home_dir / "AppData/Local/Google/Chrome/User Data"
        
        # ชื่อโฟลเดอร์ชั่วคราวจะอ้างอิงถึงชื่อโปรไฟล์
        temp_user_data_dir = Path(f"./playwright_chrome_user_data_{profile_name}") 
        source_profile_path = base_chrome_user_data_dir / profile_name

        if not source_profile_path.is_dir():
            print(f"❌ ไม่พบโปรไฟล์ Chrome '{profile_name}' ที่พาธ: {source_profile_path}. ตรวจสอบให้แน่ใจว่าโปรไฟล์นี้มีอยู่จริงใน Chrome.")
            raise ValueError(f"ไม่พบโปรไฟล์ Chrome '{profile_name}'")
        
        if temp_user_data_dir.exists():
            shutil.rmtree(temp_user_data_dir)
            print(f"🗑️ ลบโฟลเดอร์ชั่วคราวเก่า: {temp_user_data_dir}")

        shutil.copytree(source_profile_path, temp_user_data_dir)
        print(f"📂 คัดลอกโปรไฟล์ '{profile_name}' ไปยัง: {temp_user_data_dir}")

        executable = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        return str(temp_user_data_dir), executable

    elif browser == 'edge':
        base = home_dir / f"AppData/Local/Microsoft/Edge/User Data/{profile_name}"
        executable = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        return str(base), executable

    else:
        raise ValueError("Browser ต้องเป็น chrome หรือ edge")

def load_time_config():
    """
    โหลดข้อมูลเวลาจาก branch/time.json
    """
    time_file = os.path.join("branch", "time.json")
    try:
        with open(time_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"โหลดไฟล์ time.json ไม่ได้: {e}")
        return []

# **เพิ่ม parameter สำหรับ LINE Login**
def run_browser_for_user(user_config, branch, day, time_index, line_email=None, line_password=None):
    username = user_config['username']
    browser_name = user_config['browser'].lower()
    profile_name = user_config.get('profile_name', 'Default')

    user_data_dir, executable_path = get_user_data_dir_and_executable(username, browser_name, profile_name)

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

            if browser_context.pages:
                page = browser_context.pages[0]
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    print("⚠️ แท็บเริ่มต้นโหลดไม่ทันเวลา, ลองดำเนินการต่อ...")
            else:
                page = browser_context.new_page()

            time_options = load_time_config()
            if not time_options:
                print("❌ ไม่มีข้อมูลเวลาใน time.json")
                return

            if time_index >= len(time_options):
                print("❌ ดัชนีเวลาที่เลือกไม่ถูกต้อง")
                return

            time_str = time_options[time_index]
            print(f"⏰ เวลาที่เลือก: {time_str}")

            page.goto("https://popmartth.rocket-booking.app/booking")
            page.wait_for_load_state("networkidle")
            print(f"✅ เปิด browser สำหรับ {username} ({browser_name}, โปรไฟล์: {profile_name}) เรียบร้อย")

            site_config = load_site_config()

            # **เรียก booking พร้อมส่ง line_email และ line_password**
            booking(page, branch, str(day), time_str, line_email, line_password)

            input("กด Enter เพื่อปิด browser ...")
            browser_context.close()

    finally:
        if browser_name == 'chrome' and Path(user_data_dir).exists():
            shutil.rmtree(user_data_dir)
            print(f"🗑️ ลบโฟลเดอร์ชั่วคราว: {user_data_dir}")

# **เพิ่ม parameter สำหรับ LINE Login**
def run_live_mode_for_user(username, browser, profile_name, branch, day, time_index, line_email=None, line_password=None):
    config = load_config()
    users = config.get('users', [])
    matched_users = [
        u for u in users if u['username'] == username and u['browser'] == browser and u['profile_name'] == profile_name
    ]

    if not matched_users:
        print("❌ ไม่พบ config ที่ตรงกับข้อมูลที่ระบุ")
        return

    # **ส่ง line_email และ line_password ไปยัง run_browser_for_user**
    run_browser_for_user(matched_users[0], branch, day, time_index, line_email, line_password)