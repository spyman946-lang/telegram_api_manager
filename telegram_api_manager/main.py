"""
Telegram API Manager — получение api_id / api_hash и менеджер профилей.

Запуск: python main.py
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, ttk

import requests

from mytelegram_client import (
    ApiCredentials,
    MyTelegramClient,
    MyTelegramError,
    random_app_defaults,
)
from user_storage import UserProfile, UserStorage


class TelegramApiApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Telegram API ID / Hash — менеджер")
        self.minsize(920, 620)
        self.geometry("980x680")

        self.storage = UserStorage()
        self.client = MyTelegramClient()
        self._worker: threading.Thread | None = None
        self._ui_queue: queue.Queue = queue.Queue()

        self._build_style()
        self._build_ui()
        self.after(100, self._poll_queue)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Step.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 9))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=(12, 10, 12, 0))
        header.pack(fill=tk.X)
        ttk.Label(
            header,
            text="Получение API ID и API Hash для Telegram",
            style="Title.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            header,
            text="Весь процесс выполняется в этом окне через my.telegram.org. "
            "Данные сохраняются локально в users_data.json.",
            style="Status.TLabel",
            wraplength=900,
        ).pack(anchor=tk.W, pady=(4, 0))

        self.status_var = tk.StringVar(value="Готово")

        self.notebook = ttk.Notebook(self, padding=8)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._build_fetch_tab()
        self._build_manager_tab()

        status_bar = ttk.Label(
            self,
            textvariable=self.status_var,
            style="Status.TLabel",
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(8, 4),
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # --- Вкладка получения API ---

    def _build_fetch_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Получить API")

        self.fetch_steps = ttk.Frame(tab)
        self.fetch_steps.pack(fill=tk.BOTH, expand=True)

        self.step_frames: list[ttk.Frame] = []
        for _ in range(4):
            frame = ttk.Frame(self.fetch_steps)
            self.step_frames.append(frame)

        self._build_step_phone()
        self._build_step_code()
        self._build_step_app()
        self._build_step_result()

        nav = ttk.Frame(tab)
        nav.pack(fill=tk.X, pady=(12, 0))
        self.btn_back = ttk.Button(nav, text="← Назад", command=self._go_back)
        self.btn_back.pack(side=tk.LEFT)
        self.btn_next = ttk.Button(
            nav, text="Далее →", style="Accent.TButton", command=self._go_next
        )
        self.btn_next.pack(side=tk.RIGHT)

        self.fetch_log = tk.Text(tab, height=6, wrap=tk.WORD, state=tk.DISABLED)
        self.fetch_log.pack(fill=tk.X, pady=(12, 0))

        self._show_step(0)

    def _build_step_phone(self) -> None:
        f = self.step_frames[0]
        ttk.Label(f, text="Шаг 1. Номер телефона", style="Step.TLabel").pack(anchor=tk.W)
        ttk.Label(
            f,
            text="Введите номер в международном формате (например +79001234567). "
            "Код придёт в приложение Telegram.",
            wraplength=860,
        ).pack(anchor=tk.W, pady=(8, 4))
        row = ttk.Frame(f)
        row.pack(fill=tk.X, pady=8)
        ttk.Label(row, text="Телефон:").pack(side=tk.LEFT)
        self.phone_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.phone_var, width=32).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(row, text="Отправить код", command=self._send_code).pack(
            side=tk.LEFT, padx=(12, 0)
        )

    def _build_step_code(self) -> None:
        f = self.step_frames[1]
        ttk.Label(f, text="Шаг 2. Код подтверждения", style="Step.TLabel").pack(anchor=tk.W)
        ttk.Label(
            f,
            text="Откройте Telegram — придёт сообщение от Telegram с кодом для my.telegram.org.",
            wraplength=860,
        ).pack(anchor=tk.W, pady=(8, 4))
        row = ttk.Frame(f)
        row.pack(fill=tk.X, pady=8)
        ttk.Label(row, text="Код:").pack(side=tk.LEFT)
        self.code_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.code_var, width=20, show="*").pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(row, text="Войти", command=self._login).pack(side=tk.LEFT, padx=(12, 0))

    def _build_step_app(self) -> None:
        f = self.step_frames[2]
        ttk.Label(f, text="Шаг 3. Приложение (если ещё не создано)", style="Step.TLabel").pack(
            anchor=tk.W
        )
        ttk.Label(
            f,
            text="Если у аккаунта уже есть api_id и api_hash, они будут загружены автоматически. "
            "Иначе создаётся новое приложение с указанными полями.",
            wraplength=860,
        ).pack(anchor=tk.W, pady=(8, 8))

        defaults = random_app_defaults()
        grid = ttk.Frame(f)
        grid.pack(fill=tk.X)

        self.app_title_var = tk.StringVar(value=defaults.app_title)
        self.app_short_var = tk.StringVar(value=defaults.app_shortname)
        self.app_url_var = tk.StringVar(value=defaults.app_url)
        self.app_platform_var = tk.StringVar(value=defaults.app_platform)
        self.app_desc_var = tk.StringVar(value=defaults.app_desc)

        fields = [
            ("Название приложения:", self.app_title_var),
            ("Short name:", self.app_short_var),
            ("URL:", self.app_url_var),
            ("Платформа:", self.app_platform_var),
            ("Описание:", self.app_desc_var),
        ]
        for i, (label, var) in enumerate(fields):
            ttk.Label(grid, text=label).grid(row=i, column=0, sticky=tk.W, pady=4)
            ttk.Entry(grid, textvariable=var, width=48).grid(
                row=i, column=1, sticky=tk.W, padx=(8, 0), pady=4
            )

        btns = ttk.Frame(f)
        btns.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(btns, text="Случайные значения", command=self._fill_random_app).pack(
            side=tk.LEFT
        )
        ttk.Button(
            btns, text="Получить API ID / Hash", command=self._fetch_credentials
        ).pack(side=tk.LEFT, padx=(8, 0))

    def _build_step_result(self) -> None:
        f = self.step_frames[3]
        ttk.Label(f, text="Шаг 4. Результат", style="Step.TLabel").pack(anchor=tk.W)
        ttk.Label(f, text="Скопируйте данные или сохраните в менеджер.").pack(
            anchor=tk.W, pady=(8, 8)
        )

        grid = ttk.Frame(f)
        grid.pack(fill=tk.X)
        self.result_api_id = tk.StringVar()
        self.result_api_hash = tk.StringVar()
        self.result_phone = tk.StringVar()

        for i, (label, var) in enumerate(
            [
                ("Телефон:", self.result_phone),
                ("API ID:", self.result_api_id),
                ("API Hash:", self.result_api_hash),
            ]
        ):
            ttk.Label(grid, text=label).grid(row=i, column=0, sticky=tk.W, pady=4)
            entry = ttk.Entry(grid, textvariable=var, width=56)
            entry.grid(row=i, column=1, sticky=tk.W, padx=(8, 0), pady=4)
            ttk.Button(
                grid,
                text="Копировать",
                command=lambda v=var: self._copy_to_clipboard(v.get()),
            ).grid(row=i, column=2, padx=(8, 0))

        save = ttk.LabelFrame(f, text="Сохранить в менеджер", padding=10)
        save.pack(fill=tk.X, pady=(16, 0))
        row = ttk.Frame(save)
        row.pack(fill=tk.X)
        ttk.Label(row, text="Имя пользователя:").pack(side=tk.LEFT)
        self.save_username_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.save_username_var, width=28).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(row, text="Сохранить профиль", command=self._save_result_to_manager).pack(
            side=tk.LEFT, padx=(12, 0)
        )

        ttk.Button(f, text="Новый запрос (сброс)", command=self._reset_fetch).pack(
            anchor=tk.W, pady=(16, 0)
        )

    def _show_step(self, index: int) -> None:
        self._current_step = index
        for i, frame in enumerate(self.step_frames):
            frame.pack_forget()
            if i == index:
                frame.pack(fill=tk.BOTH, expand=True)
        self.btn_back.configure(state=tk.NORMAL if index > 0 else tk.DISABLED)
        labels = ["Отправить код", "Войти", "Получить API", "Готово"]
        self.btn_next.configure(
            text="Далее →" if index < 3 else "Завершить",
            state=tk.DISABLED if index == 0 else tk.NORMAL,
        )
        self.status_var.set(f"Шаг {index + 1} из 4 — {labels[index]}")

    def _go_back(self) -> None:
        if self._current_step > 0:
            self._show_step(self._current_step - 1)

    def _go_next(self) -> None:
        if self._current_step == 1:
            self._login()
        elif self._current_step == 2:
            self._fetch_credentials()
        elif self._current_step < 3:
            self._show_step(self._current_step + 1)
        else:
            self.notebook.select(1)

    # --- Вкладка менеджера ---

    def _build_manager_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Менеджер пользователей")

        top = ttk.Frame(tab)
        top.pack(fill=tk.X)
        ttk.Button(top, text="Добавить", command=self._manager_add).pack(side=tk.LEFT)
        ttk.Button(top, text="Изменить", command=self._manager_edit).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(top, text="Удалить", command=self._manager_delete).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(top, text="Обновить список", command=self._refresh_user_list).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        body = ttk.Panedwindow(tab, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        left = ttk.Frame(body)
        body.add(left, weight=1)
        columns = ("username", "phone", "api_id")
        self.user_tree = ttk.Treeview(
            left, columns=columns, show="headings", height=16, selectmode="browse"
        )
        self.user_tree.heading("username", text="Имя")
        self.user_tree.heading("phone", text="Телефон")
        self.user_tree.heading("api_id", text="API ID")
        self.user_tree.column("username", width=160)
        self.user_tree.column("phone", width=140)
        self.user_tree.column("api_id", width=120)
        scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.user_tree.yview)
        self.user_tree.configure(yscrollcommand=scroll.set)
        self.user_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.user_tree.bind("<<TreeviewSelect>>", self._on_user_select)

        right = ttk.LabelFrame(body, text="Данные профиля", padding=10)
        body.add(right, weight=2)

        self.m_username = tk.StringVar()
        self.m_phone = tk.StringVar()
        self.m_api_id = tk.StringVar()
        self.m_api_hash = tk.StringVar()
        self.m_app_title = tk.StringVar()
        self.m_app_short = tk.StringVar()
        self.m_notes = tk.StringVar()
        self.m_created = tk.StringVar()
        self.m_updated = tk.StringVar()
        self._selected_user_id: str | None = None

        form = ttk.Frame(right)
        form.pack(fill=tk.BOTH, expand=True)
        manager_fields = [
            ("Имя пользователя:", self.m_username),
            ("Телефон:", self.m_phone),
            ("API ID:", self.m_api_id),
            ("API Hash:", self.m_api_hash),
            ("App title:", self.m_app_title),
            ("Short name:", self.m_app_short),
            ("Заметки:", self.m_notes),
        ]
        for i, (label, var) in enumerate(manager_fields):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky=tk.W, pady=4)
            show = "*" if "Hash" in label else ""
            width = 42 if "Hash" not in label else 48
            ttk.Entry(form, textvariable=var, width=width, show=show).grid(
                row=i, column=1, sticky=tk.W, padx=(8, 0), pady=4
            )
            ttk.Button(
                form,
                text="Копир.",
                width=6,
                command=lambda v=var: self._copy_to_clipboard(v.get()),
            ).grid(row=i, column=2, padx=(4, 0))

        meta = ttk.Frame(right)
        meta.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(meta, textvariable=self.m_created).pack(anchor=tk.W)
        ttk.Label(meta, textvariable=self.m_updated).pack(anchor=tk.W)

        actions = ttk.Frame(right)
        actions.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(actions, text="Сохранить изменения", command=self._manager_save).pack(
            side=tk.LEFT
        )
        ttk.Button(
            actions,
            text="Экспорт JSON",
            command=self._export_selected,
        ).pack(side=tk.LEFT, padx=(8, 0))

        self._refresh_user_list()

    # --- Логика получения API ---

    def _log(self, message: str) -> None:
        self.fetch_log.configure(state=tk.NORMAL)
        self.fetch_log.insert(tk.END, message + "\n")
        self.fetch_log.see(tk.END)
        self.fetch_log.configure(state=tk.DISABLED)

    def _set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        self.btn_next.configure(state=state if not busy else tk.DISABLED)
        self.btn_back.configure(state=tk.DISABLED if busy else tk.NORMAL)

    def _run_async(self, task, on_success=None) -> None:
        if self._worker and self._worker.is_alive():
            messagebox.showwarning("Подождите", "Операция уже выполняется.")
            return

        self._set_busy(True)

        def runner() -> None:
            try:
                result = task()
                self._ui_queue.put(("ok", result, on_success))
            except MyTelegramError as exc:
                self._ui_queue.put(("error", str(exc), None))
            except requests.RequestException as exc:
                self._ui_queue.put(("error", f"Сеть: {exc}", None))
            except Exception as exc:
                self._ui_queue.put(("error", f"Ошибка: {exc}", None))

        self._worker = threading.Thread(target=runner, daemon=True)
        self._worker.start()

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload, callback = self._ui_queue.get_nowait()
                self._set_busy(False)
                if kind == "ok":
                    if callback:
                        callback(payload)
                else:
                    messagebox.showerror("Ошибка", payload)
                    self._log(f"Ошибка: {payload}")
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _send_code(self) -> None:
        phone = self.phone_var.get().strip()
        if not phone:
            messagebox.showwarning("Телефон", "Введите номер телефона.")
            return

        def task():
            self.client.send_code(phone)
            return self.client.phone

        def on_success(normalized_phone: str) -> None:
            self._log(f"Код отправлен на {normalized_phone}")
            self.status_var.set("Код отправлен — проверьте Telegram")
            self._show_step(1)

        self._log(f"Отправка кода на {phone}...")
        self._run_async(task, on_success)

    def _login(self) -> None:
        code = self.code_var.get().strip()
        if not code:
            messagebox.showwarning("Код", "Введите код из Telegram.")
            return

        def task():
            self.client.login(code)
            return True

        def on_success(_: bool) -> None:
            self._log("Вход выполнен.")
            self.status_var.set("Вход успешен")
            self._show_step(2)

        self._log("Проверка кода...")
        self._run_async(task, on_success)

    def _fill_random_app(self) -> None:
        d = random_app_defaults()
        self.app_title_var.set(d.app_title)
        self.app_short_var.set(d.app_shortname)
        self.app_url_var.set(d.app_url)
        self.app_platform_var.set(d.app_platform)
        self.app_desc_var.set(d.app_desc)

    def _fetch_credentials(self) -> None:
        def task() -> ApiCredentials:
            return self.client.fetch_or_create_app(
                app_title=self.app_title_var.get().strip(),
                app_shortname=self.app_short_var.get().strip(),
                app_url=self.app_url_var.get().strip(),
                app_platform=self.app_platform_var.get().strip(),
                app_desc=self.app_desc_var.get().strip(),
            )

        def on_success(creds: ApiCredentials) -> None:
            phone = self.client.phone or self.phone_var.get().strip()
            self.result_phone.set(phone)
            self.result_api_id.set(creds.api_id)
            self.result_api_hash.set(creds.api_hash)
            self.save_username_var.set(phone.replace("+", "") if phone else "")
            self._log(f"Получено: api_id={creds.api_id}")
            self._show_step(3)
            messagebox.showinfo(
                "Готово",
                f"API ID: {creds.api_id}\nAPI Hash получен (см. поле на шаге 4).",
            )

        self._log("Запрос api_id и api_hash...")
        self._run_async(task, on_success)

    def _save_result_to_manager(self) -> None:
        username = self.save_username_var.get().strip()
        if not username:
            messagebox.showwarning("Имя", "Укажите имя пользователя для сохранения.")
            return
        try:
            self.storage.add(
                username=username,
                phone=self.result_phone.get().strip(),
                api_id=self.result_api_id.get().strip(),
                api_hash=self.result_api_hash.get().strip(),
                app_title=self.app_title_var.get().strip(),
                app_shortname=self.app_short_var.get().strip(),
            )
        except ValueError as exc:
            messagebox.showwarning("Сохранение", str(exc))
            return
        self._refresh_user_list()
        self._log(f"Профиль «{username}» сохранён.")
        messagebox.showinfo("Сохранено", f"Профиль «{username}» добавлен в менеджер.")

    def _reset_fetch(self) -> None:
        if messagebox.askyesno("Сброс", "Начать новый запрос? Текущая сессия будет сброшена."):
            self.client.logout()
            self.phone_var.set("")
            self.code_var.set("")
            self.result_api_id.set("")
            self.result_api_hash.set("")
            self.result_phone.set("")
            self._fill_random_app()
            self._show_step(0)
            self._log("Сессия сброшена.")

    def _copy_to_clipboard(self, text: str) -> None:
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set("Скопировано в буфер обмена")

    # --- Менеджер ---

    def _refresh_user_list(self) -> None:
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        for user in self.storage.list_users():
            self.user_tree.insert(
                "",
                tk.END,
                iid=user.id,
                values=(user.username, user.phone, user.api_id),
            )
        self.status_var.set(f"Профилей: {len(self.storage.list_users())}")

    def _on_user_select(self, _event=None) -> None:
        selected = self.user_tree.selection()
        if not selected:
            return
        user_id = selected[0]
        user = self.storage.get(user_id)
        if not user:
            return
        self._fill_manager_form(user)

    def _fill_manager_form(self, user: UserProfile) -> None:
        self._selected_user_id = user.id
        self.m_username.set(user.username)
        self.m_phone.set(user.phone)
        self.m_api_id.set(user.api_id)
        self.m_api_hash.set(user.api_hash)
        self.m_app_title.set(user.app_title)
        self.m_app_short.set(user.app_shortname)
        self.m_notes.set(user.notes)
        self.m_created.set(f"Создан: {user.created_at}")
        self.m_updated.set(f"Изменён: {user.updated_at}")

    def _manager_add(self) -> None:
        dialog = UserEditDialog(self, title="Новый пользователь")
        self.wait_window(dialog)
        if not dialog.result:
            return
        try:
            profile = self.storage.add(**dialog.result)
        except ValueError as exc:
            messagebox.showwarning("Добавление", str(exc))
            return
        self._refresh_user_list()
        self.user_tree.selection_set(profile.id)
        self._fill_manager_form(profile)

    def _manager_edit(self) -> None:
        if not self._selected_user_id:
            messagebox.showinfo("Выбор", "Выберите пользователя в списке.")
            return
        user = self.storage.get(self._selected_user_id)
        if not user:
            return
        dialog = UserEditDialog(self, title="Изменить пользователя", initial=user)
        self.wait_window(dialog)
        if not dialog.result:
            return
        try:
            updated = self.storage.update(self._selected_user_id, **dialog.result)
        except KeyError as exc:
            messagebox.showerror("Ошибка", str(exc))
            return
        self._refresh_user_list()
        self.user_tree.selection_set(updated.id)
        self._fill_manager_form(updated)

    def _manager_save(self) -> None:
        if not self._selected_user_id:
            messagebox.showinfo("Выбор", "Выберите пользователя.")
            return
        try:
            updated = self.storage.update(
                self._selected_user_id,
                username=self.m_username.get(),
                phone=self.m_phone.get(),
                api_id=self.m_api_id.get(),
                api_hash=self.m_api_hash.get(),
                app_title=self.m_app_title.get(),
                app_shortname=self.m_app_short.get(),
                notes=self.m_notes.get(),
            )
        except (KeyError, ValueError) as exc:
            messagebox.showwarning("Сохранение", str(exc))
            return
        self._refresh_user_list()
        self.user_tree.selection_set(updated.id)
        self._fill_manager_form(updated)
        messagebox.showinfo("Сохранено", "Профиль обновлён.")

    def _manager_delete(self) -> None:
        if not self._selected_user_id:
            messagebox.showinfo("Выбор", "Выберите пользователя для удаления.")
            return
        user = self.storage.get(self._selected_user_id)
        if not user:
            return
        if not messagebox.askyesno("Удаление", f"Удалить профиль «{user.username}»?"):
            return
        try:
            self.storage.delete(self._selected_user_id)
        except KeyError as exc:
            messagebox.showerror("Ошибка", str(exc))
            return
        self._selected_user_id = None
        for var in (
            self.m_username,
            self.m_phone,
            self.m_api_id,
            self.m_api_hash,
            self.m_app_title,
            self.m_app_short,
            self.m_notes,
            self.m_created,
            self.m_updated,
        ):
            var.set("")
        self._refresh_user_list()

    def _export_selected(self) -> None:
        if not self._selected_user_id:
            messagebox.showinfo("Экспорт", "Выберите пользователя.")
            return
        user = self.storage.get(self._selected_user_id)
        if not user:
            return
        from dataclasses import asdict
        import json

        text = json.dumps(asdict(user), ensure_ascii=False, indent=2)
        self._copy_to_clipboard(text)
        messagebox.showinfo("Экспорт", "JSON профиля скопирован в буфер обмена.")


class UserEditDialog(tk.Toplevel):
    def __init__(self, parent: TelegramApiApp, title: str, initial: UserProfile | None = None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result: dict | None = None
        self.transient(parent)
        self.grab_set()

        vars_map = {
            "username": tk.StringVar(value=initial.username if initial else ""),
            "phone": tk.StringVar(value=initial.phone if initial else ""),
            "api_id": tk.StringVar(value=initial.api_id if initial else ""),
            "api_hash": tk.StringVar(value=initial.api_hash if initial else ""),
            "app_title": tk.StringVar(value=initial.app_title if initial else ""),
            "app_shortname": tk.StringVar(value=initial.app_shortname if initial else ""),
            "notes": tk.StringVar(value=initial.notes if initial else ""),
        }

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        labels = [
            ("Имя пользователя *", "username"),
            ("Телефон", "phone"),
            ("API ID", "api_id"),
            ("API Hash", "api_hash"),
            ("App title", "app_title"),
            ("Short name", "app_shortname"),
            ("Заметки", "notes"),
        ]
        for i, (label, key) in enumerate(labels):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=4)
            show = "*" if key == "api_hash" else ""
            ttk.Entry(frame, textvariable=vars_map[key], width=40, show=show).grid(
                row=i, column=1, padx=(8, 0), pady=4
            )

        btns = ttk.Frame(frame)
        btns.grid(row=len(labels), column=0, columnspan=2, pady=(12, 0), sticky=tk.E)

        def save() -> None:
            data = {k: v.get().strip() for k, v in vars_map.items()}
            if not data["username"]:
                messagebox.showwarning("Имя", "Имя пользователя обязательно.", parent=self)
                return
            self.result = data
            self.destroy()

        ttk.Button(btns, text="Отмена", command=self.destroy).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(btns, text="OK", command=save).pack(side=tk.RIGHT)

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


def main() -> None:
    try:
        app = TelegramApiApp()
        app.mainloop()
    except Exception as exc:
        import traceback

        err_text = traceback.format_exc()
        log_path = Path(__file__).resolve().parent / "error.log"
        try:
            log_path.write_text(err_text, encoding="utf-8")
        except OSError:
            pass
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Ошибка запуска",
                f"{exc}\n\nПодробности в файле:\n{log_path}",
            )
            root.destroy()
        except tk.TclError:
            print(err_text, file=__import__("sys").stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
