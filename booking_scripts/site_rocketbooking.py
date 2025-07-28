import time
from playwright.sync_api import Page, TimeoutError
import json
from pathlib import Path
import shutil

# CONFIG_PATH (ยังคงเหมือนเดิม)
CONFIG_PATH = Path("booking_elements/rocketbooking.json")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        full_config = json.load(f)
        return full_config.get("selectors", {})

def wait_for_captcha_and_confirm(page: Page, config):
    # โค้ดส่วนนี้ยังคงเดิม
    captcha_form_selector = config.get("captcha_form_selector")
    captcha_begin_button = config.get("captcha_begin_button")
    captcha_confirm_button = config.get("captcha_confirm_button")

    if captcha_form_selector and page.query_selector(captcha_form_selector):
        print("⚠️ พบ CAPTCHA Form")
        if page.query_selector(captcha_begin_button):
            print("กรุณากดปุ่ม Begin CAPTCHA เพื่อดำเนินการต่อ...")
            while page.query_selector(captcha_begin_button):
                time.sleep(1)
            print("ปุ่ม Begin ถูกกดแล้ว กำลังรอ CAPTCHA ผ่าน...")

        if page.query_selector(captcha_confirm_button):
            print("กรุณากดปุ่ม Confirm CAPTCHA เพื่อดำเนินการต่อ...")
            while page.query_selector(captcha_confirm_button):
                time.sleep(1)
            print("ปุ่ม Confirm CAPTCHA ถูกกดแล้ว")

        while page.query_selector(captcha_form_selector):
            time.sleep(1)
        print("✅ CAPTCHA ผ่านแล้ว")

def perform_line_login(page: Page, config, line_email: str, line_password: str):
    # โค้ดส่วนนี้ยังคงเดิม ไม่ได้มีการเปลี่ยนแปลงตามคำขอปัจจุบัน
    profile_button_selector = config.get("profile_button")
    line_connect_button_initial = config.get("line_connect_button_initial")
    line_connect_account_button = config.get("line_connect_account_button")
    line_login_email_field = config.get("line_login_email_field")
    line_login_password_field = config.get("line_login_password_field")
    line_login_button = config.get("line_login_button")
    line_verification_code_text = config.get("line_verification_code_text")

    print(f"DEBUG perform_line_login: line_email: {line_email}, line_password: {'*' * len(line_password) if line_password else 'None'}")
    
    if not all([line_login_email_field, line_login_password_field, line_login_button]):
        print("❌ Selector สำหรับ LINE Login ไม่ครบถ้วนใน config. ไม่สามารถดำเนินการได้.")
        return False

    print("กำลังมองหาปุ่ม 'Connect' แรกสุด...")
    try:
        page.locator(line_connect_button_initial).click(timeout=20000) 
        print("Clicked initial 'Connect' button.")
        page.wait_for_load_state("domcontentloaded", timeout=5000)
        page.wait_for_timeout(1000)
    except TimeoutError:
        print("⚠️ ไม่พบปุ่ม 'Connect' (เริ่มต้น) หรือไม่สามารถคลิกได้ภายใน 20 วินาที. ดำเนินการต่อเพื่อหาปุ่มถัดไป.")
        pass

    print("กำลังมองหาปุ่ม 'Connect LINE Account*'...")
    try:
        page.locator(line_connect_account_button).click(timeout=20000) 
        print("Clicked 'Connect LINE Account*' button.")
    except TimeoutError:
        print("❌ ไม่พบปุ่ม 'Connect LINE Account*' หรือปุ่มไม่พร้อมใช้งาน. ไม่สามารถดำเนินการเชื่อมต่อ LINE ได้.")
        return False

    print("รอหน้า LINE Login โหลด...")
    try:
        page.wait_for_selector(line_login_email_field, state="visible", timeout=30000)
        print("หน้า LINE Login โหลดแล้ว.")
    except TimeoutError:
        print("❌ หน้า LINE Login ไม่โหลดขึ้นมาภายในเวลาที่กำหนด. ไม่สามารถดำเนินการต่อได้.")
        return False

    if line_email and line_password:
        print("กำลังกรอกข้อมูล LINE Login อัตโนมัติ...")
        page.fill(line_login_email_field, line_email)
        print(f"กรอก Email: {line_email}")

        page.fill(line_login_password_field, line_password)
        print("กรอก Password แล้ว.")

        page.click(line_login_button)
        print("คลิกปุ่ม Login แล้ว.")
    else:
        print("❌ ไม่พบ Email หรือ Password สำหรับ LINE Login ใน config_line_user.json. จะต้องดำเนินการด้วยตนเอง.")
        input("กรุณาทำการล็อกอิน LINE ในหน้าเว็บที่เปิดขึ้น (ด้วยตนเอง) และกด Enter เพื่อดำเนินการต่อ: ")
    
    print("รอการเปลี่ยนหน้าหลังจาก Login LINE (สูงสุด 60 วินาที)...")
    try:
        page.wait_for_load_state("networkidle", timeout=60000) 
        
        if line_verification_code_text and page.query_selector(line_verification_code_text):
            code = page.text_content(line_verification_code_text)
            print(f"⚠️ พบหน้ายืนยันรหัส LINE: โปรดยืนยันรหัสนี้ ({code}) บนมือถือของคุณ")
            input("หลังจากยืนยันในมือถือแล้ว กด Enter เพื่อดำเนินการต่อ...")
            page.wait_for_load_state("networkidle", timeout=60000)
        
        print("คลิกปุ่ม Profile อีกครั้งเพื่อรีเฟรชสถานะ LINE Login...")
        try:
            page.locator(profile_button_selector).click(timeout=5000)
            page.wait_for_load_state("networkidle", timeout=10000) 
        except TimeoutError:
            print("⚠️ ไม่สามารถคลิกปุ่ม Profile อีกครั้งเพื่อยืนยัน LINE Login ได้")
            return False 

        if page.query_selector(line_connect_button_initial) is None:
            print("✅ กระบวนการ Login LINE อัตโนมัติเสร็จสมบูรณ์และยืนยันแล้ว.")
            return True
        else:
            print("❌ ปุ่ม Connect ยังปรากฏอยู่หลัง Login LINE. กระบวนการไม่สมบูรณ์.")
            return False

    except TimeoutError:
        print("❌ ไม่สามารถยืนยันการเปลี่ยนหน้าหลังจาก Login LINE ได้.")
        return False
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดที่ไม่คาดคิดใน perform_line_login: {e}")
        return False


