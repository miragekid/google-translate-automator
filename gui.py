#!/usr/bin/env python3
"""
Google Translate Automator - Modern Desktop GUI (PyQt6)
Aplikasi desktop modern untuk menerjemahkan manga, komik, dan dokumen
secara otomatis dengan multi-tab Playwright, Smart Diff, dan deteksi hasil palsu.
"""

import os
import sys
import time
import asyncio
import threading
import shutil
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QProgressBar, QCheckBox, QFileDialog, QMessageBox, QHeaderView,
    QFrame, QTextEdit, QSpinBox, QDoubleSpinBox, QSlider, QTabWidget,
    QSplitter, QDialog, QListWidget, QListWidgetItem
)

# Import logic dari main.py
try:
    import main
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import main


# ── Modern Styling QSS (Dark Obsidian Theme) ──────────────────────────────────
QSS_STYLE = """
QMainWindow, QWidget#centralWidget {
    background-color: #0b0f19;
    color: #f1f5f9;
    font-family: "Segoe UI", -apple-system, Roboto, Helvetica, Arial, sans-serif;
}

QScrollArea {
    background-color: #0b0f19;
    border: none;
}

QFrame#cardFrame {
    background-color: #151c2e;
    border: 1px solid rgba(99, 102, 241, 0.22);
    border-radius: 12px;
}

QFrame#headerCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e1b4b, stop:1 #312e81);
    border: 1px solid rgba(129, 140, 248, 0.35);
    border-radius: 12px;
}

QFrame#statCardGreen {
    background-color: #0f241d;
    border: 1px solid rgba(16, 185, 129, 0.4);
    border-radius: 10px;
}

QFrame#statCardRed {
    background-color: #2a1215;
    border: 1px solid rgba(239, 68, 68, 0.4);
    border-radius: 10px;
}

QFrame#statCardYellow {
    background-color: #2a200f;
    border: 1px solid rgba(245, 158, 11, 0.4);
    border-radius: 10px;
}

QFrame#statCardBlue {
    background-color: #131d36;
    border: 1px solid rgba(99, 102, 241, 0.4);
    border-radius: 10px;
}

QLabel#appTitle {
    font-size: 19px;
    font-weight: 700;
    color: #ffffff;
}

QLabel#appSubtitle {
    font-size: 12px;
    color: #a5b4fc;
}

QLabel#sectionTitle {
    font-size: 13px;
    font-weight: 700;
    color: #e2e8f0;
}

QLabel#statValue {
    font-size: 24px;
    font-weight: 800;
}

QLabel#statLabel {
    font-size: 11px;
    color: #94a3b8;
    font-weight: 600;
}

QLineEdit {
    background-color: #0f172a;
    border: 1.5px solid rgba(148, 163, 184, 0.3);
    border-radius: 8px;
    padding: 6px 12px;
    color: #ffffff;
    font-size: 12px;
    selection-background-color: #6366f1;
}

QLineEdit:focus {
    border: 1.5px solid #6366f1;
}

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
    color: #ffffff;
    font-weight: 600;
    font-size: 12px;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #818cf8);
}

QPushButton:pressed {
    background-color: #3730a3;
}

QPushButton:disabled {
    background-color: #1e293b;
    color: #64748b;
}

QPushButton#btnPrimary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
    font-size: 13px;
    font-weight: 700;
    padding: 10px 20px;
}

QPushButton#btnPrimary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #34d399);
}

QPushButton#btnWarning {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #f59e0b);
    font-size: 13px;
    font-weight: 700;
    padding: 10px 18px;
}

QPushButton#btnWarning:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #fbbf24);
}

QPushButton#btnDanger {
    background: #ef4444;
    font-size: 13px;
    font-weight: 700;
    padding: 10px 18px;
}

QPushButton#btnDanger:hover {
    background: #dc2626;
}

QPushButton#btnSecondary {
    background: #1e293b;
    border: 1px solid rgba(148, 163, 184, 0.25);
    color: #cbd5e1;
    font-size: 11px;
    padding: 6px 12px;
}

QPushButton#btnSecondary:hover {
    background: #334155;
    color: #ffffff;
    border-color: #94a3b8;
}

QTableWidget {
    background-color: #0f172a;
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 8px;
    gridline-color: rgba(148, 163, 184, 0.1);
    color: #e2e8f0;
    font-size: 12px;
}

QTableWidget::item {
    padding: 6px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}

QTableWidget::item:selected {
    background-color: rgba(99, 102, 241, 0.3);
    color: #ffffff;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #94a3b8;
    padding: 6px;
    font-weight: 700;
    font-size: 11px;
    border: none;
    border-bottom: 1.5px solid rgba(99, 102, 241, 0.4);
}

QTabWidget::pane {
    border: 1px solid rgba(99, 102, 241, 0.2);
    background-color: #151c2e;
    border-radius: 8px;
}

QTabBar::tab {
    background: #0f172a;
    color: #94a3b8;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: #151c2e;
    color: #ffffff;
    border-bottom: 2px solid #6366f1;
}

QProgressBar {
    background-color: #0f172a;
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 6px;
    text-align: center;
    color: #ffffff;
    font-weight: 700;
    font-size: 11px;
    min-height: 20px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
    border-radius: 5px;
}

QTextEdit#logConsole {
    background-color: #070a12;
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 8px;
    color: #e2e8f0;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    padding: 8px;
}

QCheckBox {
    color: #e2e8f0;
    font-size: 12px;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1.5px solid rgba(148, 163, 184, 0.4);
    background-color: #0f172a;
}

QCheckBox::indicator:checked {
    background-color: #6366f1;
    border-color: #6366f1;
}
"""


