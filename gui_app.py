import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
import threading
import sys
import os
import datetime
import schedule
import time as time_module

# เพิ่มพาธของโฟลเดอร์แม่เพื่อให้สามารถ import live_mode และ trial_mode ได้
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))

from live_mode import run_live_mode_for_user
from trial_mode import start_trial_mode, TRIAL_SITES, BROWSERS # นำเข้า start_trial_mode และตัวเลือกจาก trial_mode

# --- พาธไปยัง config ไฟล์ต่างๆ ---
USER_CONFIG_PATH = Path("user_config.json")
LINE_USER_CONFIG_PATH = Path("booking_elements/config_line_user.json")
BRANCH_CONFIG_PATH = Path("branch/config.json")
TIME_CONFIG_PATH = Path("branch/time.json")
SCHEDULE_CONFIG_PATH = Path("booking_elements/schedule_config.json")

# กำหนดค่า Role เริ่มต้น (ใช้เป็นค่า fallback หากข้อมูลจาก Google Sheet ไม่สมบูรณ์)
DEFAULT_USER_ROLES = {
    "admin": {
      "max_profiles": 999,
      "can_use_scheduler": True
    },
    "vip2": {
      "max_profiles": 5,
      "can_use_scheduler": True
    },
    "vip1": {
      "max_profiles": 3,
      "can_use_scheduler": True
    },
    "normal": {
      "max_profiles": 1,
      "can_use_scheduler": False
    }
}