def check_line_login(page: Page, config, line_email: str = None, line_password: str = None):
    # โค้ดส่วนนี้ยังคงเหมือนเดิม
    profile_button_selector = config.get("profile_button")
    line_connect_button_initial = config.get("line_connect_button_initial")
    
    print("ตรวจสอบสถานะการล็อกอิน LINE ...")

    if not profile_button_selector:
        print("❌ ไม่พบ Selector สำหรับปุ่ม Profile")
        return False

    print("รอหน้าหลักโหลดให้พร้อมก่อนคลิกปุ่ม Profile...")
    try:
        page.wait_for_url("https://popmartth.rocket-booking.app/booking", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000) 
        page.locator(profile_button_selector).wait_for(state="visible", timeout=10000) 
        print("หน้าหลักโหลดพร้อมและปุ่ม Profile ปรากฏ.")
    except TimeoutError:
        print("❌ หน้าหลักโหลดไม่ทันเวลา หรือปุ่ม Profile ไม่ปรากฏหลังจากโหลด.")
        return False

    try:
        page.click(profile_button_selector)
        print("Clicked Profile button.")
        
        print("รอการแสดงผลสถานะ LINE Login บนหน้าโปรไฟล์...")
        try:
            page.wait_for_selector(line_connect_button_initial, state="visible", timeout=15000) 
            
            print("❌ ยังไม่ได้เชื่อมต่อบัญชี LINE. กำลังเริ่มกระบวนการล็อกอิน LINE...")
            
            login_successful = perform_line_login(page, config, line_email, line_password)
            
            return login_successful 
        
        except TimeoutError:
            print("✅ ผู้ใช้ล็อกอิน LINE แล้ว (ไม่พบปุ่มเชื่อมต่อ LINE หลังจากรอ)")
            return True
    
    except TimeoutError:
        print("❌ ปุ่ม Profile ไม่ปรากฏให้คลิกหลังจากหน้าโหลด, ไม่สามารถตรวจสอบ LINE Login ได้")
        return False

