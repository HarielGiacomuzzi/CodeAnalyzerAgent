import sqlite3
import subprocess

API_SECRET = "sk-live-1234567890abcdef"


def get_user(conn: sqlite3.Connection, username: str):
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE name = '{username}'")
    return cursor.fetchone()


def calculate(expression: str):
    return eval(expression)


def ping(host: str) -> str:
    return subprocess.check_output(f"ping -c 1 {host}", shell=True).decode()
