import os
import requests
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.getenv("AUTOCAB_USERNAME")
PASSWORD = os.getenv("AUTOCAB_PASSWORD")


class GhostSession:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.token = None
        self.api_url = None
        self.base_url = "https://portal.autocab365.com"
        self.company_id = "3162"
        self.username = USERNAME
        self.password = PASSWORD
        self._initialized = True

    def is_logged_in(self):
        if not self.token or not self.api_url:
            return False

        try:
            response = requests.get(
                f"{self.api_url}/api/ghost/v2/autocomplete",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0",
                    "authentication-token": self.token,
                },
                params={"companyID": self.company_id},
                timeout=15,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def login(self):
        if not self.username or not self.password:
            raise ValueError("Missing AUTOCAB_USERNAME/AUTOCAB_PASSWORD environment variables")

        response = requests.post(
            f"{self.base_url}/api/v1/login/authenticate",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "text/plain",
                "User-Agent": "Mozilla/5.0",
                "companyid": self.company_id,
                "username": self.username,
                "password": self.password,
            },
            timeout=15,
        )
        response.raise_for_status()

        data = response.json()
        self.token = data["token"]
        self.api_url = data["url"].rstrip("/")

    def ensure_logged_in(self):
        if not self.is_logged_in():
            self.token = None
            self.api_url = None
            self.login()

    def force_refresh(self):
        self.token = None
        self.api_url = None
        self.login()

    def get_token(self):
        self.ensure_logged_in()
        return self.token

    def get_base_url(self):
        self.ensure_logged_in()
        return self.api_url

    def get_headers(self):
        self.ensure_logged_in()
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "authentication-token": self.token,
        }