class BookingApp:
    def __init__(self, root, all_configs, gsheet_users_data):
        self.root = root
        self.root.title("Popmartth Rocket Booking Bot UI (แยก Main)")
        self.root.geometry("800x800") # ขยายหน้าต่างให้ใหญ่ขึ้นเพื่อรองรับ Config Tab

        # Load configs (รับมาจาก main.py)
        self.users_data = all_configs['user_profiles'].get("users", []) # Profiles from user_config.json
        self.line_accounts = all_configs['line_accounts'] # LINE accounts from config_line_user.json
        self.branches = all_configs['branches'] # Branches from branch/config.json
        self.times = all_configs['times'] # Times from branch/time.json
        self.gsheet_users_data = gsheet_users_data # User credentials from Google Sheet (from main.py)
        
        # Schedule config (โหลดเองเพราะ GUI เป็นผู้จัดการการเพิ่ม/แก้ไข)
        self.scheduled_bookings = self._load_json_config_for_gui(SCHEDULE_CONFIG_PATH).get("scheduled_bookings", [])

        # User session variables
        self.logged_in_username = None
        self.user_role = None
        self.max_allowed_profiles = 0
        self.can_use_scheduler = False

        # Scheduler
        self.scheduler_thread = None
        self.scheduler_running = False
        self.job_refs = {}

        self._create_widgets()
        self._populate_initial_data()
        self._update_scheduled_jobs_display()
        self._update_user_profiles_display() # อัปเดต Treeview ของ User Profiles
        self._update_line_accounts_display() # อัปเดต Treeview ของ LINE Accounts

        sys.stdout = TextRedirector(self.log_text, 'stdout')
        sys.stderr = TextRedirector(self.log_text, 'stderr')
        
    def _load_json_config_for_gui(self, path):
        """Helper to load JSON config safely (for GUI's internal files like schedule_config and new config tabs)."""
        try:
            if not path.exists():
                # สร้างไฟล์เปล่าหากไม่พบ
                empty_data = {}
                if path == SCHEDULE_CONFIG_PATH:
                    empty_data = {"scheduled_bookings": []}
                elif path == USER_CONFIG_PATH:
                    empty_data = {"users": []}
                elif path == LINE_USER_CONFIG_PATH:
                    empty_data = {"line_accounts": []}

                with open(path, "w", encoding="utf-8") as f:
                    json.dump(empty_data, f, indent=2, ensure_ascii=False) # เพิ่ม ensure_ascii=False
                self.log_message(f"✅ สร้างไฟล์ config เปล่าที่ {path} แล้ว.")
                return empty_data
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            messagebox.showerror("Error", f"Invalid JSON in config file: {path}")
            return {}
        except Exception as e:
            messagebox.showerror("Error", f"Could not load config file {path}: {e}")
            return {}

    def _save_json_config_for_gui(self, path, data):
        """Helper to save JSON config safely."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False) # เพิ่ม ensure_ascii=False
            self.log_message(f"✅ Config saved to {path}")
        except Exception as e:
            self.log_message(f"❌ Failed to save config to {path}: {e}")
            messagebox.showerror("Error", f"Failed to save config to {path}: {e}")

    def _create_widgets(self):
        # --- Login Frame (Common for both tabs, placed at the top of root) ---
        # *** PACK Login Frame ก่อน ***
        login_main_frame = ttk.LabelFrame(self.root, text="ล็อกอินเข้าสู่ระบบ", padding=10)
        login_main_frame.pack(padx=10, pady=5, fill="x", side="top") 
        
        ttk.Label(login_main_frame, text="Username:").grid(row=0, column=0, sticky="w", pady=2)
        self.login_username_entry = ttk.Entry(login_main_frame)
        self.login_username_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        
        ttk.Label(login_main_frame, text="Password:").grid(row=1, column=0, sticky="w", pady=2)
        self.login_password_entry = ttk.Entry(login_main_frame, show="*")
        self.login_password_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.login_password_entry.bind("<Return>", lambda event: self._attempt_login())
        
        self.login_main_button = ttk.Button(login_main_frame, text="Login", command=self._attempt_login)
        self.login_main_button.grid(row=2, column=0, columnspan=2, pady=5)

        self.login_status_label = ttk.Label(login_main_frame, text="สถานะ: ยังไม่ได้ล็อกอิน")
        self.login_status_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=2)

        login_main_frame.grid_columnconfigure(1, weight=1)

        # --- Main Tabs (Notebook) ---
        # *** PACK Notebook ทีหลัง Login Frame ***
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(padx=10, pady=10, fill="both", expand=True)

        self.manual_tab = ttk.Frame(self.notebook)
        self.schedule_tab = ttk.Frame(self.notebook)
        self.config_tab = ttk.Frame(self.notebook) 
        
        self.notebook.add(self.manual_tab, text="จองด้วยตัวเอง")
        self.notebook.add(self.schedule_tab, text="ตั้งเวลาจอง")
        self.notebook.add(self.config_tab, text="จัดการ Config") 


        self.manual_widgets = {}
        manual_frame = ttk.Frame(self.manual_tab, padding=10)
        manual_frame.pack(fill="both", expand=True)

        # --- Booking Mode Selection ---
        self.manual_widgets['booking_mode_frame'] = ttk.LabelFrame(manual_frame, text="เลือกโหมดการจอง", padding=10)
        self.manual_widgets['booking_mode_var'] = tk.StringVar(self.root)
        self.manual_widgets['booking_mode_combobox'] = ttk.Combobox(self.manual_widgets['booking_mode_frame'],
                                                                    textvariable=self.manual_widgets['booking_mode_var'],
                                                                    values=["Live Mode", "Trial Mode"], state="readonly")
        self.manual_widgets['booking_mode_combobox'].pack(fill="x", padx=5, pady=5)
        self.manual_widgets['booking_mode_var'].set("Live Mode") # Default mode
        self.manual_widgets['booking_mode_var'].trace_add('write', self._on_booking_mode_change) # Trace changes

        self.manual_widgets['user_profile_frame'] = ttk.LabelFrame(manual_frame, text="เลือกโปรไฟล์ผู้ใช้", padding=10)
        self.manual_widgets['user_profile_var'] = tk.StringVar(self.root)
        self.manual_widgets['user_profile_combobox'] = ttk.Combobox(self.manual_widgets['user_profile_frame'], 
                                                                    textvariable=self.manual_widgets['user_profile_var'], 
                                                                    values=[], state="readonly")
        self.manual_widgets['user_profile_combobox'].pack(fill="x", padx=5, pady=5)

        self.manual_widgets['branch_frame'] = ttk.LabelFrame(manual_frame, text="เลือกสาขา", padding=10)
        self.manual_widgets['branch_var'] = tk.StringVar(self.root)
        self.manual_widgets['branch_combobox'] = ttk.Combobox(self.manual_widgets['branch_frame'], 
                                                                textvariable=self.manual_widgets['branch_var'], 
                                                                values=self.branches, state="readonly")
        self.manual_widgets['branch_combobox'].pack(fill="x", padx=5, pady=5)

        self.manual_widgets['day_frame'] = ttk.LabelFrame(manual_frame, text="เลือกวัน (1-31)", padding=10)
        self.manual_widgets['day_var'] = tk.StringVar(self.root)
        self.manual_widgets['day_spinbox'] = ttk.Spinbox(self.manual_widgets['day_frame'], from_=1, to_=31, 
                                                        textvariable=self.manual_widgets['day_var'], width=5)
        self.manual_widgets['day_spinbox'].pack(fill="x", padx=5, pady=5)
        self.manual_widgets['day_var'].set(str(datetime.date.today().day))

        self.manual_widgets['time_frame'] = ttk.LabelFrame(manual_frame, text="เลือกเวลา", padding=10)
        self.manual_widgets['time_var'] = tk.StringVar(self.root)
        self.manual_widgets['time_combobox'] = ttk.Combobox(self.manual_widgets['time_frame'], 
                                                            textvariable=self.manual_widgets['time_var'], 
                                                            values=self.times, state="readonly")
        self.manual_widgets['time_combobox'].pack(fill="x", padx=5, pady=5)
        self.manual_widgets['time_var'].set(self.times[0] if self.times else "")

        # --- Trial Mode Specific Widgets ---
        self.manual_widgets['trial_mode_options_frame'] = ttk.LabelFrame(manual_frame, text="ตัวเลือกโหมดทดสอบ", padding=10)
        
        # Get trial site options from imported TRIAL_SITES
        trial_site_options = [url for key, (url, _) in TRIAL_SITES.items()]
        self.manual_widgets['trial_site_var'] = tk.StringVar(self.root)
        self.manual_widgets['trial_site_combobox'] = ttk.Combobox(self.manual_widgets['trial_mode_options_frame'],
                                                                    textvariable=self.manual_widgets['trial_site_var'],
                                                                    values=trial_site_options, state="readonly")
        self.manual_widgets['trial_site_combobox'].pack(fill="x", padx=5, pady=5)
        if trial_site_options: self.manual_widgets['trial_site_var'].set(trial_site_options[0])

        # Get trial browser options from imported BROWSERS
        trial_browser_options = list(BROWSERS.values()) # 'chrome', 'edge'
        self.manual_widgets['trial_browser_var'] = tk.StringVar(self.root)
        self.manual_widgets['trial_browser_combobox'] = ttk.Combobox(self.manual_widgets['trial_mode_options_frame'],
                                                                    textvariable=self.manual_widgets['trial_browser_var'],
                                                                    values=trial_browser_options, state="readonly")
        self.manual_widgets['trial_browser_combobox'].pack(fill="x", padx=5, pady=5)
        if trial_browser_options: self.manual_widgets['trial_browser_var'].set(trial_browser_options[0])


        self.manual_widgets['start_button'] = ttk.Button(manual_frame, text="🚀 เริ่มการจอง", command=self._start_manual_booking_thread, state="disabled")
        self.manual_widgets['start_button'].pack(pady=10)


        schedule_frame = ttk.Frame(self.schedule_tab, padding=10)
        schedule_frame.pack(fill="both", expand=True)

        schedule_control_frame = ttk.LabelFrame(schedule_frame, text="ควบคุมการตั้งเวลา", padding=10)
        schedule_control_frame.pack(padx=5, pady=5, fill="x")
        self.start_scheduler_button = ttk.Button(schedule_control_frame, text="▶️ เริ่ม Scheduler", command=self._start_scheduler)
        self.start_scheduler_button.pack(side="left", padx=5, pady=5)
        self.stop_scheduler_button = ttk.Button(schedule_control_frame, text="⏹️ หยุด Scheduler", command=self._stop_scheduler, state="disabled")
        self.stop_scheduler_button.pack(side="left", padx=5, pady=5)

        self.schedule_list_frame = ttk.LabelFrame(schedule_frame, text="รายการจองที่ตั้งเวลาไว้", padding=10)
        self.schedule_list_frame.pack(padx=5, pady=5, fill="both", expand=True)
        self.schedule_tree = ttk.Treeview(self.schedule_list_frame, columns=("Name", "Profile", "Time", "Enabled"), show="headings")
        self.schedule_tree.heading("Name", text="ชื่อ")
        self.schedule_tree.heading("Profile", text="โปรไฟล์")
        self.schedule_tree.heading("Time", text="เวลาจอง")
        self.schedule_tree.column("Name", width=150, anchor="w")
        self.schedule_tree.column("Profile", width=150, anchor="w")
        self.schedule_tree.column("Time", width=120, anchor="center")
        self.schedule_tree.column("Enabled", width=80, anchor="center")
        self.schedule_tree.pack(fill="both", expand=True)

        self.schedule_tree.bind("<Double-1>", self._edit_scheduled_job)

        schedule_buttons_frame = ttk.Frame(self.schedule_list_frame)
        schedule_buttons_frame.pack(pady=5, fill="x")
        ttk.Button(schedule_buttons_frame, text="➕ เพิ่มใหม่", command=self._add_scheduled_job).pack(side="left", padx=2)
        ttk.Button(schedule_buttons_frame, text="✏️ แก้ไข", command=self._edit_selected_job).pack(side="left", padx=2)
        ttk.Button(schedule_buttons_frame, text="🗑️ ลบ", command=self._delete_selected_job).pack(side="left", padx=2)
        ttk.Button(schedule_buttons_frame, text="🔄 รีเฟรช", command=self._update_scheduled_jobs_display).pack(side="right", padx=2)


        # --- Config Tab Content ---
        config_frame = ttk.Frame(self.config_tab, padding=10)
        config_frame.pack(fill="both", expand=True)

        # User Profiles Section
        user_profiles_config_frame = ttk.LabelFrame(config_frame, text="จัดการโปรไฟล์เบราว์เซอร์ (user_config.json)", padding=10)
        user_profiles_config_frame.pack(padx=5, pady=5, fill="x", expand=True)

        self.user_profiles_tree = ttk.Treeview(user_profiles_config_frame, columns=("Username", "Browser", "Profile Name"), show="headings")
        self.user_profiles_tree.heading("Username", text="Username")
        self.user_profiles_tree.heading("Browser", text="Browser")
        self.user_profiles_tree.heading("Profile Name", text="Profile Name")
        self.user_profiles_tree.column("Username", width=100, anchor="w")
        self.user_profiles_tree.column("Browser", width=80, anchor="w")
        self.user_profiles_tree.column("Profile Name", width=120, anchor="w")
        self.user_profiles_tree.pack(fill="both", expand=True)
        self.user_profiles_tree.bind("<Double-1>", self._edit_user_profile_gui) # Bind double-click

        user_profiles_buttons_frame = ttk.Frame(user_profiles_config_frame)
        user_profiles_buttons_frame.pack(pady=5, fill="x")
        ttk.Button(user_profiles_buttons_frame, text="➕ เพิ่มโปรไฟล์", command=self._add_user_profile_gui).pack(side="left", padx=2)
        ttk.Button(user_profiles_buttons_frame, text="✏️ แก้ไขโปรไฟล์", command=self._edit_selected_user_profile_gui).pack(side="left", padx=2)
        ttk.Button(user_profiles_buttons_frame, text="🗑️ ลบโปรไฟล์", command=self._delete_selected_user_profile_gui).pack(side="left", padx=2)

        # LINE Accounts Section
        line_accounts_config_frame = ttk.LabelFrame(config_frame, text="จัดการบัญชี LINE (config_line_user.json)", padding=10)
        line_accounts_config_frame.pack(padx=5, pady=5, fill="x", expand=True)

        self.line_accounts_tree = ttk.Treeview(line_accounts_config_frame, columns=("Username", "Profile Name", "Email"), show="headings")
        self.line_accounts_tree.heading("Username", text="Username")
        self.line_accounts_tree.heading("Profile Name", text="Profile Name")
        self.line_accounts_tree.heading("Email", text="Email")
        self.line_accounts_tree.column("Username", width=100, anchor="w")
        self.line_accounts_tree.column("Profile Name", width=100, anchor="w")
        self.line_accounts_tree.column("Email", width=150, anchor="w")
        self.line_accounts_tree.pack(fill="both", expand=True)
        self.line_accounts_tree.bind("<Double-1>", self._edit_line_account_gui) # Bind double-click

        line_accounts_buttons_frame = ttk.Frame(line_accounts_config_frame)
        line_accounts_buttons_frame.pack(pady=5, fill="x")
        ttk.Button(line_accounts_buttons_frame, text="➕ เพิ่มบัญชี LINE", command=self._add_line_account_gui).pack(side="left", padx=2)
        ttk.Button(line_accounts_buttons_frame, text="✏️ แก้ไขบัญชี LINE", command=self._edit_selected_line_account_gui).pack(side="left", padx=2)
        ttk.Button(line_accounts_buttons_frame, text="🗑️ ลบบัญชี LINE", command=self._delete_selected_line_account_gui).pack(side="left", padx=2)


        # Log Text area (Shared across tabs)
        self.log_text = tk.Text(self.root, height=10, state='disabled', wrap='word')
        self.log_text.pack(padx=10, pady=5, fill="both", expand=True)

        self._set_ui_state_after_login()
        self._on_booking_mode_change() # Call once to set initial state of trial widgets
    
    def _on_booking_mode_change(self, *args):
        """Handle change in booking mode selection."""
        selected_mode = self.manual_widgets['booking_mode_var'].get()
        if selected_mode == "Trial Mode":
            self.manual_widgets['trial_mode_options_frame'].pack(padx=5, pady=5, fill="x")
            # Hide user profile selection for Trial Mode as it's not directly used by start_trial_mode
            self.manual_widgets['user_profile_frame'].pack_forget() 
            self.manual_widgets['day_frame'].pack_forget() # Hide Day selection for Trial (uses current day)
            self.manual_widgets['time_frame'].pack_forget() # Hide Time selection for Trial (uses current time)
        else: # Live Mode
            self.manual_widgets['trial_mode_options_frame'].pack_forget()
            self.manual_widgets['user_profile_frame'].pack(padx=5, pady=5, fill="x")
            self.manual_widgets['day_frame'].pack(padx=5, pady=5, fill="x")
            self.manual_widgets['time_frame'].pack(padx=5, pady=5, fill="x")


    def _set_manual_booking_controls_state(self, state):
        """Controls visibility and state of manual booking widgets."""
        # Always pack booking mode selector
        self.manual_widgets['booking_mode_frame'].pack(padx=5, pady=5, fill="x") 

        # Control other frames based on selected mode
        selected_mode = self.manual_widgets['booking_mode_var'].get()

        if selected_mode == "Trial Mode":
            # Only Trial specific frames and shared ones visible
            self.manual_widgets['user_profile_frame'].pack_forget()
            self.manual_widgets['branch_frame'].pack(padx=5, pady=5, fill="x")
            self.manual_widgets['day_frame'].pack_forget() # Trial uses current day
            self.manual_widgets['time_frame'].pack_forget() # Trial uses current time
            self.manual_widgets['trial_mode_options_frame'].pack(padx=5, pady=5, fill="x")
        else: # Live Mode
            # All frames for Live mode visible
            self.manual_widgets['user_profile_frame'].pack(padx=5, pady=5, fill="x")
            self.manual_widgets['branch_frame'].pack(padx=5, pady=5, fill="x")
            self.manual_widgets['day_frame'].pack(padx=5, pady=5, fill="x")
            self.manual_widgets['time_frame'].pack(padx=5, pady=5, fill="x")
            self.manual_widgets['trial_mode_options_frame'].pack_forget()

        # Set state for start button based on overall state
        if 'start_button' in self.manual_widgets:
            self.manual_widgets['start_button'].config(state=state)


    def _set_ui_state_after_login(self):
        """Controls visibility and state of UI elements based on login status and role."""
        if self.logged_in_username:
            self._set_manual_booking_controls_state("normal")
            
            user_profiles_for_logged_in_user = [u for u in self.users_data if u['username'] == self.logged_in_username]
            allowed_profile_names = [f"{u['username']} - {u['browser']} - {u['profile_name']}" for u in user_profiles_for_logged_in_user][:self.max_allowed_profiles]
            
            self.manual_widgets['user_profile_combobox'].config(values=allowed_profile_names)
            if allowed_profile_names:
                self.manual_widgets['user_profile_combobox'].set(allowed_profile_names[0])
            else:
                self.manual_widgets['user_profile_combobox'].set("")
                messagebox.showwarning("Warning", "ไม่พบโปรไฟล์ที่ใช้งานได้สำหรับผู้ใช้นี้.")
                self._set_manual_booking_controls_state("disabled")

            self.login_status_label.config(text=f"สถานะ: ล็อกอินแล้ว ({self.user_role})")
            self.login_main_button.config(text="Logout", command=self._logout)
            self.login_username_entry.config(state="disabled")
            self.login_password_entry.config(state="disabled")

            if not self.can_use_scheduler:
                self.notebook.tab(self.schedule_tab, state="disabled")
                self.log_message("⚠️ คุณไม่มีสิทธิ์ใช้งานระบบตั้งเวลาจอง.")
            else:
                self.notebook.tab(self.schedule_tab, state="normal")
            
            # อัปเดต Treeview ของ Scheduler และ Config Tab
            self._update_scheduled_jobs_display()
            self._update_user_profiles_display() # อัปเดต Treeview ของ User Profiles
            self._update_line_accounts_display() # อัปเดต Treeview ของ LINE Accounts
            
            if self.user_role == 'admin':
                self.notebook.tab(self.config_tab, state="normal")
            else:
                self.notebook.tab(self.config_tab, state="disabled")
                self.log_message("⚠️ คุณไม่มีสิทธิ์ใช้งานแท็บ 'จัดการ Config'.")

            # Ensure correct visibility of booking mode specific controls after login
            self._on_booking_mode_change() # Re-evaluate packing based on selected mode
        else: # Not logged in
            self._set_manual_booking_controls_state("disabled")
            self.notebook.tab(self.schedule_tab, state="disabled")
            self.notebook.tab(self.config_tab, state="disabled") # ปิด Config Tab เมื่อไม่ได้ Login
            self.login_status_label.config(text="สถานะ: ยังไม่ได้ล็อกอิน")
            self.login_main_button.config(text="Login", command=self._attempt_login)
            self.login_username_entry.config(state="normal")
            self.login_password_entry.config(state="normal")
            self.login_username_entry.delete(0, tk.END)
            self.login_password_entry.delete(0, tk.END)
            self._update_scheduled_jobs_display()
            self._update_user_profiles_display() # ยังแสดงได้ แต่อาจจะแก้ไขไม่ได้
            self._update_line_accounts_display() # ยังแสดงได้ แต่อาจจะแก้ไขไม่ได้


    def _populate_initial_data(self):
        if self.branches:
            self.manual_widgets['branch_combobox'].set(self.branches[0])
        if self.times:
            self.manual_widgets['time_combobox'].set(self.times[0])

    def _authenticate_user_from_gsheet(self, username, password):
        # Data is already loaded in self.gsheet_users_data from main.py's load
        for user_cred in self.gsheet_users_data:
            if user_cred.get("username") == username and user_cred.get("password") == password:
                return user_cred
        return None

    def _attempt_login(self):
        username = self.login_username_entry.get().strip()
        password = self.login_password_entry.get()

        if not username or not password:
            messagebox.showwarning("Warning", "กรุณาใส่ Username และ Password.")
            return

        user_auth_data = self._authenticate_user_from_gsheet(username, password)

        if user_auth_data:
            self.logged_in_username = user_auth_data['username']
            self.user_role = user_auth_data['role']
            self.max_allowed_profiles = user_auth_data['max_profiles']
            self.can_use_scheduler = user_auth_data['can_use_scheduler']
            
            self.log_message(f"✅ Login สำเร็จ: Welcome, {username}! (Role: {self.user_role}, Profiles: {self.max_allowed_profiles}, Scheduler: {self.can_use_scheduler})")
            self._set_ui_state_after_login()

        else:
            messagebox.showerror("Error", "Username หรือ Password ไม่ถูกต้อง.")
            self.log_message("❌ Login ไม่สำเร็จ: Username หรือ Password ไม่ถูกต้อง.")
            self.logged_in_username = None
            self.user_role = None
            self.max_allowed_profiles = 0
            self.can_use_scheduler = False
            self._set_ui_state_after_login()

    def _logout(self):
        self.logged_in_username = None
        self.user_role = None
        self.max_allowed_profiles = 0
        self.can_use_scheduler = False
        self._stop_scheduler()
        self.log_message("ℹ️ Logout สำเร็จ.")
        self._set_ui_state_after_login()


    def _start_manual_booking_thread(self):
        selected_mode = self.manual_widgets['booking_mode_var'].get()
        selected_branch = self.manual_widgets['branch_var'].get()
        selected_day_str = self.manual_widgets['day_var'].get()
        selected_time_str = self.manual_widgets['time_var'].get()

        if not selected_branch or not selected_day_str or not selected_time_str:
            messagebox.showwarning("Warning", "กรุณาเลือก สาขา, วัน, และเวลา ให้ครบถ้วนก่อนเริ่มการจอง.")
            return

        # Common checks
        if not self.logged_in_username:
            messagebox.showwarning("Warning", "กรุณาล็อกอินก่อนเริ่มการจอง.")
            return

        self.manual_widgets['start_button'].config(state="disabled")
        self.log_message(f"เริ่มต้นกระบวนการจอง ({selected_mode})...")

        if selected_mode == "Live Mode":
            selected_profile_str = self.manual_widgets['user_profile_var'].get()
            if not selected_profile_str:
                messagebox.showwarning("Warning", "กรุณาเลือกโปรไฟล์ก่อนเริ่มการจอง.")
                self.root.after(100, lambda: self.manual_widgets['start_button'].config(state="normal"))
                return

            parts = selected_profile_str.split(' - ')
            selected_username_in_profile = parts[0]
            selected_browser_in_profile = parts[1]
            selected_profile_name_in_profile = parts[2]

            all_user_profiles_full_objects = [u for u in self.users_data if u['username'] == selected_username_in_profile]
            
            actual_profile_idx_for_check = -1
            for i, p_obj in enumerate(all_user_profiles_full_objects):
                if p_obj['browser'] == selected_browser_in_profile and p_obj['profile_name'] == selected_profile_name_in_profile:
                    actual_profile_idx_for_check = i
                    break
            
            if self.logged_in_username != selected_username_in_profile and self.user_role != 'admin':
                messagebox.showerror("Error", "คุณสามารถจองได้เฉพาะโปรไฟล์ของบัญชีที่คุณล็อกอินอยู่เท่านั้น.")
                self.root.after(100, lambda: self.manual_widgets['start_button'].config(state="normal"))
                return

            if self.user_role != 'admin' and actual_profile_idx_for_check >= self.max_allowed_profiles:
                messagebox.showerror("Error", f"โปรไฟล์ที่เลือกเกินจำนวนที่อนุญาต ({self.max_allowed_profiles} โปรไฟล์สำหรับ Role '{self.user_role}').")
                self.root.after(100, lambda: self.manual_widgets['start_button'].config(state="normal"))
                return

            booking_thread = threading.Thread(target=self._run_booking_process_live, args=(
                selected_profile_str,
                selected_branch,
                selected_day_str,
                selected_time_str
            ))
            booking_thread.start()

        elif selected_mode == "Trial Mode":
            selected_trial_site_url = self.manual_widgets['trial_site_var'].get()
            selected_trial_browser = self.manual_widgets['trial_browser_var'].get()

            if not selected_trial_site_url or not selected_trial_browser:
                messagebox.showwarning("Warning", "กรุณาเลือกเว็บไซต์ทดสอบและเบราว์เซอร์ทดสอบให้ครบถ้วน.")
                self.root.after(100, lambda: self.manual_widgets['start_button'].config(state="normal"))
                return

            # Map URL to site_choice key (e.g., '1' or '2')
            trial_site_key = None
            for key, (url, _) in TRIAL_SITES.items():
                if url == selected_trial_site_url:
                    trial_site_key = key
                    break
            
            if trial_site_key is None:
                messagebox.showerror("Error", "ไม่พบเว็บไซต์ทดสอบที่เลือก.")
                self.root.after(100, lambda: self.manual_widgets['start_button'].config(state="normal"))
                return

            # Map browser name to browser_choice key (e.g., '1' or '2')
            trial_browser_key = None
            for key, name in BROWSERS.items():
                if name == selected_trial_browser:
                    trial_browser_key = key
                    break

            if trial_browser_key is None:
                messagebox.showerror("Error", "ไม่พบเบราว์เซอร์ทดสอบที่เลือก.")
                self.root.after(100, lambda: self.manual_widgets['start_button'].config(state="normal"))
                return
            
            # For trial mode, we can use the logged-in username or a dummy
            # For simplicity, we'll pass the logged-in username
            trial_username = self.logged_in_username 
            
            booking_thread = threading.Thread(target=self._run_booking_process_trial, args=(
                trial_username,
                trial_site_key,
                trial_browser_key,
                selected_branch,
                int(selected_day_str), # day
                selected_time_str # time_str
            ))
            booking_thread.start()


    def _run_booking_process_live(self, selected_profile_str, selected_branch, selected_day_str, selected_time_str):
        try:
            parts = selected_profile_str.split(' - ')
            username = parts[0]
            browser = parts[1]
            profile_name = parts[2]

            day = int(selected_day_str)
            
            time_index = self.times.index(selected_time_str) if selected_time_str in self.times else 0

            line_email, line_password = self._load_line_credentials_for_ui(username, profile_name)

            self.log_message(f"Selected: User='{username}', Browser='{browser}', Profile='{profile_name}', Branch='{selected_branch}', Day={day}, Time='{selected_time_str}'")
            
            run_live_mode_for_user(username, browser, profile_name, selected_branch, day, time_index, line_email, line_password)
            
            self.log_message(f"✅ กระบวนการจอง '{selected_profile_str}' (Branch: {selected_branch}, Day: {day}, Time: {selected_time_str}) เสร็จสิ้น.")

        except ValueError:
            self.log_message("❌ กรุณาตรวจสอบการเลือกวัน (ต้องเป็นตัวเลข).")
        except Exception as e:
            self.log_message(f"❌ เกิดข้อผิดพลาดในกระบวนการจอง: {e}")
        finally:
            self.root.after(100, lambda: self.manual_widgets['start_button'].config(state="normal"))

    def _run_booking_process_trial(self, username, site_key, browser_key, branch, day, time_str):
        try:
            self.log_message(f"Selected Trial: User='{username}', Site='{TRIAL_SITES[site_key][0]}', Browser='{BROWSERS[browser_key]}', Branch='{branch}', Day={day}, Time='{time_str}'")
            
            start_trial_mode(username, site_key, browser_key, branch, day, time_str)
            
            self.log_message(f"✅ กระบวนการทดสอบ '{username}' (Site: {TRIAL_SITES[site_key][0]}, Browser: {BROWSERS[browser_key]}) เสร็จสิ้น.")

        except Exception as e:
            self.log_message(f"❌ เกิดข้อผิดพลาดในกระบวนการทดสอบ: {e}")
        finally:
            self.root.after(100, lambda: self.manual_widgets['start_button'].config(state="normal"))


    def _load_line_credentials_for_ui(self, username, profile_name):
        try:
            with open(LINE_USER_CONFIG_PATH, "r", encoding="utf-8") as f:
                line_config = json.load(f)
            
            for account in line_config.get("line_accounts", []):
                if account["username"] == username and account["profile_name"] == profile_name:
                    self.log_message(f"✅ โหลดข้อมูล LINE Login สำหรับ '{username}' ({profile_name}) สำเร็จแล้ว (สำหรับ UI).")
                    return account.get("line_email"), account.get("line_password")
            self.log_message(f"⚠️ ไม่พบข้อมูล LINE Login สำหรับ '{username}' ({profile_name}) ใน {LINE_USER_CONFIG_PATH}")
            return None, None
        except FileNotFoundError:
            self.log_message(f"❌ ไม่พบไฟล์ config LINE Login: {LINE_USER_CONFIG_PATH}")
            return None, None
        except json.JSONDecodeError:
            self.log_message(f"❌ รูปแบบไฟล์ JSON ใน {LINE_USER_CONFIG_PATH} ไม่ถูกต้อง")
            return None, None

    def log_message(self, message):
        if self.root.winfo_exists():
            self.root.after(0, self._insert_log_message, message)

    def _insert_log_message(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    # --- Scheduler Functions ---
    def _update_scheduled_jobs_display(self):
        """Clears and repopulates the Treeview with current scheduled jobs."""
        for i in self.schedule_tree.get_children():
            self.schedule_tree.delete(i)
        
        self.scheduled_bookings = self._load_json_config_for_gui(SCHEDULE_CONFIG_PATH).get("scheduled_bookings", [])

        for idx, job_data in enumerate(self.scheduled_bookings):
            job_username = job_data.get('username')
            job_profile_name = job_data.get('profile_name')
            job_browser = job_data.get('browser')

            is_profile_available = any(u['username'] == job_username and 
                                       u['profile_name'] == job_profile_name and
                                       u['browser'] == job_browser for u in self.users_data)
            
            is_for_current_user = (self.logged_in_username is None) or \
                                  (job_username == self.logged_in_username)

            is_within_profile_limit = True
            if self.logged_in_username == job_username and self.max_allowed_profiles < 999:
                all_user_profiles_for_logged_in_user = [f"{u['username']} - {u['browser']} - {u['profile_name']}" 
                                                        for u in self.users_data if u['username'] == self.logged_in_username]
                
                job_profile_str = f"{job_username} - {job_browser} - {job_profile_name}"
                
                try:
                    job_profile_idx_in_user_profiles = all_user_profiles_for_logged_in_user.index(job_profile_str)
                    if job_profile_idx_in_user_profiles >= self.max_allowed_profiles:
                        is_within_profile_limit = False
                except ValueError:
                    is_within_profile_limit = False
            
            profile_str = f"{job_data['username']} - {job_data['browser']} - {job_data['profile_name']}"
            job_time_str = job_data['schedule_time']
            enabled_status = "✅ เปิด" if job_data['enabled'] else "❌ ปิด"
            
            tags = []
            if not job_data['enabled']:
                tags.append("disabled")
            if not is_profile_available:
                profile_str += " (โปรไฟล์ไม่มีอยู่)"
                tags.append("invalid_profile")
            if not is_for_current_user:
                profile_str += " (ไม่ใช่ผู้ใช้ปัจจุบัน)"
                tags.append("not_current_user")
            if not is_within_profile_limit:
                profile_str += " (เกินขีดจำกัดโปรไฟล์)"
                tags.append("profile_limit_exceeded")
            
            self.schedule_tree.insert("", "end", iid=str(idx), 
                                      values=(job_data['name'], profile_str, job_time_str, enabled_status),
                                      tags=tuple(tags))
        
        self.schedule_tree.tag_configure("disabled", foreground="gray")
        self.schedule_tree.tag_configure("invalid_profile", foreground="red")
        self.schedule_tree.tag_configure("not_current_user", foreground="orange")
        self.schedule_tree.tag_configure("profile_limit_exceeded", foreground="purple")


    def _add_scheduled_job(self):
        if not self.logged_in_username:
            messagebox.showwarning("Warning", "กรุณาล็อกอินก่อนเพิ่มรายการจอง.")
            return
        if not self.can_use_scheduler:
            messagebox.showerror("Error", "บัญชีของคุณไม่มีสิทธิ์ใช้งานระบบตั้งเวลาจอง.")
            return

        self._open_job_editor_window()

    def _edit_selected_job(self):
        if not self.logged_in_username:
            messagebox.showwarning("Warning", "กรุณาล็อกอินก่อนแก้ไขรายการจอง.")
            return
        if not self.can_use_scheduler:
            messagebox.showerror("Error", "บัญชีของคุณไม่มีสิทธิ์ใช้งานระบบตั้งเวลาจอง.")
            return

        selected_item = self.schedule_tree.focus()
        if not selected_item:
            messagebox.showwarning("Warning", "กรุณาเลือกรายการที่ต้องการแก้ไข.")
            return
        
        job_index = int(selected_item)
        job_data = self.scheduled_bookings[job_index]
        
        if job_data.get('username') != self.logged_in_username and self.user_role != 'admin':
            messagebox.showerror("Error", "คุณไม่มีสิทธิ์แก้ไขรายการจองนี้.")
            return

        self._open_job_editor_window(job_data, job_index)

    def _edit_scheduled_job(self, event):
        self._edit_selected_job()


    def _delete_selected_job(self):
        if not self.logged_in_username:
            messagebox.showwarning("Warning", "กรุณาล็อกอินก่อนลบรายการจอง.")
            return
        if not self.can_use_scheduler:
            messagebox.showerror("Error", "บัญชีของคุณไม่มีสิทธิ์ใช้งานระบบตั้งเวลาจอง.")
            return

        selected_item = self.schedule_tree.focus()
        if not selected_item:
            messagebox.showwarning("Warning", "กรุณาเลือกรายการที่ต้องการลบ.")
            return
        
        job_index = int(selected_item)
        job_name = self.scheduled_bookings[job_index]['name']

        if self.scheduled_bookings[job_index].get('username') != self.logged_in_username and self.user_role != 'admin':
            messagebox.showerror("Error", "คุณไม่มีสิทธิ์ลบรายการจองนี้.")
            return

        if messagebox.askyesno("ยืนยันการลบ", f"คุณแน่ใจหรือไม่ที่ต้องการลบ '{job_name}' ออกจาก Schedule?"):
            del self.scheduled_bookings[job_index]
            self._save_json_config_for_gui(SCHEDULE_CONFIG_PATH, {"scheduled_bookings": self.scheduled_bookings})
            self._update_scheduled_jobs_display()
            self.log_message(f"🗑️ ลบรายการจอง '{job_name}' ออกจาก Schedule แล้ว.")

    def _open_job_editor_window(self, job_data=None, job_index=None):
        editor_win = tk.Toplevel(self.root)
        editor_win.title("เพิ่ม/แก้ไขรายการจองที่ตั้งเวลา")
        editor_win.geometry("450x550")
        editor_win.transient(self.root)
        editor_win.grab_set()
        
        job_name_var = tk.StringVar(editor_win)
        profile_var = tk.StringVar(editor_win)
        branch_var = tk.StringVar(editor_win)
        day_var = tk.StringVar(editor_win)
        time_var = tk.StringVar(editor_win)
        schedule_time_var = tk.StringVar(editor_win)
        enabled_var = tk.BooleanVar(editor_win)

        form_frame = ttk.Frame(editor_win, padding=10)
        form_frame.pack(fill="both", expand=True)

        current_user_profiles_full = [u for u in self.users_data if u['username'] == self.logged_in_username]
        current_user_profile_names = [f"{u['username']} - {u['browser']} - {u['profile_name']}" 
                                      for u in current_user_profiles_full]
        
        allowed_profile_names_for_combobox = current_user_profile_names[:self.max_allowed_profiles]
        
        if job_data:
            existing_job_profile_str = f"{job_data.get('username', '')} - {job_data.get('browser', '')} - {job_data.get('profile_name', '')}"
            if existing_job_profile_str not in allowed_profile_names_for_combobox:
                allowed_profile_names_for_combobox.append(existing_job_profile_str)
                allowed_profile_names_for_combobox = sorted(list(set(allowed_profile_names_for_combobox)))


        labels_data = [
            ("ชื่อ Event:", job_name_var, "entry"),
            ("โปรไฟล์:", profile_var, "combobox", allowed_profile_names_for_combobox),
            ("สาขา:", branch_var, "combobox", self.branches),
            ("วัน (1-31):", day_var, "spinbox"),
            ("เวลา (HH:MM):", time_var, "combobox", self.times),
            ("เวลาเริ่ม Schedule (YYYY-MM-DD HH:MM:SS):", schedule_time_var, "entry"),
            ("เปิดใช้งาน:", enabled_var, "checkbutton")
        ]

        row = 0
        for label_text, var, widget_type, *options in labels_data:
            ttk.Label(form_frame, text=label_text).grid(row=row, column=0, sticky="w", pady=2)
            if widget_type == "entry":
                ttk.Entry(form_frame, textvariable=var, width=40).grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            elif widget_type == "combobox":
                ttk.Combobox(form_frame, textvariable=var, values=options[0], state="readonly", width=37).grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            elif widget_type == "spinbox":
                ttk.Spinbox(form_frame, from_=1, to_=31, textvariable=var, width=5).grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            elif widget_type == "checkbutton":
                ttk.Checkbutton(form_frame, text="ใช่", variable=enabled_var).grid(row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

        if job_data:
            job_name_var.set(job_data.get('name', ''))
            profile_str_to_set = f"{job_data.get('username', '')} - {job_data.get('browser', '')} - {job_data.get('profile_name', '')}"
            profile_var.set(profile_str_to_set)
            branch_var.set(job_data.get('branch', ''))
            day_var.set(str(job_data.get('day', datetime.date.today().day)))
            time_var.set(job_data.get('time_str', ''))
            schedule_time_var.set(job_data.get('schedule_time', ''))
            enabled_var.set(job_data.get('enabled', False))
        else:
            job_name_var.set(f"งานใหม่_{datetime.datetime.now().strftime('%H%M%S')}")
            if allowed_profile_names_for_combobox: profile_var.set(allowed_profile_names_for_combobox[0])
            if self.branches: branch_var.set(self.branches[0])
            day_var.set(str(datetime.date.today().day))
            if self.times: time_var.set(self.times[0])
            schedule_time_var.set(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            enabled_var.set(True)

        button_frame = ttk.Frame(editor_win, padding=10)
        button_frame.pack(fill="x", pady=5)
        ttk.Button(button_frame, text="บันทึก", command=lambda: self._save_job_from_editor(editor_win, job_name_var.get(), profile_var.get(), branch_var.get(), day_var.get(), time_var.get(), schedule_time_var.get(), enabled_var.get(), job_index)).pack(side="left", padx=5)
        ttk.Button(button_frame, text="ยกเลิก", command=editor_win.destroy).pack(side="right", padx=5)

    def _save_job_from_editor(self, editor_win, name, profile_str, branch, day_str, time_str, schedule_time_str, enabled, job_index):
        try:
            if not all([name, profile_str, branch, day_str, time_str, schedule_time_str]):
                messagebox.showwarning("ข้อมูลไม่ครบ", "กรุณากรอกข้อมูลให้ครบทุกช่อง.")
                return

            day = int(day_str)
            if not (1 <= day <= 31): raise ValueError("วันต้องอยู่ระหว่าง 1-31")

            try:
                datetime.datetime.strptime(schedule_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                raise ValueError("รูปแบบเวลาเริ่ม Schedule ไม่ถูกต้อง. ตัวอย่าง: YYYY-MM-DD HH:MM:SS")

            parts = profile_str.split(' - ')
            if len(parts) != 3: raise ValueError("รูปแบบโปรไฟล์ไม่ถูกต้อง: Username - Browser - ProfileName")
            username, browser, profile_name = parts[0], parts[1], parts[2]

            logged_in_user_details = next((u for u in self.gsheet_users_data if u.get('username') == self.logged_in_username), None)
            
            current_user_max_profiles = logged_in_user_details.get('max_profiles', 1) if logged_in_user_details else 1
            current_user_role = logged_in_user_details.get('role', 'normal') if logged_in_user_details else 'normal'
            
            user_profiles_for_current_user = [u for u in self.users_data if u['username'] == self.logged_in_username]
            user_profile_strings_for_current_user = [f"{u['username']} - {u['browser']} - {u['profile_name']}" for u in user_profiles_for_current_user]

            try:
                selected_profile_index_in_user_profiles = user_profile_strings_for_current_user.index(profile_str)
            except ValueError:
                if username != self.logged_in_username and current_user_role != 'admin':
                    messagebox.showerror("ข้อผิดพลาด", "คุณสามารถเลือกได้เฉพาะโปรไฟล์ของบัญชีที่คุณล็อกอินอยู่เท่านั้น.")
                    return
                # ถ้าเป็น admin หรือโปรไฟล์ที่เลือกไม่ใช่ของ user ปัจจุบัน แต่ก็ไม่ใช่ admin ที่จัดการได้
                # เราต้องตรวจสอบว่าโปรไฟล์นี้มีอยู่จริงใน self.users_data หรือไม่
                if not any(u['username'] == username and u['browser'] == browser and u['profile_name'] == profile_name for u in self.users_data):
                    messagebox.showerror("ข้อผิดพลาด", f"โปรไฟล์ '{profile_str}' ไม่มีอยู่จริงใน user_config.json")
                    return

            if current_user_role != 'admin' and selected_profile_index_in_user_profiles >= current_user_max_profiles:
                messagebox.showerror("ข้อผิดพลาด", f"โปรไฟล์ที่เลือกเกินจำนวนที่อนุญาต ({current_user_max_profiles} โปรไฟล์สำหรับ Role '{current_user_role}').")
                return


            new_job_data = {
                "name": name,
                "username": username,
                "browser": browser,
                "profile_name": profile_name,
                "branch": branch,
                "day": day,
                "time_str": time_str,
                "schedule_time": schedule_time_str,
                "enabled": enabled
            }

            if job_index is not None:
                self.scheduled_bookings[job_index] = new_job_data
                self.log_message(f"✅ แก้ไขรายการจอง '{name}' แล้ว.")
            else:
                self.scheduled_bookings.append(new_job_data)
                self.log_message(f"✅ เพิ่มรายการจอง '{name}' ใหม่แล้ว.")
            
            self._save_json_config_for_gui(SCHEDULE_CONFIG_PATH, {"scheduled_bookings": self.scheduled_bookings})
            self._update_scheduled_jobs_display()
            editor_win.destroy()

        except ValueError as e:
            messagebox.showerror("ข้อมูลไม่ถูกต้อง", f"ข้อผิดพลาด: {e}")
        except Exception as e:
            messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถบันทึกรายการจองได้: {e}")


    def _start_scheduler(self):
        if self.scheduler_running:
            self.log_message("Scheduler กำลังทำงานอยู่แล้ว.")
            return
        if not self.logged_in_username:
            messagebox.showwarning("Warning", "กรุณาล็อกอินก่อนเริ่ม Scheduler.")
            return
        if not self.can_use_scheduler:
            messagebox.showerror("Error", "บัญชีของคุณไม่มีสิทธิ์ใช้งานระบบตั้งเวลาจอง.")
            return

        self.scheduler_running = True
        self.start_scheduler_button.config(state="disabled")
        self.stop_scheduler_button.config(state="normal")
        self.log_message("▶️ เริ่ม Scheduler แล้ว. ตรวจสอบรายการจองที่เปิดใช้งาน...")

        self._clear_all_scheduled_jobs()
        for idx, job_data in enumerate(self.scheduled_bookings):
            if job_data['enabled'] and \
               ((self.logged_in_username == job_data['username']) or (self.user_role == 'admin')):
                job_time_str = job_data['schedule_time']
                job_name = job_data['name']
                
                try:
                    scheduled_dt = datetime.datetime.strptime(job_time_str, "%Y-%m-%d %H:%M:%S")
                    
                    def job_function_wrapper(data):
                        current_datetime = datetime.datetime.now()
                        target_datetime = datetime.datetime.strptime(data['schedule_time'], "%Y-%m-%d %H:%M:%S")
                        
                        if current_datetime.year == target_datetime.year and \
                           current_datetime.month == target_datetime.month and \
                           current_datetime.day == target_datetime.day and \
                           current_datetime.hour == target_datetime.hour and \
                           current_datetime.minute == target_datetime.minute:

                            logged_in_user_details = next((u for u in self.gsheet_users_data if u.get('username') == self.logged_in_username), None)
                            
                            current_user_max_profiles_at_run_time = logged_in_user_details.get('max_profiles', 1) if logged_in_user_details else 1
                            current_user_role_at_run_time = logged_in_user_details.get('role', 'normal') if logged_in_user_details else 'normal'

                            job_profile_str_for_check = f"{data['username']} - {data['browser']} - {data['profile_name']}"
                            all_user_profiles_for_check = [f"{u['username']} - {u['browser']} - {u['profile_name']}" 
                                                            for u in self.users_data if u['username'] == data['username']]
                            
                            profile_index_at_run_time = -1
                            try:
                                profile_index_at_run_time = all_user_profiles_for_check.index(job_profile_str_for_check)
                            except ValueError:
                                pass

                            if data['username'] == self.logged_in_username and \
                               (current_user_role_at_run_time == 'admin' or profile_index_at_run_time < current_user_max_profiles_at_run_time):
                                self.log_message(f"🚀 Scheduler: กำลังเริ่มจอง '{job_name}' ตามเวลาที่ตั้งไว้ ({target_datetime}).")
                                self._run_booking_process_scheduled(data)
                            else:
                                self.log_message(f"❌ Scheduler: งาน '{job_name}' ถูกเรียก แต่ถูกข้ามเนื่องจากสิทธิ์ผู้ใช้หรือเกินขีดจำกัดโปรไฟล์.")
                        else:
                            self.log_message(f"ℹ️ Scheduler: งาน '{job_name}' ถูกเรียก แต่ไม่ใช่เวลา/วันที่ตรงตามเป้าหมาย (เป้าหมาย: {target_datetime}, ปัจจุบัน: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}).")


                    job_instance = schedule.every().day.at(scheduled_dt.strftime("%H:%M")).do(
                        job_function_wrapper, job_data
                    ).tag(job_name) 
                    
                    self.job_refs[job_name] = job_instance
                    self.log_message(f"✅ ตั้งเวลาจอง '{job_name}' สำหรับทุกวันเวลา {scheduled_dt.strftime('%H:%M')} น. (จะตรวจสอบวันที่และเวลาที่แน่นอนใน Job).")
                    
                except ValueError:
                    self.log_message(f"❌ รายการจอง '{job_name}' มีรูปแบบเวลา Schedule ไม่ถูกต้อง: {job_time_str}. ข้ามรายการนี้.")
                except Exception as e:
                    self.log_message(f"❌ ไม่สามารถตั้งเวลาจอง '{job_name}' ได้: {e}")
        
        self.scheduler_thread = threading.Thread(target=self._run_scheduler_loop)
        self.scheduler_thread.daemon = True 
        self.scheduler_thread.start()

    def _run_scheduler_loop(self):
        while self.scheduler_running:
            schedule.run_pending()
            time_module.sleep(1)
        self.log_message("Scheduler หยุดทำงานแล้ว.")


    def _stop_scheduler(self):
        if self.scheduler_running:
            self.scheduler_running = False
            self.start_scheduler_button.config(state="normal")
            self.stop_scheduler_button.config(state="disabled")
            self._clear_all_scheduled_jobs() 
            self.log_message("⏹️ Scheduler ถูกหยุดและลบงานทั้งหมดแล้ว.")
        else:
            self.log_message("Scheduler ไม่ได้กำลังทำงาน.")


    def _clear_all_scheduled_jobs(self):
        schedule.clear()
        self.job_refs = {}
        self.log_message("Scheduler: ลบงานทั้งหมดในคิวแล้ว.")

    def _run_booking_process_scheduled(self, job_data):
        selected_profile_str = f"{job_data['username']} - {job_data['browser']} - {job_data['profile_name']}"
        selected_branch = job_data['branch']
        selected_day_str = str(job_data['day'])
        selected_time_str = job_data['time_str']

        booking_thread = threading.Thread(target=self._run_booking_process_live, args=( # ต้องใช้ _run_booking_process_live เสมอสำหรับ Scheduled Booking
            selected_profile_str, selected_branch, selected_day_str, selected_time_str
        ))
        booking_thread.start()
        self.log_message(f"✅ Scheduler: งานจอง '{job_data['name']}' ถูกส่งเข้าคิวแล้ว.")
        
    # --- ฟังก์ชันจัดการ User Profiles (ย้ายมาจากคำตอบก่อนหน้า) ---
    def _update_user_profiles_display(self):
        """Clears and repopulates the user profiles Treeview."""
        for i in self.user_profiles_tree.get_children():
            self.user_profiles_tree.delete(i)
        
        # โหลดข้อมูล users_data ล่าสุดจากไฟล์ user_config.json
        self.users_data = self._load_json_config_for_gui(USER_CONFIG_PATH).get("users", [])

        for idx, user_profile in enumerate(self.users_data):
            self.user_profiles_tree.insert("", "end", iid=str(idx),
                                         values=(user_profile.get('username', ''), 
                                                 user_profile.get('browser', ''), 
                                                 user_profile.get('profile_name', '')))

    def _add_user_profile_gui(self):
        # ตรวจสอบสิทธิ์การเพิ่มโปรไฟล์ (อาจจะจำกัดเฉพาะ Admin)
        if self.logged_in_username is None or self.user_role != 'admin':
            messagebox.showerror("ข้อผิดพลาด", "คุณไม่มีสิทธิ์เพิ่มโปรไฟล์เบราว์เซอร์.")
            return
        self._open_user_profile_editor_window()

    def _edit_selected_user_profile_gui(self):
        # ตรวจสอบสิทธิ์การแก้ไขโปรไฟล์ (อาจจะจำกัดเฉพาะ Admin)
        if self.logged_in_username is None or self.user_role != 'admin':
            messagebox.showerror("ข้อผิดพลาด", "คุณไม่มีสิทธิ์แก้ไขโปรไฟล์เบราว์เซอร์.")
            return

        selected_item = self.user_profiles_tree.focus()
        if not selected_item:
            messagebox.showwarning("Warning", "กรุณาเลือกโปรไฟล์ที่ต้องการแก้ไข.")
            return
        
        profile_index = int(selected_item)
        profile_data = self.users_data[profile_index]
        self._open_user_profile_editor_window(profile_data, profile_index)

    def _edit_user_profile_gui(self, event): # For double-click
        self._edit_selected_user_profile_gui()

    def _delete_selected_user_profile_gui(self):
        # ตรวจสอบสิทธิ์การลบโปรไฟล์ (อาจจะจำกัดเฉพาะ Admin)
        if self.logged_in_username is None or self.user_role != 'admin':
            messagebox.showerror("ข้อผิดพลาด", "คุณไม่มีสิทธิ์ลบโปรไฟล์เบราว์เซอร์.")
            return

        selected_item = self.user_profiles_tree.focus()
        if not selected_item:
            messagebox.showwarning("Warning", "กรุณาเลือกโปรไฟล์ที่ต้องการลบ.")
            return
        
        profile_index = int(selected_item)
        profile_name = self.users_data[profile_index].get('profile_name', 'Unknown')

        if messagebox.askyesno("ยืนยันการลบ", f"คุณแน่ใจหรือไม่ที่ต้องการลบโปรไฟล์ '{profile_name}'?"):
            del self.users_data[profile_index]
            self._save_json_config_for_gui(USER_CONFIG_PATH, {"users": self.users_data})
            self._update_user_profiles_display()
            self.log_message(f"🗑️ ลบโปรไฟล์ '{profile_name}' แล้ว.")
            self._set_ui_state_after_login() # รีเฟรช Combobox ใน Manual Tab ด้วย

    def _open_user_profile_editor_window(self, profile_data=None, profile_index=None):
        editor_win = tk.Toplevel(self.root)
        editor_win.title("เพิ่ม/แก้ไขโปรไฟล์เบราว์เซอร์")
        editor_win.geometry("400x300")
        editor_win.transient(self.root)
        editor_win.grab_set()

        username_var = tk.StringVar(editor_win)
        browser_var = tk.StringVar(editor_win)
        profile_name_var = tk.StringVar(editor_win)
        user_agent_var = tk.StringVar(editor_win) # Assuming user_agent is part of profile

        form_frame = ttk.Frame(editor_win, padding=10)
        form_frame.pack(fill="both", expand=True)

        labels_data = [
            ("Username:", username_var, "entry"),
            ("Browser:", browser_var, "combobox", ["chrome", "edge"]), # Options for browser
            ("Profile Name:", profile_name_var, "entry"),
            ("User Agent:", user_agent_var, "entry")
        ]

        row = 0
        for label_text, var, widget_type, *options in labels_data:
            ttk.Label(form_frame, text=label_text).grid(row=row, column=0, sticky="w", pady=2)
            if widget_type == "entry":
                ttk.Entry(form_frame, textvariable=var, width=30).grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            elif widget_type == "combobox":
                ttk.Combobox(form_frame, textvariable=var, values=options[0], state="readonly", width=27).grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            row += 1

        if profile_data:
            username_var.set(profile_data.get('username', ''))
            browser_var.set(profile_data.get('browser', ''))
            profile_name_var.set(profile_data.get('profile_name', ''))
            user_agent_var.set(profile_data.get('user_agent', ''))
        else:
            # Default values for new profile
            username_var.set(self.logged_in_username if self.logged_in_username else "")
            browser_var.set("chrome")
            profile_name_var.set("Default")

        button_frame = ttk.Frame(editor_win, padding=10)
        button_frame.pack(fill="x", pady=5)
        ttk.Button(button_frame, text="บันทึก", command=lambda: self._save_user_profile_from_editor(editor_win, username_var.get(), browser_var.get(), profile_name_var.get(), user_agent_var.get(), profile_index)).pack(side="left", padx=5)
        ttk.Button(button_frame, text="ยกเลิก", command=editor_win.destroy).pack(side="right", padx=5)

    def _save_user_profile_from_editor(self, editor_win, username, browser, profile_name, user_agent, profile_index):
        try:
            if not all([username, browser, profile_name]):
                messagebox.showwarning("ข้อมูลไม่ครบ", "กรุณากรอก Username, Browser, และ Profile Name.")
                return

            new_profile_data = {
                "username": username,
                "browser": browser,
                "profile_name": profile_name,
                "user_agent": user_agent # Include user_agent
            }

            # Check for duplicates (only if adding a new profile, or if username/profile_name changed during edit)
            is_duplicate = False
            for idx, existing_profile in enumerate(self.users_data):
                if (existing_profile['username'] == username and 
                    existing_profile['browser'] == browser and
                    existing_profile['profile_name'] == profile_name and 
                    idx != profile_index): # Exclude itself if editing
                    is_duplicate = True
                    break
            
            if is_duplicate:
                messagebox.showerror("ข้อผิดพลาด", "โปรไฟล์เบราว์เซอร์นี้มีอยู่แล้ว.")
                return

            if profile_index is not None:
                self.users_data[profile_index] = new_profile_data
                self.log_message(f"✅ แก้ไขโปรไฟล์ '{profile_name}' แล้ว.")
            else:
                self.users_data.append(new_profile_data)
                self.log_message(f"✅ เพิ่มโปรไฟล์ '{profile_name}' ใหม่แล้ว.")
            
            self._save_json_config_for_gui(USER_CONFIG_PATH, {"users": self.users_data})
            self._update_user_profiles_display()
            self._set_ui_state_after_login() # รีเฟรช Combobox ใน Manual Tab ด้วย
            editor_win.destroy()

        except Exception as e:
            messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถบันทึกโปรไฟล์ได้: {e}")

    # --- ฟังก์ชันจัดการ LINE Accounts (ย้ายมาจากคำตอบก่อนหน้า) ---
    def _update_line_accounts_display(self):
        """Clears and repopulates the LINE accounts Treeview."""
        for i in self.line_accounts_tree.get_children():
            self.line_accounts_tree.delete(i)
        
        # โหลดข้อมูล line_accounts ล่าสุดจากไฟล์ config_line_user.json
        self.line_accounts = self._load_json_config_for_gui(LINE_USER_CONFIG_PATH).get("line_accounts", [])

        for idx, line_account in enumerate(self.line_accounts):
            self.line_accounts_tree.insert("", "end", iid=str(idx),
                                         values=(line_account.get('username', ''), 
                                                 line_account.get('profile_name', ''), 
                                                 line_account.get('line_email', '')))

    def _add_line_account_gui(self):
        # ตรวจสอบสิทธิ์การเพิ่มบัญชี LINE (อาจจะจำกัดเฉพาะ Admin)
        if self.logged_in_username is None or self.user_role != 'admin':
            messagebox.showerror("ข้อผิดพลาด", "คุณไม่มีสิทธิ์เพิ่มบัญชี LINE.")
            return
        self._open_line_account_editor_window()

    def _edit_selected_line_account_gui(self):
        # ตรวจสอบสิทธิ์การแก้ไขบัญชี LINE (อาจจะจำกัดเฉพาะ Admin)
        if self.logged_in_username is None or self.user_role != 'admin':
            messagebox.showerror("ข้อผิดพลาด", "คุณไม่มีสิทธิ์แก้ไขบัญชี LINE.")
