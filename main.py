import json
from auth import login_user
from live_mode import run_live_mode_for_user
from trial_mode import start_trial_mode as run_trial_mode
from pathlib import Path

def get_available_profiles(username):
    with open("user_config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    user_profiles = [u for u in config["users"] if u["username"] == username]
    if not user_profiles:
        return []

    print("\n📋 โปรไฟล์ที่มีให้เลือก:")
    for i, u in enumerate(user_profiles):
        print(f"{i+1}. {u['browser']} - {u['profile_name']}")
    return user_profiles

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

def choose_time():
    times = [f"{h:02d}:{m:02d}" for h in range(10, 21) for m in (0, 30)]  # 10:00 ถึง 20:30 ครึ่งชั่วโมง
    print("\n⏰ เลือกเวลาจากรายการนี้:")
    for i, t in enumerate(times, 1):
        print(f"{i}. {t}")
    while True:
        try:
            choice = int(input("กรุณาเลือกหมายเลขเวลา: "))
            if 1 <= choice <= len(times):
                return choice  # return index (1-based)
            else:
                print("❌ เลือกหมายเลขไม่ถูกต้อง")
        except ValueError:
            print("❌ กรุณาใส่ตัวเลข")

def start():
    username = input("Username: ").strip()
    if login_user(username):
        print(f"✅ Welcome, {username}!")
        mode = input("Enter mode (live/trial): ").strip().lower()

        if mode == "live":
            profiles = get_available_profiles(username)
            if not profiles:
                print("❌ ไม่พบโปรไฟล์ใน config")
                return

            try:
                choice = int(input("เลือกหมายเลขโปรไฟล์ที่ต้องการใช้: "))
                selected = profiles[choice - 1]
                browser = selected['browser']
                profile_name = selected['profile_name']

                # รับข้อมูลเพิ่มเติมสำหรับการ booking
                branch = choose_branch()
                if branch is None:
                    print("❌ ไม่สามารถโหลดรายชื่อสาขาได้")
                    return

                day = choose_day()
                time_index = choose_time()

                # เรียก live_mode โดยส่ง branch, day, time_index ไป (ต้องแก้ live_mode.py ให้รับ parameter เพิ่มเติม)
                run_live_mode_for_user(username, browser, profile_name, branch, day, time_index)

            except (IndexError, ValueError):
                print("❌ เลือกไม่ถูกต้อง")

        elif mode == "trial":
            run_trial_mode(username)
        else:
            print("❌ Invalid mode.")
    else:
        print("❌ Invalid username.")

if __name__ == "__main__":
    start()
