import os
import sys

# Tingkatkan batas memori Node.js Playwright driver ke 4GB untuk mencegah crash OOM V8
os.environ["NODE_OPTIONS"] = "--max-old-space-size=4096"

import time
import shutil
import re
import asyncio
import threading
import msvcrt
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError
import subprocess

# Set utf-8 output encoding for terminal on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


try:
    from rich.console import Console
    from rich.progress import (
        Progress,
        SpinnerColumn,
        BarColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn
    )
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Menginstall modul pendukung 'rich'...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])
    from rich.console import Console
    from rich.progress import (
        Progress,
        SpinnerColumn,
        BarColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn
    )
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

# ── Konfigurasi ───────────────────────────────────────────────────────────────
DIR_MENTAH   = "mentah"
DIR_HASIL    = "hasil"
DIR_SELESAI  = "mentah/selesai"
NUM_TABS     = 3           # Jumlah tab paralel (3 lebih stabil untuk mencegah memory crash pada file besar)
MAX_RETRIES  = 3           # Maksimal percobaan per file
TRANSLATE_TIMEOUT = 60     # Timeout tunggu terjemahan dalam detik (dinaikkan untuk file besar)
HEADLESS     = True        # True = browser di background (hanya CLI yang tampil)
TAB_DELAY    = 3.0         # Jeda waktu (detik) antar tab saat mulai agar tidak bersamaan


# Toleransi ukuran file untuk mendeteksi hasil "palsu" (Google Translate return file asli)
# Jika ukuran file hasil >= X% ukuran asli, dianggap belum diterjemahkan
FAKE_TRANSLATE_RATIO = 0.90  # 90% → jika hasil >= 90% ukuran asli = dianggap gagal terjemah

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
DOC_EXTENSIONS   = {'.pdf', '.docx', '.pptx', '.xlsx'}

console = Console()

# ── Abort flag ────────────────────────────────────────────────────────────────
abort_flag = threading.Event()

def _listen_abort():
    """Thread background: menunggu tombol Q untuk membatalkan proses."""
    while not abort_flag.is_set():
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key.lower() == b'q':
                abort_flag.set()
                console.print("\n[bold red][ABORT][/bold red] Pembatalan diminta! Menghentikan semua proses...", style="red")
                break
        time.sleep(0.05)
# ─────────────────────────────────────────────────────────────────────────────


def _stem_normalize(filename: str) -> str:
    """
    Normalisasi nama file agar bisa dibandingkan antara mentah & hasil.
    Google Translate kadang menambahkan suffix seperti '_translated' atau
    mengubah ekstensi. Kita ambil stem (nama tanpa ekstensi) saja.
    """
    return Path(filename).stem.lower().strip()


def _is_fake_translation(src_path: Path, hasil_path: Path) -> bool:
    """
    Deteksi apakah file di 'hasil' adalah file palsu (tidak benar-benar diterjemahkan).
    File dianggap palsu jika ukurannya >= FAKE_TRANSLATE_RATIO dari ukuran asli.
    Google Translate yang berhasil akan menghasilkan file yang jauh lebih kecil (kompresi WEBP/PNG).
    """
    if not src_path.exists() or not hasil_path.exists():
        return False
    src_size  = src_path.stat().st_size
    hasil_size = hasil_path.stat().st_size
    if src_size == 0:
        return False
    ratio = hasil_size / src_size
    return ratio >= FAKE_TRANSLATE_RATIO