# --- ฟังก์ชัน check_for_events ที่ปรับปรุงใหม่โดยใช้ปุ่ม Register เป็นตัวหลัก ---
def check_for_events(page: Page, config):
    """
    ตรวจสอบว่ามี Event ให้จองหรือไม่ โดยอ้างอิงจากปุ่ม Register
    และข้อความ 'ไม่มีอีเว้นต์ในขณะนี้' เป็นตัวสำรอง
    """
    register_button_selector = config.get("register_button")
    no_event_text_selector = config.get("no_event_text_selector") # เช่น "ไม่มีอีเว้นต์ในขณะนี้"

    print("กำลังตรวจสอบ Event ที่มีให้จอง...")

    # Step 1: ตรวจสอบว่าปุ่ม Register ปรากฏหรือไม่
    try:
        # Playwright จะรอให้ปุ่ม Register มองเห็นได้และพร้อมคลิก
        page.locator(register_button_selector).wait_for(state="visible", timeout=10000) 
        print("✅ พบปุ่ม 'Register'. มี Event ให้จอง.")
        return True
    except TimeoutError:
        # ถ้าไม่พบปุ่ม Register ภายในเวลาที่กำหนด
        print(f"ไม่พบปุ่ม 'Register' ({register_button_selector}) ภายในเวลาที่กำหนด. กำลังตรวจสอบข้อความ 'ไม่มีอีเว้นต์'.")
        
        # Step 2: ตรวจสอบข้อความ "ไม่มีอีเว้นต์ในขณะนี้"
        try:
            # ใช้ text= ใน selector เพื่อหาข้อความที่ตรงกัน
            page.wait_for_selector(f"text={no_event_text_selector}", state="visible", timeout=5000) 
            print(f"❌ ไม่พบ Event ให้จอง: พบข้อความ '{no_event_text_selector}'.")
            return False
        except TimeoutError:
            print("❌ ไม่พบ Event ให้จอง: ไม่พบปุ่ม 'Register' และไม่พบข้อความแจ้งว่าไม่มีกิจกรรม.")
            return False
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการตรวจสอบ Event: {e}")
        return False