# ── Worker Thread untuk Eksekusi Playwright Asinkron ─────────────────────────
class TranslationWorker(QThread):
    log_signal      = pyqtSignal(str, str)         # message, level (info, success, warn, error)
    progress_signal = pyqtSignal(int, int, str, float) # current, total, filename, percent
    file_status_sig = pyqtSignal(str, str, str)     # rel_path, status, info
    finished_signal = pyqtSignal(bool, str)        # success, summary_text

    def __init__(self, mode: str, files: list, source_dir: str, num_tabs: int, tab_delay: float, headless: bool):
        super().__init__()
        self.mode       = mode         # 'all', 'missing', 'fake'
        self.files      = files
        self.source_dir = source_dir
        self.num_tabs   = num_tabs
        self.tab_delay  = tab_delay
        self.headless   = headless
        self.is_aborted = False

    def abort(self):
        self.is_aborted = True
        main.abort_flag.set()

    def run(self):
        main.abort_flag.clear()
        main.NUM_TABS  = self.num_tabs
        main.TAB_DELAY = self.tab_delay
        main.HEADLESS  = self.headless

        total = len(self.files)
        self.log_signal.emit(f"🚀 Memulai batch terjemahan: {total} file (Tab: {self.num_tabs}, Jeda: {self.tab_delay}s, Headless: {self.headless})", "info")

        try:
            asyncio.run(self._run_async(total))
        except Exception as e:
            self.log_signal.emit(f"❌ Error fatal pada worker: {e}", "error")
            self.finished_signal.emit(False, str(e))

    async def _run_async(self, total: int):
        from playwright.async_api import async_playwright

        success_files = []
        failed_files  = []

        # Bersihkan Edge background process lama
        os.system('wmic process where "name=\'msedge.exe\' and commandline like \'%edge_profile%\'" call terminate >nul 2>&1')
        await asyncio.sleep(1)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                channel="msedge",
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=1920,1080",
                    "--no-first-run",
                    "--no-default-browser-check"
                ]
            )

            sem = asyncio.Semaphore(self.num_tabs)
            lock = asyncio.Lock()
            start_lock = asyncio.Lock()
            last_start_time = 0.0
            completed_count = 0

            class DummyProgress:
                def __init__(self, log_signal, filename):
                    self.log_signal = log_signal
                    self.filename   = filename

                def update(self, task_id=0, status_file=None, **kwargs):
                    if status_file:
                        clean_text = status_file
                        for tag in ["[blue]", "[/blue]", "[cyan]", "[/cyan]", "[yellow]", "[/yellow]", "[red]", "[/red]", "[green]", "[/green]", "[magenta]", "[/magenta]", "[dim]", "[/dim]", "[bold]", "[/bold]"]:
                            clean_text = clean_text.replace(tag, "")
                        self.log_signal.emit(f"[{self.filename}] {clean_text}", "info")

                def advance(self, task_id=0, step=1):
                    pass

            async def process_one(fp: str):
                nonlocal last_start_time, completed_count
                if self.is_aborted or main.abort_flag.is_set():
                    return

                rel = os.path.relpath(fp, self.source_dir)
                filename = os.path.basename(fp)

                async with sem:
                    if self.is_aborted or main.abort_flag.is_set():
                        return

                    # Jeda antar tab saat mulai agar tidak bersamaan
                    async with start_lock:
                        if self.is_aborted or main.abort_flag.is_set():
                            return
                        now = time.monotonic()
                        elapsed = now - last_start_time
                        if elapsed < self.tab_delay:
                            await asyncio.sleep(self.tab_delay - elapsed)
                        last_start_time = time.monotonic()

                    self.file_status_sig.emit(rel, "Memproses", "-")

                    # Jalankan process_file asli dari main.py dengan DummyProgress lengkap
                    dummy_p = DummyProgress(self.log_signal, filename)
                    res = False
                    try:
                        res = await main.process_file(browser, fp, self.source_dir, dummy_p, 0, lock, failed_files, success_files)
                    except Exception as err:
                        self.log_signal.emit(f"⚠️ Error memproses {filename}: {err}", "warn")
                        res = False

                    async with lock:
                        completed_count += 1
                        pct = (completed_count / total) * 100.0 if total > 0 else 100.0
                        self.progress_signal.emit(completed_count, total, filename, pct)

                    if res:
                        self.file_status_sig.emit(rel, "Selesai", "Sukses")
                        self.log_signal.emit(f"✅ Selesai ({completed_count}/{total}): {filename}", "success")
                    else:
                        self.file_status_sig.emit(rel, "Gagal", "Skip/Error")
                        self.log_signal.emit(f"❌ Gagal/Skip: {filename}", "error")

            tasks = [asyncio.create_task(process_one(f)) for f in self.files]

            while tasks:
                active = [t for t in tasks if not t.done()]
                tasks = active
                if self.is_aborted or main.abort_flag.is_set():
                    for t in tasks:
                        t.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    break
                if tasks:
                    await asyncio.sleep(0.3)

            await browser.close()

        if self.is_aborted:
            self.log_signal.emit("⏹️ Proses translasi dihentikan oleh pengguna.", "warn")
            self.finished_signal.emit(False, "Proses dibatalkan.")
        else:
            summary = f"Selesai! Berhasil: {len(success_files)} file | Gagal: {len(failed_files)} file"
            self.log_signal.emit(f"🎉 {summary}", "success")
            self.finished_signal.emit(True, summary)