def build_comparison_table() -> tuple:
    """
    Bangun data perbandingan antara mentah dan hasil.
    Juga memeriksa mentah/selesai/ untuk mendeteksi file yang sudah dipindah
    tapi hasilnya palsu (ukuran sama dengan asli).

    Return: (translated_list, missing_list, fake_list)
    - translated_list: list of (rel, rel_hasil) yang sudah ada hasilnya & valid
    - missing_list   : list of (src_path, rel) yang tidak ada hasilnya sama sekali
    - fake_list      : list of (src_path, rel, hasil_path) yang hasilnya palsu
    """
    mentah_root  = Path(DIR_MENTAH)
    selesai_root = Path(DIR_SELESAI)
    hasil_root   = Path(DIR_HASIL)

    translated = []
    missing    = []
    fake       = []
    seen_rels  = set()  # hindari duplikat

    # Kumpulkan kandidat: dari mentah/ dan mentah/selesai/
    candidates = []

    for src_file in sorted(mentah_root.rglob('*')):
        if not src_file.is_file():
            continue
        if 'selesai' in src_file.parts:
            continue
        ext = src_file.suffix.lower()
        if ext not in IMAGE_EXTENSIONS and ext not in DOC_EXTENSIONS:
            continue
        rel = src_file.relative_to(mentah_root)
        candidates.append((src_file, rel))

    # Juga scan selesai/ untuk deteksi fake pada file yang sudah dipindah
    if selesai_root.exists():
        for src_file in sorted(selesai_root.rglob('*')):
            if not src_file.is_file():
                continue
            ext = src_file.suffix.lower()
            if ext not in IMAGE_EXTENSIONS and ext not in DOC_EXTENSIONS:
                continue
            rel = src_file.relative_to(selesai_root)
            if str(rel) not in seen_rels:
                candidates.append((src_file, rel))

    for src_file, rel in candidates:
        rel_key  = str(rel)
        if rel_key in seen_rels:
            continue
        seen_rels.add(rel_key)

        ext      = src_file.suffix.lower()
        rel_dir  = rel.parent
        src_stem = _stem_normalize(src_file.name)

        # Cari pasangan di hasil/
        target_dir = hasil_root / rel_dir
        found_path = None
        if target_dir.exists():
            for f in target_dir.iterdir():
                if f.is_file() and _stem_normalize(f.name) == src_stem:
                    found_path = f
                    break

        if found_path:
            if ext in IMAGE_EXTENSIONS and _is_fake_translation(src_file, found_path):
                fake.append((str(src_file), str(rel), str(found_path)))
            else:
                # Hanya masukkan sebagai "translated" jika sumber dari mentah aktif
                if 'selesai' not in src_file.parts:
                    translated.append((str(rel), str(found_path.relative_to(hasil_root))))
                # Jika dari selesai dan valid → sudah beres, tidak perlu ditampilkan
        else:
            # Tidak ada hasil sama sekali
            if 'selesai' not in src_file.parts:
                missing.append((str(src_file), str(rel)))
            # Dari selesai tapi tidak ada hasil → di-restore juga (restore_fake akan handle)

    return translated, missing, fake


def restore_fake_results(fake_list: list):
    """
    Hapus file palsu dari folder 'hasil' agar bisa di-translate ulang.
    File di 'mentah/selesai' dikembalikan ke 'mentah' supaya bisa diproses lagi.
    """
    mentah_root  = Path(DIR_MENTAH)
    selesai_root = Path(DIR_SELESAI)
    restored = 0

    for src_mentah, rel, hasil_path_str in fake_list:
        hasil_path = Path(hasil_path_str)

        # 1. Hapus file palsu dari hasil
        try:
            if hasil_path.exists():
                hasil_path.unlink()
        except Exception as e:
            console.print(f"[red]Gagal hapus hasil palsu {hasil_path.name}: {e}[/red]")
            continue

        # 2. Jika file asli sudah dipindah ke selesai, kembalikan ke mentah
        rel_path    = Path(rel)
        selesai_src = selesai_root / rel_path
        mentah_dst  = mentah_root / rel_path

        if selesai_src.exists() and not mentah_dst.exists():
            mentah_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(selesai_src), str(mentah_dst))
            restored += 1
        elif Path(src_mentah).exists():
            # File masih di mentah, tidak perlu dipindah
            restored += 1

    return restored


