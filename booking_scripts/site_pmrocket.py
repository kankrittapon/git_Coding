import json
from pathlib import Path
from playwright.sync_api import Page

def booking(page: Page, branch: str, selected_day: int, selected_time_str: str):
    # โหลด config elements จากไฟล์ json
    config_path = Path("booking_elements/pmrocket.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    try:
        # กดปุ่ม Register (ถ้ามี)
        register_selector = config.get("register_button")
        if register_selector:
            page.click(register_selector)
            print("Clicked Register button")

        # รอ Branch list ขึ้นแล้วเลือก branch ที่ user เลือก
        branch_list_selector = config.get("branch_list")
        branch_buttons_selector = config.get("branch_buttons")

        if branch_list_selector and branch_buttons_selector:
            page.wait_for_selector(branch_list_selector)
            # หา list ปุ่ม branch
            branch_buttons = page.query_selector_all(f"{branch_buttons_selector} > button")
            selected_branch_index = None
            for idx, btn in enumerate(branch_buttons):
                btn_text = btn.inner_text().strip()
                if btn_text == branch:
                    selected_branch_index = idx + 1  # nth-child เริ่มที่ 1
                    break
            
            if selected_branch_index is None:
                print(f"❌ ไม่พบ branch ที่เลือก: {branch}, เลือก branch แรกแทน")
                selected_branch_index = 1
            
            branch_button_selector = f"{branch_buttons_selector} > button:nth-child({selected_branch_index})"
            page.click(branch_button_selector)
            print(f"Selected branch: {branch} (button #{selected_branch_index})")

        # กด Next หลังเลือก branch
        branch_next_button = config.get("branch_next_button")
        if branch_next_button:
            page.click(branch_next_button)
            print("Clicked Next button after branch selection")

        # เลือกวัน booking
        calendar_day_button_prefix = config.get("calendar_day_button_prefix")
        if calendar_day_button_prefix:
            day_selector = f"{calendar_day_button_prefix}{selected_day})"
            page.click(day_selector)
            print(f"Selected day: {selected_day}")

        # เลือกเวลา booking (หา button ที่ text ตรงกับ selected_time_str)
        time_buttons_selector_prefix = config.get("time_buttons_prefix")
        if time_buttons_selector_prefix:
            # ดึง list ปุ่มเวลา
            time_buttons = page.query_selector_all("#root > div > div.step > div > div.button-grid > button")
            selected_time_index = None
            for idx, btn in enumerate(time_buttons, start=1):
                btn_text = btn.inner_text().strip()
                if btn_text == selected_time_str:
                    selected_time_index = idx
                    break
            
            if selected_time_index is None:
                print(f"❌ ไม่พบเวลาที่เลือก: {selected_time_str}, เลือกเวลาแรกแทน")
                selected_time_index = 1
            
            time_selector = f"{time_buttons_selector_prefix}{selected_time_index})"
            page.click(time_selector)
            print(f"Selected time: {selected_time_str} (button #{selected_time_index})")

        # กด Next หลังเลือกวันและเวลา
        datetime_next_button = config.get("datetime_next_button")
        if datetime_next_button:
            page.click(datetime_next_button)
            print("Clicked Next button after date/time selection")

        # ติ๊ก Checkbox
        checkbox_selector = config.get("checkbox")
        if checkbox_selector:
            page.check(checkbox_selector)
            print("Checked confirmation checkbox")

        # กด Confirm Booking
        confirm_button_selector = config.get("confirm_button")
        if confirm_button_selector:
            page.click(confirm_button_selector)
            print("Clicked Confirm Booking button")

    except Exception as e:
        print(f"Error during booking steps: {e}")
