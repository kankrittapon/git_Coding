import gspread
from google.oauth2.service_account import Credentials

SHEET_NAME = "Users"  # ชื่อชีตที่เก็บข้อมูล user
SPREADSHEET_ID = "1rQnV_-30tmb8oYj7g9q6-YdyuWZZ2c8sZ2xH7pqszVk"

def connect_gsheet():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID)
    return sheet

def load_users():
    sheet = connect_gsheet()
    user_sheet = sheet.worksheet(SHEET_NAME)
    users = user_sheet.col_values(1)[1:]  # ข้าม header
    return users