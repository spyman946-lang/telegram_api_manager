"""Клиент my.telegram.org для получения api_id и api_hash."""

from __future__ import annotations

import random
import re
import string
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://my.telegram.org"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/auth?to=apps",
    "User-Agent": USER_AGENT,
    "X-Requested-With": "XMLHttpRequest",
}


class MyTelegramError(Exception):
    """Ошибка при работе с my.telegram.org."""


@dataclass
class ApiCredentials:
    api_id: str
    api_hash: str


@dataclass
class AppFormDefaults:
    app_title: str
    app_shortname: str
    app_url: str = "https://telegram.org"
    app_platform: str = "desktop"
    app_desc: str = "Desktop client"


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone.strip())
    if not digits:
        raise MyTelegramError("Введите номер телефона с кодом страны.")
    return f"+{digits}"


def _random_word(length: Optional[int] = None) -> str:
    n = length or random.randint(5, 9)
    return "".join(random.choice(string.ascii_lowercase) for _ in range(n))


def random_app_defaults() -> AppFormDefaults:
    title = _random_word()
    return AppFormDefaults(
        app_title=title.capitalize(),
        app_shortname=title,
        app_desc=f"{title} application",
    )


class MyTelegramClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.phone: Optional[str] = None
        self.random_hash: Optional[str] = None

    def send_code(self, phone: str) -> None:
        self.phone = normalize_phone(phone)
        response = self.session.post(
            f"{BASE_URL}/auth/send_password",
            data={"phone": self.phone},
            headers=DEFAULT_HEADERS,
            timeout=30,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise MyTelegramError(
                f"Неожиданный ответ сервера ({response.status_code})."
            ) from exc

        if "random_hash" not in payload:
            message = payload.get("error") or payload.get("message") or str(payload)
            raise MyTelegramError(f"Не удалось отправить код: {message}")

        self.random_hash = payload["random_hash"]

    def login(self, code: str) -> None:
        if not self.phone or not self.random_hash:
            raise MyTelegramError("Сначала отправьте код на номер телефона.")

        code = code.strip()
        if not code:
            raise MyTelegramError("Введите код из Telegram.")

        response = self.session.post(
            f"{BASE_URL}/auth/login",
            data={
                "phone": self.phone,
                "random_hash": self.random_hash,
                "password": code,
            },
            headers=DEFAULT_HEADERS,
            timeout=30,
        )
        text = response.text.strip().lower()
        if text not in ("true", '"true"'):
            try:
                payload = response.json()
                message = payload.get("error") or payload.get("message") or response.text
            except ValueError:
                message = response.text or "Неверный код."
            raise MyTelegramError(f"Ошибка входа: {message}")

    def _parse_existing_credentials(self, html: str) -> Optional[ApiCredentials]:
        soup = BeautifulSoup(html, "html.parser")
        spans = soup.select(
            "span.form-control.input-xlarge.uneditable-input[onclick*='select']"
        )
        if len(spans) >= 2:
            api_id = spans[0].get_text(strip=True)
            api_hash = spans[1].get_text(strip=True)
            if api_id and api_hash:
                return ApiCredentials(api_id=api_id, api_hash=api_hash)

        labels = soup.find_all("label")
        api_id = api_hash = None
        for label in labels:
            text = label.get_text(strip=True).lower()
            parent = label.find_parent()
            if not parent:
                continue
            value_el = parent.find("span", class_=re.compile("uneditable-input"))
            if not value_el:
                continue
            value = value_el.get_text(strip=True)
            if "api_id" in text or "app api_id" in text:
                api_id = value
            elif "api_hash" in text:
                api_hash = value
        if api_id and api_hash:
            return ApiCredentials(api_id=api_id, api_hash=api_hash)
        return None

    def _extract_form_hash(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        hidden = soup.find("input", {"name": "hash"})
        if hidden and hidden.get("value"):
            return hidden["value"]
        raise MyTelegramError(
            "Не найден hash формы. Возможно, страница my.telegram.org изменилась."
        )

    def fetch_or_create_app(
        self,
        app_title: Optional[str] = None,
        app_shortname: Optional[str] = None,
        app_url: Optional[str] = None,
        app_platform: Optional[str] = None,
        app_desc: Optional[str] = None,
    ) -> ApiCredentials:
        page = self.session.get(f"{BASE_URL}/apps", timeout=30)
        if page.status_code != 200:
            raise MyTelegramError(f"Не удалось открыть страницу приложений ({page.status_code}).")

        existing = self._parse_existing_credentials(page.text)
        if existing:
            return existing

        defaults = random_app_defaults()
        form_hash = self._extract_form_hash(page.text)
        data = {
            "hash": form_hash,
            "app_title": app_title or defaults.app_title,
            "app_shortname": app_shortname or defaults.app_shortname,
            "app_url": app_url or defaults.app_url,
            "app_platform": app_platform or defaults.app_platform,
            "app_desc": app_desc or defaults.app_desc,
        }

        create_headers = {
            **DEFAULT_HEADERS,
            "Accept": "*/*",
            "Referer": f"{BASE_URL}/apps",
        }
        response = self.session.post(
            f"{BASE_URL}/apps/create",
            data=data,
            headers=create_headers,
            timeout=30,
        )
        if response.status_code >= 400 and response.text.strip().lower() not in ("true", '"true"'):
            try:
                payload = response.json()
                message = payload.get("error") or payload.get("message") or response.text
            except ValueError:
                message = response.text or "Ошибка создания приложения."
            if "already" not in message.lower():
                raise MyTelegramError(f"Создание приложения: {message}")

        page = self.session.get(f"{BASE_URL}/apps", timeout=30)
        credentials = self._parse_existing_credentials(page.text)
        if credentials:
            return credentials
        raise MyTelegramError(
            "Приложение создано, но не удалось прочитать api_id и api_hash со страницы."
        )

    def logout(self) -> None:
        try:
            self.session.get(f"{BASE_URL}/auth/logout", timeout=15)
        except requests.RequestException:
            pass
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.phone = None
        self.random_hash = None