async def process_image_file(page, abs_path: str, rel_path: str, update_status) -> object:
    """
    Upload gambar ke Google Translate, tunggu respon OCR backend dan render canvas, lalu download.
    Mendukung file besar (5-12MB+) dengan timeout yang lebih panjang dan validasi hasil.
    """
    src_size = Path(abs_path).stat().st_size

    await page.goto("https://translate.google.com/?sl=auto&tl=en&op=images&hl=en", wait_until="domcontentloaded")

    file_input = page.locator('input[type="file"][accept*="image"]').first
    if await file_input.count() == 0:
        file_input = page.locator('input[type="file"]').last

    await file_input.wait_for(state="attached", timeout=10000)

    # Daftarkan listener OCR sebelum upload
    ocr_done_event = asyncio.Event()

    def on_response(r):
        if "batchexecute" in r.url and r.status == 200:
            ocr_done_event.set()

    page.on("response", on_response)

    try:
        await file_input.set_input_files(abs_path)
        update_status(f"[blue]Menerjemahkan:[/blue] {os.path.basename(rel_path)}")

        # Tunggu respon OCR — file besar butuh lebih lama
        # Skala timeout berdasarkan ukuran file: min 20s, max 60s
        ocr_timeout = max(20.0, min(60.0, src_size / (500 * 1024)))  # ~1s per 500KB
        try:
            await asyncio.wait_for(ocr_done_event.wait(), timeout=ocr_timeout)
        except asyncio.TimeoutError:
            pass

        # Jeda rendering canvas
        await asyncio.sleep(4.0)

        dl_btn = page.locator(
            'button[jsname="hRZeKc"], '
            'button:has-text("Download translation"), '
            'button[aria-label*="Download translation" i], '
            'button[aria-label*="Unduh terjemahan" i]'
        ).first

        # Poll berbasis waktu nyata (bukan hitungan iterasi)
        deadline = time.monotonic() + TRANSLATE_TIMEOUT
        while time.monotonic() < deadline:
            if abort_flag.is_set():
                break

            # Cek status terjemahan langsung di dalam DOM browser tanpa mentransfer string body besar via IPC
            try:
                is_translating = await page.evaluate(
                    "() => { const t = document.body ? (document.body.innerText || '') : ''; return t.includes('Translating') || t.includes('Menerjemahkan'); }"
                )
            except Exception:
                is_translating = False

            if not is_translating and await dl_btn.count() > 0:
                update_status(f"[cyan]Mengunduh:[/cyan] {os.path.basename(rel_path)}")
                try:
                    async with page.expect_download(timeout=30000) as dl_info:
                        await dl_btn.evaluate("b => b.click()")
                    dl = await dl_info.value

                    # ── Validasi: pastikan hasil download BUKAN file asli yang sama ──
                    # Simpan sementara ke temp path untuk cek ukurannya
                    dl_path_str = await dl.path()
                    if dl_path_str:
                        tmp_path = Path(dl_path_str)
                        if tmp_path.exists():
                            dl_size = tmp_path.stat().st_size
                            ratio   = dl_size / src_size if src_size > 0 else 0
                            if ratio >= FAKE_TRANSLATE_RATIO:
                                # Google return file asli = terjemahan tidak terjadi
                                update_status(f"[red]Gagal (file asli):[/red] {os.path.basename(rel_path)}")
                                try:
                                    await dl.delete()
                                except Exception:
                                    pass
                                return None

                    return dl
                except Exception:
                    pass

            await asyncio.sleep(0.8)

        return None
    finally:
        try:
            page.remove_listener("response", on_response)
        except Exception:
            pass


async def process_doc_file(page, abs_path: str, rel_path: str, update_status) -> object:
    """Upload dokumen ke Google Translate dan download hasilnya."""
    await page.goto("https://translate.google.com/?sl=auto&tl=en&op=docs&hl=en", wait_until="domcontentloaded")

    file_input = page.locator('input[type="file"][accept*="pdf"]').first
    if await file_input.count() == 0:
        file_input = page.locator('input[type="file"]').first

    await file_input.wait_for(state="attached", timeout=10000)
    await file_input.set_input_files(abs_path)
    update_status(f"[blue]Menerjemahkan dokumen:[/blue] {os.path.basename(rel_path)}")

    dl_btn = page.locator('button[jsname="hRZeKc"]:visible, button:has-text("Download translation"):visible, button:has-text("Download"):visible, button[aria-label*="Download" i]:visible, button[aria-label*="Unduh" i]:visible').first
    try:
        await dl_btn.wait_for(state="visible", timeout=TRANSLATE_TIMEOUT * 1000)
        update_status(f"[cyan]Mengunduh dokumen:[/cyan] {os.path.basename(rel_path)}")
        async with page.expect_download(timeout=15000) as dl:
            await dl_btn.click()
        return await dl.value
    except Exception:
        return None


