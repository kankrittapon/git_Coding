from utils import load_users

def login_user(username):
    users = load_users()
    return username in users
