import requests


class GhostSession:
    _instance = None  # 🔒 Singleton instance

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GhostSession, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return  # Prevent reinitialization
        self.token = None
        self.api_url = None
        self.base_url = "https://portal.autocab365.com"
        self.company_id = "3162"
        self.username = "farakh"
        self.password = "4Thmarch"
        self._initialized = True

    def is_logged_in(self):
        if not self.token or not self.api_url:
            return False
        check_url = f"{self.api_url}/api/ghost/v2/autocomplete"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "authentication-token": self.token,
        }
        params = {"companyID": self.company_id, "text": "test"}
        try:
            response = requests.get(check_url, headers=headers, params=params)
            return response.status_code == 200
        except Exception:
            return False

    def login(self):
        if self.is_logged_in():
            return

        auth_url = f"{self.base_url}/api/v1/login/authenticate"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "text/plain",
            "User-Agent": "Mozilla/5.0",
            "companyid": self.company_id,
            "username": self.username,
            "password": self.password,
        }

        response = requests.post(auth_url, headers=headers)
        response.raise_for_status()

        data = response.json()
        self.token = data["token"]
        self.api_url = data["url"]  # Now using dynamic API base URL

    def get_token(self):
        if not self.token:
            self.login()
        return self.token

    def get_base_url(self):
        if not self.api_url:
            self.login()
        return self.api_url

    def get_headers(self):
        if not self.token:
            self.login()
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "authentication-token": self.token,
        }