# ── Dialog Import dari Pawchive ───────────────────────────────────────────────
class PawchiveImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Chapter dari Pawchive Downloader")
        self.resize(650, 420)
        self.setStyleSheet(QSS_STYLE)

        self.pawchive_dir = Path(r"C:\Users\Miragekids\Documents\pawchive-image-downloader-extension\downloads")
        self.target_mentah = Path(main.DIR_MENTAH)

        layout = QVBoxLayout(self)

        lbl_desc = QLabel("Pilih folder hasil download Pawchive yang ingin disalin ke folder <b>mentah</b>:")
        lbl_desc.setObjectName("sectionTitle")
        layout.addWidget(lbl_desc)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("background-color: #0f172a; border-radius: 8px; color: #ffffff;")
        layout.addWidget(self.list_widget)

        self.load_pawchive_folders()

        btn_layout = QHBoxLayout()
        btn_copy = QPushButton("📂 Salin Folder Terpilih ke Mentah")
        btn_copy.setObjectName("btnPrimary")
        btn_copy.clicked.connect(self.do_copy)

        btn_close = QPushButton("Tutup")
        btn_close.setObjectName("btnSecondary")
        btn_close.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        btn_layout.addWidget(btn_copy)
        layout.addLayout(btn_layout)

    def load_pawchive_folders(self):
        self.list_widget.clear()
        if not self.pawchive_dir.exists():
            item = QListWidgetItem("Direktori pawchive downloads tidak ditemukan.")
            self.list_widget.addItem(item)
            return

        for d in sorted(self.pawchive_dir.iterdir()):
            if d.is_dir():
                files = [f for f in d.glob("*.*") if f.suffix.lower() in main.IMAGE_EXTENSIONS]
                item_text = f"📁 {d.name} ({len(files)} gambar)"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, str(d))
                self.list_widget.addItem(item)

    def do_copy(self):
        selected = self.list_widget.currentItem()
        if not selected:
            QMessageBox.warning(self, "Pilih Folder", "Silakan pilih salah satu folder komik terlebih dahulu.")
            return

        src_dir = Path(selected.data(Qt.ItemDataRole.UserRole))
        if not src_dir.exists():
            return

        # Sederhanakan nama folder untuk mentah
        folder_name = src_dir.name
        # Jika nama ada yodomu - Aoi... ambil bagian penting
        if "Aoi" in folder_name:
            folder_name = "Aoi"

        dst_dir = self.target_mentah / folder_name
        dst_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for f in src_dir.glob("*.*"):
            if f.suffix.lower() in main.IMAGE_EXTENSIONS:
                shutil.copy2(f, dst_dir / f.name)
                count += 1

        QMessageBox.information(
            self, "Sukses Import",
            f"Berhasil menyalin {count} gambar dari:\n'{src_dir.name}'\nke:\n'{dst_dir}'"
        )
        self.accept()


