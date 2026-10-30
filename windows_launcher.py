"""Desktop launcher. Binds the FastAPI UI to loopback only."""
import os
import secrets
import socket
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, filedialog
import webbrowser
import tempfile

import uvicorn


def self_check():
    """Verify packaged assets and authenticated API without opening a GUI."""
    from fastapi.testclient import TestClient

    from app import main

    asset = main.ROOT / "ui" / "index.html"
    script = main.ROOT / "ui" / "workflow.js"
    if not asset.is_file() or not script.is_file():
        raise RuntimeError("Packaged frontend files are missing")
    with tempfile.TemporaryDirectory(prefix="vibe-qa-self-check-") as temp_dir:
        main.DB_PATH = Path(temp_dir) / "check.sqlite3"
        secret = secrets.token_urlsafe(32)
        os.environ["QA_ADMIN_TOKEN"] = secret
        with TestClient(main.app) as client:
            if client.get("/").status_code != 200:
                raise RuntimeError("Frontend route not reachable")
            if client.get("/api/projects").status_code != 401:
                raise RuntimeError("Unauthorized access was not denied")
            authorized = client.get("/api/projects", headers={"Authorization": f"Bearer {secret}"})
            if authorized.status_code != 200 or authorized.json() != []:
                raise RuntimeError("Authenticated API or isolated SQLite database failed")


def app_data_dir():
    base = os.getenv("LOCALAPPDATA") or str(Path.home())
    target = Path(base) / "VibeCodeQAMaster"
    target.mkdir(parents=True, exist_ok=True)
    return target


def free_local_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Launcher:
    def __init__(self, root):
        self.root = root
        self.server = None
        self.url = None
        self.token = secrets.token_urlsafe(32)
        self.root.title("VIBE CODE QA MASTER")
        self.root.geometry("530x275")
        self.root.resizable(False, False)
        tk.Label(root, text="VIBE CODE QA MASTER", font=("Segoe UI", 17, "bold")).pack(pady=(22, 10))
        tk.Label(root, text="GitHub / 로컬 프로젝트 간편 검수", font=("Segoe UI", 10)).pack()
        self.status = tk.StringVar(value="준비 완료")
        tk.Label(root, textvariable=self.status).pack(pady=10)
        bar = tk.Frame(root)
        bar.pack()
        tk.Button(bar, text="검수 화면 열기", command=self.open, width=19).pack(side="left", padx=5)
        tk.Button(bar, text="관리자 키 복사", command=self.copy_token, width=19).pack(side="left", padx=5)
        tk.Button(root, text="실행 검사용 폴더 승인", command=self.approve_folder, width=35).pack(pady=8)
        tk.Label(root, text="관리자 키는 열리는 웹 화면에 붙여넣으세요.", fg="#555555").pack(pady=12)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def open(self):
        if self.server is None or self.server.should_exit:
            try:
                from app.main import app
                port = free_local_port()
                config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False, log_config=None)
                self.server = uvicorn.Server(config)
                worker = threading.Thread(target=self.server.run, daemon=True)
                worker.start()
                self.url = f"http://127.0.0.1:{port}"
                # The initial browser request must not race Uvicorn startup.
                for _ in range(30):
                    if self.server.started:
                        break
                    if not worker.is_alive():
                        raise RuntimeError("검수 서버가 시작되기 전에 종료되었습니다.")
                    time.sleep(0.1)
                if not self.server.started:
                    raise RuntimeError("검수 서버 시작 시간 초과")
                self.status.set("로컬 검수 서버 실행 중")
            except Exception as exc:
                if self.server is not None:
                    self.server.should_exit = True
                self.server = None
                messagebox.showerror("실행 오류", str(exc))
                return
        webbrowser.open(self.url)

    def copy_token(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.token)
        self.root.update()
        self.status.set("관리자 키 복사 완료")

    def approve_folder(self):
        folder = filedialog.askdirectory(title="테스트용 프로젝트 폴더 선택")
        if not folder:
            return
        if not messagebox.askyesno("실행 승인", "선택한 프로젝트에서 테스트 코드를 실행할 수 있습니다.\nDocker 격리 환경에서만 수행하며 네트워크를 차단합니다. 계속할까요?"):
            return
        try:
            from app.runtime import register
            project = register(folder)
            self.status.set("테스트 폴더 승인됨: " + project["name"])
        except (OSError, ValueError) as exc:
            messagebox.showerror("폴더 등록 실패", str(exc))

    def close(self):
        if self.server is not None:
            self.server.should_exit = True
        self.root.destroy()


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--self-check":
        self_check()
        return
    os.environ["QA_DB_PATH"] = str(app_data_dir() / "qa.sqlite3")
    os.environ["QA_ADMIN_TOKEN"] = secrets.token_urlsafe(40)
    # Launcher/admin use a single session secret; agent ingestion is separate.
    os.environ["QA_AGENT_TOKEN"] = secrets.token_urlsafe(40)
    root = tk.Tk()
    launcher = Launcher(root)
    os.environ["QA_ADMIN_TOKEN"] = launcher.token
    root.mainloop()


if __name__ == "__main__":
    main()
