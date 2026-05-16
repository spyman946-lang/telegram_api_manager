"""Локальное хранение профилей пользователей с api_id и api_hash."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass
class UserProfile:
    id: str
    username: str
    phone: str = ""
    api_id: str = ""
    api_hash: str = ""
    app_title: str = ""
    app_shortname: str = ""
    notes: str = ""
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def touch(self) -> None:
        self.updated_at = _now_iso()


class UserStorage:
    def __init__(self, path: Optional[Path] = None) -> None:
        base = Path(__file__).resolve().parent
        self.path = path or (base / "users_data.json")
        self._users: List[UserProfile] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self._users = []
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._users = []
            return
        items = raw.get("users", raw if isinstance(raw, list) else [])
        self._users = [UserProfile(**item) for item in items]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"users": [asdict(u) for u in self._users]}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_users(self) -> List[UserProfile]:
        return sorted(self._users, key=lambda u: u.username.lower())

    def get(self, user_id: str) -> Optional[UserProfile]:
        for user in self._users:
            if user.id == user_id:
                return user
        return None

    def add(
        self,
        username: str,
        phone: str = "",
        api_id: str = "",
        api_hash: str = "",
        app_title: str = "",
        app_shortname: str = "",
        notes: str = "",
    ) -> UserProfile:
        username = username.strip()
        if not username:
            raise ValueError("Имя пользователя не может быть пустым.")
        profile = UserProfile(
            id=str(uuid.uuid4()),
            username=username,
            phone=phone.strip(),
            api_id=str(api_id).strip(),
            api_hash=str(api_hash).strip(),
            app_title=app_title.strip(),
            app_shortname=app_shortname.strip(),
            notes=notes.strip(),
        )
        self._users.append(profile)
        self.save()
        return profile

    def update(self, user_id: str, **fields: str) -> UserProfile:
        user = self.get(user_id)
        if not user:
            raise KeyError("Пользователь не найден.")
        for key, value in fields.items():
            if hasattr(user, key) and key not in ("id", "created_at"):
                setattr(user, key, str(value).strip() if value is not None else "")
        user.touch()
        self.save()
        return user

    def delete(self, user_id: str) -> None:
        before = len(self._users)
        self._users = [u for u in self._users if u.id != user_id]
        if len(self._users) == before:
            raise KeyError("Пользователь не найден.")
        self.save()