async def process_file(browser, file_path: str, source_dir: str, progress: Progress, task_id,
                       lock: asyncio.Lock, failed_files: list, success_files: list) -> bool:
    """
    Proses satu file (gambar/dokumen/metadata) menggunakan context & tab bersih terisolasi per file.
    """
    filename = os.path.basename(file_path)
    rel_path = os.path.relpath(file_path, source_dir)
    rel_dir  = os.path.dirname(rel_path)
    ext      = Path(filename).suffix.lower()
    abs_path = os.path.abspath(file_path)

    def update_status(text: str):
        progress.update(task_id, status_file=text)

    # ── Handle file non-media (seperti ComicInfo.xml, metadata, txt) ────────────
    if ext not in IMAGE_EXTENSIONS and ext not in DOC_EXTENSIONS:
        if source_dir == DIR_MENTAH:
            target_hasil_dir   = os.path.join(DIR_HASIL, rel_dir)
            target_selesai_dir = os.path.join(DIR_SELESAI, rel_dir)
            Path(target_hasil_dir).mkdir(parents=True, exist_ok=True)
            Path(target_selesai_dir).mkdir(parents=True, exist_ok=True)

            shutil.copy2(file_path, os.path.join(target_hasil_dir, filename))
            shutil.move(file_path, os.path.join(target_selesai_dir, filename))

        async with lock:
            success_files.append(rel_path)
            progress.advance(task_id, 1)
        return True

    update_status(f"[yellow]Memproses:[/yellow] {filename}")

    downloaded = None
    success    = False

    try:
        for attempt in range(1, MAX_RETRIES + 1):
            if abort_flag.is_set():
                break

            if attempt > 1:
                update_status(f"[magenta]Coba lagi ({attempt}/{MAX_RETRIES}):[/magenta] {filename}")
                await asyncio.sleep(0.5)

            context = None
            page = None
            try:
                context = await browser.new_context(
                    accept_downloads=True,
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
                )
                page = await context.new_page()
                if ext in IMAGE_EXTENSIONS:
                    downloaded = await process_image_file(page, abs_path, rel_path, update_status)
                else:
                    downloaded = await process_doc_file(page, abs_path, rel_path, update_status)

                # Simpan hasil langsung saat context masih aktif
                if downloaded:
                    target_hasil_dir = os.path.join(DIR_HASIL, rel_dir)
                    Path(target_hasil_dir).mkdir(parents=True, exist_ok=True)

                    safe_filename   = downloaded.suggested_filename
                    final_save_path = os.path.join(target_hasil_dir, safe_filename)
                    await downloaded.save_as(final_save_path)
                    success = True
            except Exception:
                downloaded = None
            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass

            if success:
                break

        # ── Penanganan jika sukses atau gagal ──────────────────────────────────
        if success:
            # Jika sumber dari 'mentah', pindahkan ke 'selesai' dan bersihkan folder kosong
            if source_dir == DIR_MENTAH:
                target_selesai_dir = os.path.join(DIR_SELESAI, rel_dir)
                Path(target_selesai_dir).mkdir(parents=True, exist_ok=True)
                shutil.move(file_path, os.path.join(target_selesai_dir, filename))

                orig_dir = os.path.dirname(file_path)
                if orig_dir != DIR_MENTAH:
                    try:
                        os.rmdir(orig_dir)
                    except OSError:
                        pass

            async with lock:
                success_files.append(rel_path)
        else:
            async with lock:
                failed_files.append(file_path)

    except asyncio.CancelledError:
        raise
    except Exception:
        async with lock:
            failed_files.append(file_path)


    # Update progress bar
    async with lock:
        progress.advance(task_id, 1)

    return success