def booking(page: Page, branch: str, selected_day: int, selected_time_str: str, line_email: str = None, line_password: str = None):
    config = load_config()

    wait_for_captcha_and_confirm(page, config)

    if not check_line_login(page, config, line_email, line_password):
        print("❌ การล็อกอิน LINE ไม่สำเร็จ หรือผู้ใช้ไม่ได้ดำเนินการต่อ. การจองถูกยกเลิก.")
        return
    
    # --- คลิกปุ่ม "Booking" เพื่อไปยังหน้า Event ---
    booking_page_button_selector = config.get("booking_page_button")
    if booking_page_button_selector:
        print("กำลังคลิกปุ่ม 'Booking' เพื่อไปยังหน้า Event...")
        try:
            page.locator(booking_page_button_selector).click(timeout=10000)
            print("Clicked 'Booking' button.")
            page.wait_for_load_state("networkidle", timeout=15000) # รอให้หน้า Event โหลด
        except TimeoutError:
            print("❌ ไม่พบปุ่ม 'Booking' หรือไม่สามารถคลิกได้. ไม่สามารถดำเนินการจองต่อได้.")
            return
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการคลิกปุ่ม 'Booking': {e}")
            return
    else:
        print("⚠️ ไม่พบ Selector สำหรับปุ่ม 'Booking' ใน config. ข้ามการคลิกปุ่ม 'Booking'.")

    # --- เรียกใช้ check_for_events หลังจากคลิกปุ่ม "Booking" ---
    if not check_for_events(page, config):
        print("⚠️ ไม่มี Event ให้จองในขณะนี้. บอทจะปิดการทำงาน.")
        return # ปิดการทำงานของบอทหากไม่มี Event

    # --- ส่วนนี้จะถูกย้ายขึ้นไปตรวจสอบใน check_for_events แล้ว ---
    # กดปุ่ม Register
    register_selector = config.get("register_button")
    if register_selector and page.query_selector(register_selector):
        page.click(register_selector)
        print("Clicked Register button")
    # else: ถ้าไม่เจอ register_button ตรงนี้อาจจะหมายถึงไม่มี event ให้จองจริงๆ ก็ควร return ไปแล้ว
    # จึงไม่ต้องมี else นี้

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except TimeoutError:
        print("⚠️ โหลดหน้า Register ไม่ทันเวลา, อาจมีปัญหา")
    wait_for_captcha_and_confirm(page, config)

    # ... โค้ดส่วนที่เหลือของการจอง ...
    # (Select สาขา, วัน, เวลา และ Confirm จะอยู่ตรงนี้)
    # ลอจิกการคลิกปุ่ม Register ที่เคยอยู่ด้านบนถูกย้ายไปใน check_for_events แล้ว
    # ดังนั้นควรลบออก หรือปรับเปลี่ยนถ้าต้องการให้คลิกอีกครั้งหลังเลือก Event
    # แต่โดยทั่วไป, การคลิก Register เพื่อเข้าสู่ flow การจองจะทำแค่ครั้งเดียว

    # เลือกสาขา (branch)
    branch_list_selector = config.get("branch_list")
    branch_buttons_selector = config.get("branch_buttons")
    if branch_list_selector and branch_buttons_selector:
        page.wait_for_selector(branch_list_selector, state="visible", timeout=15000)
        branch_buttons = page.query_selector_all(f"{branch_buttons_selector} > button")
        selected_branch_index = None
        for idx, btn in enumerate(branch_buttons):
            btn_text = btn.inner_text().strip()
            if btn_text == branch:
                selected_branch_index = idx + 1
                break

        if selected_branch_index is None:
            print(f"❌ ไม่พบสาขาที่เลือก: {branch}, เลือกสาขาแรกแทน")
            selected_branch_index = 1

        branch_button_selector = f"{branch_buttons_selector} > button:nth-child({selected_branch_index})"
        page.click(branch_button_selector)
        print(f"Selected branch: {branch} (button #{selected_branch_index})")

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except TimeoutError:
        print("⚠️ โหลดหน้าหลังเลือกสาขาไม่ทันเวลา, อาจมีปัญหา")
    wait_for_captcha_and_confirm(page, config)

    # กด Next หลังเลือก branch
    branch_next_button = config.get("branch_next_button")
    if branch_next_button and page.query_selector(branch_next_button):
        page.click(branch_next_button)
        print("Clicked Next button after branch selection")

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except TimeoutError:
        print("⚠️ โหลดหน้าหลังกด Next สาขาไม่ทันเวลา, อาจมีปัญหา")
    wait_for_captcha_and_confirm(page, config)

    # เลือกวัน booking
    calendar_grid_selector = config.get("calendar_grid")
    if calendar_grid_selector:
        page.wait_for_selector(calendar_grid_selector, state="visible", timeout=15000)
        day_buttons = page.query_selector_all(f"{calendar_grid_selector} > button.day-cell")

        selected_day_button = None
        for btn in day_buttons:
            if btn.inner_text().strip() == str(selected_day):
                selected_day_button = btn
                break

        if selected_day_button:
            selected_day_button.click()
            print(f"Selected day: {selected_day}")
        else:
            print(f"❌ ไม่พบวันที่ {selected_day} ในปฏิทิน")
            return

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except TimeoutError:
        print("⚠️ โหลดหน้าหลังเลือกวันไม่ทันเวลา, อาจมีปัญหา")
    wait_for_captcha_and_confirm(page, config)

    # เลือกเวลา booking
    time_buttons_selector = config.get("time_buttons_selector")
    if time_buttons_selector:
        page.wait_for_selector(time_buttons_selector, state="visible", timeout=15000)
        time_buttons = page.query_selector_all(time_buttons_selector + " > button")

        selected_time_index = None
        for idx, btn in enumerate(time_buttons, start=1):
            if btn.inner_text().strip() == selected_time_str:
                selected_time_index = idx
                break

        if selected_time_index is None:
            print(f"❌ ไม่พบเวลาที่เลือก: {selected_time_str}, เลือกเวลาแรกแทน")
            selected_time_index = 1

        time_selector = f"{time_buttons_selector} > button:nth-child({selected_time_index})"
        page.click(time_selector)
        print(f"Selected time: {selected_time_str} (button #{selected_time_index})")

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except TimeoutError:
        print("⚠️ โหลดหน้าหลังเลือกเวลาไม่ทันเวลา, อาจมีปัญหา")
    wait_for_captcha_and_confirm(page, config)

    # กด Next หลังเลือกวันและเวลา
    datetime_next_button = config.get("datetime_next_button")
    if datetime_next_button and page.query_selector(datetime_next_button):
        page.click(datetime_next_button)
        print("Clicked Next button after date/time selection")

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except TimeoutError:
        print("⚠️ โหลดหน้าหลังกด Next วัน/เวลาไม่ทันเวลา, อาจมีปัญหา")
    wait_for_captcha_and_confirm(page, config)

    # ติ๊ก Checkbox
    checkbox_selector = config.get("checkbox")
    if checkbox_selector and page.query_selector(checkbox_selector):
        page.check(checkbox_selector)
        print("Checked confirmation checkbox")

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except TimeoutError:
        print("⚠️ โหลดหน้าหลังติ๊ก Checkbox ไม่ทันเวลา, อาจมีปัญหา")
    wait_for_captcha_and_confirm(page, config)

    # กด Confirm Booking
    confirm_button_selector = config.get("confirm_button")
    if confirm_button_selector and page.query_selector(confirm_button_selector):
        page.click(confirm_button_selector)
        print("Clicked Confirm Booking button")

    print("✅ จองสำเร็จ")