# ── Jendela Utama GUI (MainWindow) ───────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Google Translate Automator - Modern Desktop GUI")
        self.resize(1150, 800)
        self.setStyleSheet(QSS_STYLE)

        self.worker = None
        self.cached_translated = []
        self.cached_missing    = []
        self.cached_fake       = []

        self.init_ui()
        self.refresh_scan()

    def init_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # ── 1. Header Card ───────────────────────────────────────────────────
        header = QFrame()
        header.setObjectName("headerCard")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 12, 16, 12)

        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        lbl_title = QLabel("Google Translate Automator")
        lbl_title.setObjectName("appTitle")
        lbl_sub = QLabel("Automated Manga, Comic & Document Translator | Smart Diff & Fake Detection")
        lbl_sub.setObjectName("appSubtitle")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)
        h_layout.addLayout(v_title)

        h_layout.addStretch()

        btn_import = QPushButton("📂 Import dari Pawchive")
        btn_import.setObjectName("btnSecondary")
        btn_import.clicked.connect(self.open_pawchive_import)
        h_layout.addWidget(btn_import)

        btn_rescan = QPushButton("🔄 Refresh Scan")
        btn_rescan.setObjectName("btnSecondary")
        btn_rescan.clicked.connect(self.refresh_scan)
        h_layout.addWidget(btn_rescan)

        root_layout.addWidget(header)

        # ── 2. Folder Directories ────────────────────────────────────────────
        folder_card = QFrame()
        folder_card.setObjectName("cardFrame")
        f_layout = QVBoxLayout(folder_card)
        f_layout.setContentsMargins(14, 10, 14, 10)
        f_layout.setSpacing(8)

        # Row Mentah
        row_m = QHBoxLayout()
        lbl_m = QLabel("Folder Mentah:")
        lbl_m.setFixedWidth(90)
        self.txt_mentah = QLineEdit(os.path.abspath(main.DIR_MENTAH))
        btn_browse_m = QPushButton("Pilih...")
        btn_browse_m.setObjectName("btnSecondary")
        btn_browse_m.clicked.connect(self.browse_mentah)
        btn_open_m = QPushButton("Buka")
        btn_open_m.setObjectName("btnSecondary")
        btn_open_m.clicked.connect(lambda: os.startfile(self.txt_mentah.text()) if os.path.exists(self.txt_mentah.text()) else None)

        row_m.addWidget(lbl_m)
        row_m.addWidget(self.txt_mentah)
        row_m.addWidget(btn_browse_m)
        row_m.addWidget(btn_open_m)
        f_layout.addLayout(row_m)

        # Row Hasil
        row_h = QHBoxLayout()
        lbl_h = QLabel("Folder Hasil:")
        lbl_h.setFixedWidth(90)
        self.txt_hasil = QLineEdit(os.path.abspath(main.DIR_HASIL))
        btn_browse_h = QPushButton("Pilih...")
        btn_browse_h.setObjectName("btnSecondary")
        btn_browse_h.clicked.connect(self.browse_hasil)
        btn_open_h = QPushButton("Buka")
        btn_open_h.setObjectName("btnSecondary")
        btn_open_h.clicked.connect(lambda: os.startfile(self.txt_hasil.text()) if os.path.exists(self.txt_hasil.text()) else None)

        row_h.addWidget(lbl_h)
        row_h.addWidget(self.txt_hasil)
        row_h.addWidget(btn_browse_h)
        row_h.addWidget(btn_open_h)
        f_layout.addLayout(row_h)

        root_layout.addWidget(folder_card)

        # ── 3. Metric Dashboard Cards ────────────────────────────────────────
        stat_layout = QHBoxLayout()
        stat_layout.setSpacing(10)

        # Total Card
        self.card_total = QFrame()
        self.card_total.setObjectName("statCardBlue")
        v_tot = QVBoxLayout(self.card_total)
        self.val_total = QLabel("0")
        self.val_total.setObjectName("statValue")
        self.val_total.setStyleSheet("color: #818cf8;")
        lbl_tot = QLabel("TOTAL FILE")
        lbl_tot.setObjectName("statLabel")
        v_tot.addWidget(self.val_total)
        v_tot.addWidget(lbl_tot)
        stat_layout.addWidget(self.card_total)

        # Selesai Card
        self.card_ok = QFrame()
        self.card_ok.setObjectName("statCardGreen")
        v_ok = QVBoxLayout(self.card_ok)
        self.val_ok = QLabel("0")
        self.val_ok.setObjectName("statValue")
        self.val_ok.setStyleSheet("color: #10b981;")
        lbl_ok = QLabel("SUDAH DITERJEMAHKAN")
        lbl_ok.setObjectName("statLabel")
        v_ok.addWidget(self.val_ok)
        v_ok.addWidget(lbl_ok)
        stat_layout.addWidget(self.card_ok)

        # Missing Card
        self.card_miss = QFrame()
        self.card_miss.setObjectName("statCardRed")
        v_miss = QVBoxLayout(self.card_miss)
        self.val_miss = QLabel("0")
        self.val_miss.setObjectName("statValue")
        self.val_miss.setStyleSheet("color: #ef4444;")
        lbl_miss = QLabel("BELUM ADA HASIL (MISSING)")
        lbl_miss.setObjectName("statLabel")
        v_miss.addWidget(self.val_miss)
        v_miss.addWidget(lbl_miss)
        stat_layout.addWidget(self.card_miss)

        # Fake Card
        self.card_fake = QFrame()
        self.card_fake.setObjectName("statCardYellow")
        v_fk = QVBoxLayout(self.card_fake)
        self.val_fake = QLabel("0")
        self.val_fake.setObjectName("statValue")
        self.val_fake.setStyleSheet("color: #f59e0b;")
        lbl_fk = QLabel("HASIL PALSU (FILE ASLI)")
        lbl_fk.setObjectName("statLabel")
        v_fk.addWidget(self.val_fake)
        v_fk.addWidget(lbl_fk)
        stat_layout.addWidget(self.card_fake)

        root_layout.addLayout(stat_layout)

        # ── 4. Main Content: Table & Controls (Splitter) ─────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(4)

        # Tab Widget Table
        self.tabs = QTabWidget()
        self.table_all     = self.create_file_table()
        self.table_missing = self.create_file_table()
        self.table_fake    = self.create_file_table()
        self.table_done    = self.create_file_table()

        self.tabs.addTab(self.table_all, "📋 Semua File")
        self.tabs.addTab(self.table_missing, "🔴 Belum Ada (Missing)")
        self.tabs.addTab(self.table_fake, "🟡 File Palsu (Fake)")
        self.tabs.addTab(self.table_done, "🟢 Sudah Selesai")
        splitter.addWidget(self.tabs)

        # Console Log Widget
        console_widget = QWidget()
        v_cons = QVBoxLayout(console_widget)
        v_cons.setContentsMargins(0, 4, 0, 0)
        lbl_cons = QLabel("Log Terminal & Status:")
        lbl_cons.setObjectName("sectionTitle")
        self.log_console = QTextEdit()
        self.log_console.setObjectName("logConsole")
        self.log_console.setReadOnly(True)
        v_cons.addWidget(lbl_cons)
        v_cons.addWidget(self.log_console)
        splitter.addWidget(console_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root_layout.addWidget(splitter)

        # ── 5. Settings Bar ──────────────────────────────────────────────────
        settings_card = QFrame()
        settings_card.setObjectName("cardFrame")
        s_layout = QHBoxLayout(settings_card)
        s_layout.setContentsMargins(12, 8, 12, 8)
        s_layout.setSpacing(16)

        # Tabs Paralel
        s_layout.addWidget(QLabel("Tab Paralel:"))
        self.spin_tabs = QSpinBox()
        self.spin_tabs.setRange(1, 8)
        self.spin_tabs.setValue(main.NUM_TABS)
        self.spin_tabs.setFixedWidth(50)
        s_layout.addWidget(self.spin_tabs)

        # Jeda Antar Tab
        s_layout.addWidget(QLabel("Jeda Tab (dtk):"))
        self.spin_delay = QDoubleSpinBox()
        self.spin_delay.setRange(0.5, 10.0)
        self.spin_delay.setSingleStep(0.5)
        self.spin_delay.setValue(main.TAB_DELAY)
        self.spin_delay.setFixedWidth(60)
        s_layout.addWidget(self.spin_delay)

        # Headless Checkbox
        self.chk_headless = QCheckBox("Headless (Latar Belakang)")
        self.chk_headless.setChecked(main.HEADLESS)
        s_layout.addWidget(self.chk_headless)

        # Auto Optimize Checkbox
        self.chk_optimize = QCheckBox("Auto-Optimasi Gambar (>5MB/PNG)")
        self.chk_optimize.setChecked(True)
        s_layout.addWidget(self.chk_optimize)

        s_layout.addStretch()
        root_layout.addWidget(settings_card)

        # ── 6. Progress Bar ──────────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Siap - 0%")
        root_layout.addWidget(self.progress_bar)

        # ── 7. Action Buttons Bar ────────────────────────────────────────────
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)

        self.btn_run_all = QPushButton("🚀 Mulai Translate Semua")
        self.btn_run_all.setObjectName("btnPrimary")
        self.btn_run_all.clicked.connect(self.start_translate_all)

        self.btn_run_missing = QPushButton("⚡ Translate Hanya Missing")
        self.btn_run_missing.setObjectName("btnWarning")
        self.btn_run_missing.clicked.connect(self.start_translate_missing)

        self.btn_restore_fake = QPushButton("🔄 Pulihkan & Translate Fake")
        self.btn_restore_fake.setObjectName("btnSecondary")
        self.btn_restore_fake.clicked.connect(self.start_restore_fake)

        self.btn_stop = QPushButton("⏹️ Stop / Batal")
        self.btn_stop.setObjectName("btnDanger")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_translation)

        action_layout.addWidget(self.btn_run_all)
        action_layout.addWidget(self.btn_run_missing)
        action_layout.addWidget(self.btn_restore_fake)
        action_layout.addStretch()
        action_layout.addWidget(self.btn_stop)

        root_layout.addLayout(action_layout)

    def create_file_table(self) -> QTableWidget:
        tbl = QTableWidget()
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels(["No", "Status", "Nama File", "Subfolder", "Ukuran"])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        return tbl

    def append_log(self, text: str, level: str = "info"):
        timestamp = time.strftime("%H:%M:%S")
        color = "#e2e8f0"
        if level == "success":
            color = "#10b981"
        elif level == "warn":
            color = "#f59e0b"
        elif level == "error":
            color = "#ef4444"

        html = f"<span style='color: #64748b;'>[{timestamp}]</span> <span style='color: {color};'>{text}</span>"
        self.log_console.append(html)
        # Scroll to bottom
        sb = self.log_console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def refresh_scan(self):
        main.DIR_MENTAH = self.txt_mentah.text().strip()
        main.DIR_HASIL  = self.txt_hasil.text().strip()

        translated, missing, fake = main.build_comparison_table()
        self.cached_translated = translated
        self.cached_missing    = missing
        self.cached_fake       = fake

        total = len(translated) + len(missing) + len(fake)
        self.val_total.setText(str(total))
        self.val_ok.setText(str(len(translated)))
        self.val_miss.setText(str(len(missing)))
        self.val_fake.setText(str(len(fake)))

        # Populate tables
        self.populate_tables(translated, missing, fake)
        self.append_log(f"Scan diperbarui: {len(translated)} Selesai, {len(missing)} Missing, {len(fake)} Fake/Mentah", "info")

    def populate_tables(self, translated, missing, fake):
        for tbl in [self.table_all, self.table_missing, self.table_fake, self.table_done]:
            tbl.setRowCount(0)

        # 1. Missing
        for idx, (fp, rel) in enumerate(missing, 1):
            row = self.table_missing.rowCount()
            self.table_missing.insertRow(row)
            self._fill_table_row(self.table_missing, row, idx, "Belum Ada", Path(rel).name, str(Path(rel).parent), fp)

            row_all = self.table_all.rowCount()
            self.table_all.insertRow(row_all)
            self._fill_table_row(self.table_all, row_all, row_all+1, "Belum Ada", Path(rel).name, str(Path(rel).parent), fp)

        # 2. Fake
        for idx, (fp, rel, hp) in enumerate(fake, 1):
            row = self.table_fake.rowCount()
            self.table_fake.insertRow(row)
            self._fill_table_row(self.table_fake, row, idx, "File Asli (Fake)", Path(rel).name, str(Path(rel).parent), fp)

            row_all = self.table_all.rowCount()
            self.table_all.insertRow(row_all)
            self._fill_table_row(self.table_all, row_all, row_all+1, "File Asli (Fake)", Path(rel).name, str(Path(rel).parent), fp)

        # 3. Translated
        for idx, (src_rel, dst_rel) in enumerate(translated, 1):
            row = self.table_done.rowCount()
            self.table_done.insertRow(row)
            src_p = Path(main.DIR_MENTAH) / src_rel
            self._fill_table_row(self.table_done, row, idx, "Selesai", Path(src_rel).name, str(Path(src_rel).parent), str(src_p))

            row_all = self.table_all.rowCount()
            self.table_all.insertRow(row_all)
            self._fill_table_row(self.table_all, row_all, row_all+1, "Selesai", Path(src_rel).name, str(Path(src_rel).parent), str(src_p))

    def _fill_table_row(self, tbl: QTableWidget, row: int, no: int, status: str, filename: str, subfolder: str, fullpath: str):
        size_str = "-"
        if os.path.exists(fullpath):
            sz = os.path.getsize(fullpath) / (1024 * 1024)
            size_str = f"{sz:.2f} MB"

        tbl.setItem(row, 0, QTableWidgetItem(str(no)))

        item_status = QTableWidgetItem(status)
        if status == "Selesai":
            item_status.setForeground(QtGui.QColor("#10b981"))
        elif status == "Belum Ada":
            item_status.setForeground(QtGui.QColor("#ef4444"))
        elif "Fake" in status or "Asli" in status:
            item_status.setForeground(QtGui.QColor("#f59e0b"))
        tbl.setItem(row, 1, item_status)

        tbl.setItem(row, 2, QTableWidgetItem(filename))
        tbl.setItem(row, 3, QTableWidgetItem(subfolder if subfolder != "." else "[root]"))
        tbl.setItem(row, 4, QTableWidgetItem(size_str))

    def browse_mentah(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih Folder Mentah", self.txt_mentah.text())
        if d:
            self.txt_mentah.setText(d)
            self.refresh_scan()

    def browse_hasil(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih Folder Hasil", self.txt_hasil.text())
        if d:
            self.txt_hasil.setText(d)
            self.refresh_scan()

    def open_pawchive_import(self):
        dlg = PawchiveImportDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_scan()

    # ── Action Handlers ──────────────────────────────────────────────────────
    def start_translate_all(self):
        self.refresh_scan()
        all_mentah = [
            str(fp) for fp in Path(self.txt_mentah.text()).rglob('*')
            if fp.is_file() and 'selesai' not in fp.parts and fp.suffix.lower() in (main.IMAGE_EXTENSIONS | main.DOC_EXTENSIONS)
        ]
        if not all_mentah:
            QMessageBox.information(self, "Info", "Tidak ada file di folder mentah yang perlu diproses.")
            return

        self._launch_worker("all", all_mentah, self.txt_mentah.text())

    def start_translate_missing(self):
        self.refresh_scan()
        if not self.cached_missing:
            QMessageBox.information(self, "Info", "Semua file sudah ada hasilnya di folder hasil.")
            return

        files = [fp for fp, _ in self.cached_missing]
        self._launch_worker("missing", files, self.txt_mentah.text())

    def start_restore_fake(self):
        self.refresh_scan()
        if not self.cached_fake:
            QMessageBox.information(self, "Info", "Tidak ditemukan file palsu / hasil gagal.")
            return

        reply = QMessageBox.question(
            self, "Konfirmasi Restore",
            f"Ditemukan {len(self.cached_fake)} file palsu di folder hasil.\n"
            "File palsu akan dihapus dari 'hasil' dan file asli akan dikembalikan ke 'mentah' untuk ditranslate ulang.\nLanjutkan?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            restored = main.restore_fake_results(self.cached_fake)
            self.append_log(f"🔄 Berhasil restore {restored} file ke folder mentah.", "success")
            self.refresh_scan()

            files = [fp for fp, _, _ in self.cached_fake if os.path.exists(fp)]
            for _, rel, _ in self.cached_fake:
                cand = str(Path(self.txt_mentah.text()) / rel)
                if os.path.exists(cand) and cand not in files:
                    files.append(cand)

            if files:
                self._launch_worker("fake", files, self.txt_mentah.text())

    def _launch_worker(self, mode: str, files: list, source_dir: str):
        self.btn_run_all.setEnabled(False)
        self.btn_run_missing.setEnabled(False)
        self.btn_restore_fake.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"Memproses {len(files)} file... 0%")

        self.worker = TranslationWorker(
            mode=mode,
            files=files,
            source_dir=source_dir,
            num_tabs=self.spin_tabs.value(),
            tab_delay=self.spin_delay.value(),
            headless=self.chk_headless.isChecked()
        )
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.on_worker_progress)
        self.worker.file_status_sig.connect(self.on_file_status)
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_progress(self, current: int, total: int, filename: str, pct: float):
        self.progress_bar.setValue(int(pct))
        self.progress_bar.setFormat(f"[{current}/{total}] {filename} ({pct:.1f}%)")

    def on_file_status(self, rel: str, status: str, info: str):
        pass

    def on_worker_finished(self, success: bool, summary: str):
        self.btn_run_all.setEnabled(True)
        self.btn_run_missing.setEnabled(True)
        self.btn_restore_fake.setEnabled(True)
        self.btn_stop.setEnabled(False)

        self.progress_bar.setValue(100 if success else 0)
        self.progress_bar.setFormat(summary)
        self.refresh_scan()

    def stop_translation(self):
        if self.worker and self.worker.isRunning():
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("Menghentikan...")
            self.worker.abort()


def main_gui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main_gui()