async def run_batch(browser, files_to_process: list, source_dir: str, failed_files: list, success_files: list, title: str = "Translating"):
    """Jalankan batch file secara paralel dengan Loading Bar yang bersih dan rapi."""
    total = len(files_to_process)
    tabs  = min(NUM_TABS, total)

    sem  = asyncio.Semaphore(tabs)
    lock = asyncio.Lock()
    start_lock = asyncio.Lock()
    last_start_time = 0.0

    with Progress(
        SpinnerColumn("dots", style="bold cyan"),
        TextColumn("[bold green]{task.description}"),
        BarColumn(bar_width=35, style="black", complete_style="bold green", finished_style="bold green"),
        TextColumn("[bold white]{task.completed}/{task.total}"),
        TextColumn("[bold yellow]({task.percentage:>3.0f}%)"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TextColumn("{task.fields[status_file]}"),
        console=console,
        transient=False,
    ) as progress:

        task_id = progress.add_task(
            description=f"{title}",
            total=total,
            status_file="[dim]Menyiapkan proses...[/dim]"
        )

        async def worker(file_path: str):
            nonlocal last_start_time
            if abort_flag.is_set():
                return
            async with sem:
                if abort_flag.is_set():
                    return
                # Beri jeda antar tab saat mulai agar tidak bersamaan membuka page & upload
                async with start_lock:
                    if abort_flag.is_set():
                        return
                    now = time.monotonic()
                    elapsed = now - last_start_time
                    if elapsed < TAB_DELAY:
                        await asyncio.sleep(TAB_DELAY - elapsed)
                    last_start_time = time.monotonic()

                await process_file(browser, file_path, source_dir, progress, task_id, lock, failed_files, success_files)

        tasks = [asyncio.create_task(worker(fp)) for fp in files_to_process]

        while tasks:
            active_tasks = [t for t in tasks if not t.done()]
            tasks = active_tasks

            if abort_flag.is_set():
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                break

            if tasks:
                await asyncio.sleep(0.2)


def show_diff_table(translated: list, missing: list, fake: list = None):
    """Tampilkan tabel perbandingan file mentah vs hasil, termasuk file palsu."""
    if fake is None:
        fake = []
    console.print()

    total_ok    = len(translated)
    total_miss  = len(missing)
    total_fake  = len(fake)
    total_all   = total_ok + total_miss + total_fake

    # Tabel ringkasan
    summary = Table(title="Ringkasan Perbandingan Mentah vs Hasil", border_style="cyan", show_header=True)
    summary.add_column("Status", style="bold", justify="center", no_wrap=True)
    summary.add_column("Jumlah", justify="center", style="bold white")
    summary.add_column("Keterangan", style="dim")

    summary.add_row(
        "[bold green]Sudah Diterjemahkan[/bold green]",
        f"[green]{total_ok}[/green]",
        "File valid, sudah ada hasilnya di folder 'hasil'"
    )
    summary.add_row(
        "[bold red]Belum Ada Hasilnya[/bold red]",
        f"[red]{total_miss}[/red]",
        "File tidak ada hasilnya sama sekali"
    )
    summary.add_row(
        "[bold yellow]Hasil Palsu (Gagal Download)[/bold yellow]",
        f"[yellow]{total_fake}[/yellow]",
        "Ada file di hasil tapi ukurannya sama = bukan hasil terjemahan"
    )
    summary.add_row(
        "[bold white]Total[/bold white]",
        f"[white]{total_all}[/white]",
        "Total file media di folder 'mentah'"
    )

    console.print(summary)

    # File belum ada hasilnya
    if missing:
        console.print()
        missing_table = Table(
            title=f"[bold red]{len(missing)} File Belum Ada Hasilnya[/bold red]",
            border_style="red",
            show_header=True
        )
        missing_table.add_column("No", justify="center", style="cyan", no_wrap=True)
        missing_table.add_column("File (nama)", style="white")
        missing_table.add_column("Subfolder", style="dim yellow")

        for idx, (fp, rel) in enumerate(missing, 1):
            folder = str(Path(rel).parent) if str(Path(rel).parent) != "." else "[root]"
            missing_table.add_row(str(idx), str(Path(rel).name), folder)

        console.print(missing_table)

    # File dengan hasil palsu
    if fake:
        console.print()
        fake_table = Table(
            title=f"[bold yellow]{len(fake)} File Hasil Palsu (Ukuran Sama Dengan Asli)[/bold yellow]",
            border_style="yellow",
            show_header=True
        )
        fake_table.add_column("No", justify="center", style="cyan", no_wrap=True)
        fake_table.add_column("File Mentah", style="white")
        fake_table.add_column("Subfolder", style="dim yellow")
        fake_table.add_column("Ukuran", justify="right", style="dim")

        for idx, (fp, rel, hasil_p) in enumerate(fake, 1):
            folder = str(Path(rel).parent) if str(Path(rel).parent) != "." else "[root]"
            size_mb = Path(fp).stat().st_size / 1024 / 1024 if Path(fp).exists() else 0
            fake_table.add_row(str(idx), str(Path(rel).name), folder, f"{size_mb:.1f} MB")

        console.print(fake_table)

    # File yang sudah ok
    if translated:
        console.print()
        done_table = Table(
            title=f"[bold green]{len(translated)} File Sudah Diterjemahkan[/bold green]",
            border_style="green",
            show_header=True,
            show_lines=False
        )
        done_table.add_column("No", justify="center", style="cyan", no_wrap=True)
        done_table.add_column("File Mentah", style="dim")
        done_table.add_column("File Hasil", style="green")

        for idx, (src_rel, dst_rel) in enumerate(translated, 1):
            done_table.add_row(
                str(idx),
                str(Path(src_rel).name),
                str(Path(dst_rel).name)
            )

        console.print(done_table)


async def amain():
    Path(DIR_MENTAH).mkdir(exist_ok=True)
    Path(DIR_HASIL).mkdir(exist_ok=True)
    Path(DIR_SELESAI).mkdir(exist_ok=True)

    mode_label = "Headless (Background)" if HEADLESS else "Windowed"
    console.print(Panel.fit(
        "[bold cyan]GOOGLE TRANSLATE AUTOMATOR[/bold cyan]\n"
        f"[dim]Mode {mode_label} | Verified OCR Engine | Re-translate Support | Smart Diff[/dim]",
        border_style="cyan"
    ))

    # Cek file di folder mentah dan folder hasil
    mentah_files = [
        str(fp) for fp in Path(DIR_MENTAH).rglob('*')
        if fp.is_file() and 'selesai' not in fp.parts
    ]
    mentah_media = [
        f for f in mentah_files
        if Path(f).suffix.lower() in IMAGE_EXTENSIONS | DOC_EXTENSIONS
    ]
    hasil_files = [
        str(fp) for fp in Path(DIR_HASIL).rglob('*')
        if fp.is_file() and fp.suffix.lower() in IMAGE_EXTENSIONS | DOC_EXTENSIONS
    ]

    source_dir = DIR_MENTAH
    files_to_process = []
    all_mentah_mode = False  # flag: apakah memproses semua file mentah

    # ── Kasus: Ada file di mentah DAN di hasil → tunjukkan semua opsi ──────────
    if mentah_media and hasil_files:
        translated, missing, fake = build_comparison_table()
        has_missing = len(missing) > 0
        has_fake    = len(fake) > 0

        menu_lines = (
            f"[bold green][1][/bold green] : Translate folder '[bold]mentah[/bold]' ({len(mentah_files)} file, semua file)\n"
            f"[bold yellow][2][/bold yellow] : Re-translate folder '[bold]hasil[/bold]' ({len(hasil_files)} file)\n"
            f"[bold cyan][3][/bold cyan] : Lihat perbandingan file mentah vs hasil (diff)\n"
        )

        if has_missing:
            menu_lines += (
                f"[bold magenta][4][/bold magenta] : Translate HANYA file yang belum ada hasilnya "
                f"([bold red]{len(missing)}[/bold red] file)\n"
            )
        else:
            menu_lines += "[dim][4] : Tidak ada file yang hilang[/dim]\n"

        if has_fake:
            menu_lines += (
                f"[bold red][5][/bold red] : Restore & Translate file hasil PALSU "
                f"([bold yellow]{len(fake)}[/bold yellow] file ukurannya sama dengan asli = gagal translate)"
            )
        else:
            menu_lines += "[dim][5] : Tidak ada file hasil palsu[/dim]"

        console.print(Panel(menu_lines, title="Pilih Aksi", border_style="cyan"))

        choice = None
        while choice is None:
            if msvcrt.kbhit():
                key = msvcrt.getch().lower()
                if key == b'1':
                    choice = '1'
                elif key == b'2':
                    choice = '2'
                elif key == b'3':
                    choice = '3'
                elif key == b'4' and has_missing:
                    choice = '4'
                elif key == b'5' and has_fake:
                    choice = '5'
            await asyncio.sleep(0.1)

        if choice == '1':
            source_dir = DIR_MENTAH
            files_to_process = mentah_files
            all_mentah_mode = True

        elif choice == '2':
            source_dir = DIR_HASIL
            files_to_process = hasil_files

        elif choice == '3':
            show_diff_table(translated, missing, fake)
            console.print("\n[dim]Jalankan kembali untuk melanjutkan translate.[/dim]\n")
            return

        elif choice == '4':
            if not missing:
                console.print("[bold green]Semua file sudah diterjemahkan![/bold green]")
                return
            source_dir = DIR_MENTAH
            files_to_process = [fp for fp, _ in missing]
            console.print(f"\n[bold magenta]Mode: Translate HANYA {len(files_to_process)} file yang belum ada hasilnya[/bold magenta]\n")

        elif choice == '5':
            if not fake:
                console.print("[bold green]Tidak ada file palsu![/bold green]")
                return
            console.print(f"\n[bold yellow]Mengembalikan {len(fake)} file palsu dari 'hasil' ke 'mentah'...[/bold yellow]")
            restored = restore_fake_results(fake)
            console.print(f"[bold green]{restored} file berhasil dikembalikan ke folder 'mentah'.[/bold green]")
            source_dir = DIR_MENTAH
            files_to_process = [fp for fp, _, _ in fake if Path(fp).exists()]
            # Juga cek yang baru dikembalikan dari selesai
            for _, rel, _ in fake:
                candidate = str(Path(DIR_MENTAH) / rel)
                if Path(candidate).exists() and candidate not in files_to_process:
                    files_to_process.append(candidate)
            console.print(f"[bold magenta]Mode: Translate ulang {len(files_to_process)} file yang gagal sebelumnya[/bold magenta]\n")

    # ── Kasus: Hanya ada file di mentah ────────────────────────────────────────
    elif mentah_files:
        source_dir = DIR_MENTAH
        files_to_process = mentah_files
        all_mentah_mode = True

    # ── Kasus: Hanya ada file di hasil ─────────────────────────────────────────
    elif hasil_files:
        console.print(f"[yellow]Folder '{DIR_MENTAH}' kosong, ditemukan {len(hasil_files)} file di folder '{DIR_HASIL}'.[/yellow]")
        console.print(Panel(
            f"[bold yellow][Y][/bold yellow] : Mulai Re-translate semua file di folder '[bold]hasil[/bold]'\n"
            f"[bold red][N][/bold red] : Keluar",
            title="Re-translate Folder Hasil?",
            border_style="yellow"
        ))
        choice = None
        while choice is None:
            if msvcrt.kbhit():
                key = msvcrt.getch().lower()
                if key == b'y':
                    choice = 'y'
                elif key == b'n':
                    choice = 'n'
            await asyncio.sleep(0.1)

        if choice == 'y':
            source_dir = DIR_HASIL
            files_to_process = hasil_files
        else:
            console.print("[dim]Program selesai.[/dim]")
            return
    else:
        console.print(f"[yellow]Tidak ada file di folder '{DIR_MENTAH}' maupun '{DIR_HASIL}'.[/yellow]")
        return

    if not files_to_process:
        console.print("[bold green]Tidak ada file yang perlu diproses.[/bold green]")
        return

    total = len(files_to_process)
    tabs = min(NUM_TABS, total)
    console.print(f"\n[bold]Memproses dari:[/bold] '{source_dir}'  |  [bold]Total file:[/bold] {total} file  |  [bold]Tab paralel:[/bold] {tabs} tab  |  [bold]Jeda tab:[/bold] {TAB_DELAY}s  |  [bold red]Batal:[/bold red] Tekan [bold]Q[/bold]\n")

    # Bersihkan Edge background process
    os.system('wmic process where "name=\'msedge.exe\' and commandline like \'%edge_profile%\'" call terminate >nul 2>&1')
    await asyncio.sleep(1)

    # Listener tombol Q di thread terpisah
    abort_thread = threading.Thread(target=_listen_abort, daemon=True)
    abort_thread.start()

    success_files = []
    failed_files  = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="msedge",
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-size=1920,1080",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-dev-shm-usage",
                "--js-flags=--max-old-space-size=4096"
            ]
        )

        # ── Jalankan Batch Utama ──────────────────────────────────────────────
        if source_dir == DIR_HASIL:
            batch_title = "Re-translating"
        elif not all_mentah_mode:
            batch_title = "Translating Missing"
        else:
            batch_title = "Translating"

        await run_batch(browser, files_to_process, source_dir, failed_files, success_files, title=batch_title)

        # ── Loop Retry Jika Ada File Gagal ────────────────────────────────────
        while failed_files and not abort_flag.is_set():
            console.print("\n")
            table = Table(title="Daftar File yang Ter-skip / Gagal", border_style="red")
            table.add_column("No", justify="center", style="cyan", no_wrap=True)
            table.add_column("File / Path", style="white")

            for idx, f in enumerate(failed_files, 1):
                table.add_row(str(idx), os.path.relpath(f, source_dir))

            console.print(table)
            console.print(Panel(
                "[bold yellow][R][/bold yellow] : Coba Lagi (Retry) semua file yang gagal di atas\n"
                "[bold red][S][/bold red] : Lewati (Skip) dan selesaikan program",
                title="Pilihan Aksi",
                border_style="yellow"
            ))

            choice = None
            while choice is None and not abort_flag.is_set():
                if msvcrt.kbhit():
                    key = msvcrt.getch().lower()
                    if key == b'r':
                        choice = 'r'
                    elif key == b's':
                        choice = 's'
                await asyncio.sleep(0.1)

            if choice == 's' or abort_flag.is_set():
                console.print("\n[dim]Melewati sisa file yang gagal.[/dim]")
                break

            if choice == 'r':
                retry_list = failed_files[:]
                failed_files.clear()
                console.print(f"\n[bold green]Memulai ulang {len(retry_list)} file...[/bold green]\n")
                await run_batch(browser, retry_list, source_dir, failed_files, success_files, title="Retrying")

        await browser.close()

    # ── Ringkasan Akhir ───────────────────────────────────────────────────────
    console.print("\n")
    if not failed_files and not abort_flag.is_set():
        summary_text = (
            f"[bold green]Semua {len(success_files)} file berhasil diproses & ditranslate![/bold green]\n"
            f"[dim]Hasil tersimpan di folder '{DIR_HASIL}'[/dim]"
        )
        console.print(Panel(summary_text, title="Status Akhir", border_style="green"))
    else:
        summary_text = (
            f"[bold green]Berhasil:[/bold green] {len(success_files)} file\n"
            f"[bold red]Gagal/Ter-skip:[/bold red] {len(failed_files)} file"
        )
        console.print(Panel(summary_text, title="Status Akhir", border_style="yellow"))

    # ── Bersihkan ISI Folder Mentah (HANYA jika mode semua file mentah) ───────
    if source_dir == DIR_MENTAH and all_mentah_mode:
        remaining = [
            p for p in Path(DIR_MENTAH).rglob('*')
            if p.is_file() and 'selesai' not in p.parts
        ]
        if not remaining and not abort_flag.is_set():
            for item in Path(DIR_MENTAH).iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except Exception as e:
                    console.print(f"[red]Gagal menghapus {item}: {e}[/red]")
            console.print("[green]Isi folder 'mentah' telah dibersihkan. Folder 'mentah' tetap ada.[/green]\n")
        else:
            if remaining:
                console.print(f"[yellow]{len(remaining)} file masih tersisa di folder 'mentah' (tidak dihapus).[/yellow]\n")


def main():
    asyncio.run(amain())

if __name__ == "__main__":
    main()
