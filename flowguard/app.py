from __future__ import annotations

import json
import logging
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .executor import execute_plan, latest_journal, rollback
from .models import ScanResult
from .local_llm import (
    DEFAULT_ENDPOINTS, DEFAULT_MODEL, DEFAULT_PROVIDER, LocalLLMError,
    LocalModelConfig, fallback_suggestion, generate_suggestion, list_models,
)
from .planner import build_organization_plan
from .scanner import scan_folder

LOG_DIR = Path.home() / "AppData" / "Local" / "FlowGuard" / "logs"
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=LOG_DIR / "flowguard.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
except OSError:
    # Restricted/sandboxed environments may deny LocalAppData writes. Logging
    # must never prevent the safety UI from starting.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class FlowGuardApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("FlowGuard — 안전한 로컬 워크플로 도우미")
        self.geometry("980x700")
        self.minsize(820, 600)
        self.result: ScanResult | None = None
        self.plan = []
        self.monitoring = False
        self.last_snapshot: tuple[tuple[str, float], ...] = ()
        self.folder = tk.StringVar()
        self.provider = tk.StringVar(value=DEFAULT_PROVIDER)
        self.endpoint = tk.StringVar(value=DEFAULT_ENDPOINTS[DEFAULT_PROVIDER])
        self.model = tk.StringVar(value=DEFAULT_MODEL)
        self.dry_run = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="폴더를 선택한 뒤 스캔하세요.")
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._build_ui()
        self.after(150, self._drain_events)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Safe.TLabel", foreground="#146c43")
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="FlowGuard", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="선택한 폴더 안에서만 작동 · 승인 전 변경 없음 · 삭제 기능 없음", style="Safe.TLabel").pack(anchor="w", pady=(2, 16))

        picker = ttk.Frame(outer)
        picker.pack(fill="x")
        ttk.Entry(picker, textvariable=self.folder).pack(side="left", fill="x", expand=True)
        ttk.Button(picker, text="폴더 선택", command=self.choose_folder).pack(side="left", padx=(8, 0))
        ttk.Button(picker, text="지금 스캔", command=self.start_scan).pack(side="left", padx=(8, 0))
        self.monitor_button = ttk.Button(picker, text="감시 시작", command=self.toggle_monitor)
        self.monitor_button.pack(side="left", padx=(8, 0))

        options = ttk.Frame(outer)
        options.pack(fill="x", pady=10)
        ttk.Label(options, text="로컬 AI:").pack(side="left")
        provider = ttk.Combobox(options, textvariable=self.provider, values=list(DEFAULT_ENDPOINTS), state="readonly", width=12)
        provider.pack(side="left", padx=(6, 6)); provider.bind("<<ComboboxSelected>>", self._provider_changed)
        self.model_box = ttk.Combobox(options, textvariable=self.model, width=22)
        self.model_box.pack(side="left", padx=(0, 6))
        ttk.Button(options, text="모델 찾기", command=self.refresh_models).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(options, text="드라이런 (권장, 파일을 변경하지 않음)", variable=self.dry_run).pack(side="left")

        endpoint_row = ttk.Frame(outer)
        endpoint_row.pack(fill="x", pady=(0, 8))
        ttk.Label(endpoint_row, text="로컬 서버 주소:").pack(side="left")
        ttk.Entry(endpoint_row, textvariable=self.endpoint, width=42).pack(side="left", padx=6)
        ttk.Label(endpoint_row, text="localhost만 허용", style="Safe.TLabel").pack(side="left")

        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True)
        self.summary_text = self._tab("스캔 결과")
        self.suggestion_text = self._tab("AI 제안")
        self.plan_text = self._tab("실행 계획")
        self._set_text(self.summary_text, "폴더를 선택하고 ‘지금 스캔’을 누르세요.")
        self._set_text(self.suggestion_text, "스캔이 끝나면 Qwen 3.5-4B 제안을 자동으로 요청합니다.")
        self._set_text(self.plan_text, "스캔이 끝나면 안전한 실행 계획을 자동으로 만듭니다.")
        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="AI 제안 받기", command=self.start_ai).pack(side="left")
        ttk.Button(buttons, text="정리 계획 만들기", command=self.make_plan).pack(side="left", padx=8)
        ttk.Button(buttons, text="계획 실행", command=self.run_plan).pack(side="left")
        ttk.Button(buttons, text="최근 실행 되돌리기", command=self.undo_latest).pack(side="left", padx=8)
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(10, 0))

    def _tab(self, name: str) -> tk.Text:
        frame = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(frame, text=name)
        text = tk.Text(frame, wrap="word", font=("Segoe UI", 10), relief="flat", padx=8, pady=8)
        text.pack(fill="both", expand=True)
        text.configure(state="disabled")
        return text

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def choose_folder(self) -> None:
        chosen = filedialog.askdirectory(title="FlowGuard가 볼 폴더 선택")
        if chosen:
            self.folder.set(chosen)

    def start_scan(self) -> None:
        folder = self.folder.get().strip()
        if not folder:
            messagebox.showinfo("폴더 필요", "먼저 폴더를 선택하세요.")
            return
        self.status.set("선택한 폴더를 읽는 중…")
        threading.Thread(target=self._scan_worker, args=(folder,), daemon=True).start()

    def _scan_worker(self, folder: str) -> None:
        try:
            self._events.put(("scan", scan_folder(folder)))
        except Exception as exc:
            logging.exception("scan failed")
            self._events.put(("error", str(exc)))

    def _show_result(self, result: ScanResult) -> None:
        self.result = result
        self.plan = []
        size_mb = result.total_size / (1024 * 1024)
        lines = [f"폴더: {result.root}", f"파일: {len(result.files)}개 · 총 {size_mb:.1f} MB", "", "감지한 패턴:"]
        lines.extend(f"• {p.title}: {p.detail}" for p in result.patterns)
        if not result.patterns:
            lines.append("• 의미 있는 반복 패턴이 없습니다.")
        self._set_text(self.summary_text, "\n".join(lines))
        self.last_snapshot = tuple((f.path, f.modified) for f in result.files)
        logging.info("scan completed root=%s files=%s", result.root, len(result.files))
        # A scan is the user's explicit request to analyze this folder. Build
        # both outputs automatically; neither path changes any files.
        self.make_plan(select_tab=False)
        self.start_ai()

    def _pattern_summary(self) -> str:
        if not self.result:
            return ""
        return "\n".join(f"- {p.title}: {p.detail}" for p in self.result.patterns)

    def _provider_changed(self, _event: object = None) -> None:
        self.endpoint.set(DEFAULT_ENDPOINTS[self.provider.get()])
        self.model.set(DEFAULT_MODEL if self.provider.get() == "Ollama" else "local-model")

    def _model_config(self) -> LocalModelConfig:
        return LocalModelConfig(self.provider.get(), self.model.get(), self.endpoint.get()).validated()

    def refresh_models(self) -> None:
        try:
            config = self._model_config()
        except LocalLLMError as exc:
            messagebox.showerror("로컬 AI 설정", str(exc)); return
        self.status.set("로컬 서버에서 설치된 모델 목록을 확인하는 중…")
        threading.Thread(target=self._models_worker, args=(config,), daemon=True).start()

    def _models_worker(self, config: LocalModelConfig) -> None:
        try:
            self._events.put(("models", list_models(config)))
        except LocalLLMError as exc:
            self._events.put(("error", str(exc)))

    def start_ai(self) -> None:
        if not self.result:
            messagebox.showinfo("스캔 필요", "먼저 폴더를 스캔하세요.")
            return
        try:
            config = self._model_config()
        except LocalLLMError as exc:
            messagebox.showerror("로컬 AI 설정", str(exc)); return
        self._set_text(self.suggestion_text, f"{config.provider}의 {config.model} 모델이 분석 중입니다…\n\n파일은 변경되지 않습니다.")
        self.status.set("선택한 로컬 모델에 제안을 요청하는 중…")
        threading.Thread(target=self._ai_worker, args=(config,), daemon=True).start()

    def _ai_worker(self, config: LocalModelConfig) -> None:
        summary = self._pattern_summary()
        try:
            answer = generate_suggestion(summary, config)
            source = f"{config.provider} · {config.model}"
        except LocalLLMError:
            answer, source = fallback_suggestion(summary), "안전 기본 규칙"
        self._events.put(("ai", (answer, source)))

    def make_plan(self, select_tab: bool = True) -> None:
        if not self.result:
            messagebox.showinfo("스캔 필요", "먼저 폴더를 스캔하세요.")
            return
        self.plan = build_organization_plan(self.result)
        if not self.plan:
            text = "실행할 안전한 정리 작업이 없습니다.\n(최상위 폴더에 같은 형식의 지원 파일이 3개 이상일 때만 계획합니다.)"
        else:
            lines = [f"총 {len(self.plan)}개 이동 예정", "", *[f"{i+1}. {a.source}\n   → {a.destination}\n   이유: {a.reason}" for i, a in enumerate(self.plan)]]
            text = "\n".join(lines)
        self._set_text(self.plan_text, text)
        if select_tab:
            self.tabs.select(2)
        self.status.set("계획만 만들었습니다. 아직 파일은 변경되지 않았습니다.")

    def run_plan(self) -> None:
        if not self.result or not self.plan:
            messagebox.showinfo("계획 필요", "먼저 정리 계획을 만드세요.")
            return
        mode = "드라이런" if self.dry_run.get() else "실제 이동"
        if not messagebox.askyesno("명시적 승인", f"{len(self.plan)}개 작업을 {mode}으로 실행할까요?\n\n삭제 작업은 없으며 선택 폴더 밖으로 이동하지 않습니다."):
            return
        try:
            record = execute_plan(self.result.root, self.plan, dry_run=self.dry_run.get())
            self._set_text(self.plan_text, json.dumps(record, ensure_ascii=False, indent=2))
            self.status.set(f"{mode} 완료. 실제 이동은 저널에 기록되었습니다.")
            logging.info("plan executed id=%s dry_run=%s", record["id"], record["dry_run"])
        except Exception as exc:
            logging.exception("execution failed")
            messagebox.showerror("실행 실패", str(exc))

    def undo_latest(self) -> None:
        if not self.folder.get().strip():
            return
        journal = latest_journal(self.folder.get())
        if not journal:
            messagebox.showinfo("되돌릴 작업 없음", "이 폴더의 실제 실행 기록이 없습니다.")
            return
        if messagebox.askyesno("되돌리기 승인", "가장 최근 실제 파일 이동을 되돌릴까요?\n기존 파일과 충돌하면 해당 항목은 건너뜁니다."):
            outcome = rollback(journal)
            messagebox.showinfo("되돌리기 완료", f"복원 {len(outcome['restored'])}개 · 건너뜀 {len(outcome['skipped'])}개")
            self.start_scan()

    def toggle_monitor(self) -> None:
        if self.monitoring:
            self.monitoring = False
            self.monitor_button.configure(text="감시 시작")
            self.status.set("폴더 감시를 중지했습니다.")
            return
        if not self.folder.get().strip():
            messagebox.showinfo("폴더 필요", "먼저 폴더를 선택하세요.")
            return
        self.monitoring = True
        self.monitor_button.configure(text="감시 중지")
        self.status.set("선택 폴더만 10초 간격으로 확인합니다. 자동 실행은 하지 않습니다.")
        self.after(10_000, self._monitor_tick)

    def _monitor_tick(self) -> None:
        if not self.monitoring:
            return
        threading.Thread(target=self._monitor_worker, daemon=True).start()

    def _monitor_worker(self) -> None:
        try:
            result = scan_folder(self.folder.get())
            snapshot = tuple((f.path, f.modified) for f in result.files)
            if snapshot != self.last_snapshot:
                self._events.put(("scan", result))
                self._events.put(("notice", "폴더 변경을 감지해 결과를 갱신했습니다. 자동 실행은 하지 않았습니다."))
        except Exception as exc:
            self._events.put(("error", str(exc)))
        finally:
            self._events.put(("monitor_next", None))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "scan": self._show_result(payload)  # type: ignore[arg-type]
                elif kind == "ai":
                    answer, source = payload  # type: ignore[misc]
                    self._set_text(self.suggestion_text, f"제안 출처: {source}\n\n{answer}")
                    self.tabs.select(1); self.status.set(f"{source} 제안 준비 완료. 제안은 자동 실행되지 않습니다.")
                elif kind == "error": messagebox.showerror("FlowGuard", str(payload)); self.status.set("작업에 실패했습니다.")
                elif kind == "notice": self.status.set(str(payload))
                elif kind == "models":
                    models = list(payload)  # type: ignore[arg-type]
                    self.model_box.configure(values=models)
                    if models: self.model.set(models[0])
                    self.status.set(f"설치된 로컬 모델 {len(models)}개를 찾았습니다.")
                elif kind == "monitor_next" and self.monitoring: self.after(10_000, self._monitor_tick)
        except queue.Empty:
            pass
        self.after(150, self._drain_events)


def main() -> None:
    FlowGuardApp().mainloop()


if __name__ == "__main__":
    main()
