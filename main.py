import os
import time
import shutil
import re
import asyncio
import threading
import msvcrt
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

import sys
import subprocess

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
NUM_TABS     = 5           # Optimal 4-5 tab agar tidak kena antrean/rate-limit Google
MAX_RETRIES  = 3           # Maksimal percobaan per file (termasuk refresh)
TRANSLATE_TIMEOUT = 25     # Timeout tunggu terjemahan dalam detik

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

async def dismiss_popups(page):
    """Menutup banner/dialog announcement Google Translate jika ada."""
    try:
        popup_btn = page.locator('button:has-text("Got it"), button:has-text("I agree"), button:has-text("Accept all"), button:has-text("Mengerti")').first
        if await popup_btn.is_visible():
            await popup_btn.click()
            await asyncio.sleep(0.2)
    except Exception:
        pass


async def try_download_image(page, rel_path: str, update_status) -> object:
    """Upload gambar ke Google Translate dan download hasilnya. Return download object atau None."""
    dl_selector = (
        'button:has-text("Download translation"), '
        'button:has-text("Download"), '
        'button[aria-label*="Download translation"], '
        'button[aria-label*="Unduh terjemahan"], '
        'button[aria-label*="Download"]'
    )
    
    download_btn = page.locator(dl_selector).first
    try:
        # Tunggu tombol download muncul
        await download_btn.wait_for(state="visible", timeout=TRANSLATE_TIMEOUT * 1000)
        update_status(f"[cyan]Mengunduh:[/cyan] {os.path.basename(rel_path)}")
    except TimeoutError:
        return None   # Timeout: me-refresh halaman dan coba lagi

    try:
        async with page.expect_download(timeout=20000) as dl_info:
            await download_btn.click()
        return await dl_info.value
    except TimeoutError:
        # Coba klik ulang tombol jika timeout download
        try:
            if await download_btn.is_visible():
                async with page.expect_download(timeout=10000) as dl_info:
                    await download_btn.click()
                return await dl_info.value
        except Exception:
            pass
    return None


async def process_file(context, file_path: str, progress: Progress, task_id,
                       lock: asyncio.Lock, failed_files: list, success_files: list) -> bool:
    """
    Proses satu file menggunakan tab baru yang bersih (clean page lifecycle).
    """
    filename = os.path.basename(file_path)
    rel_path = os.path.relpath(file_path, DIR_MENTAH)
    rel_dir  = os.path.dirname(rel_path)
    ext      = Path(filename).suffix.lower()
    is_image = ext in ['.jpg', '.jpeg', '.png', '.webp']
    abs_path = os.path.abspath(file_path)

    def update_status(text: str):
        progress.update(task_id, status_file=text)

    update_status(f"[yellow]Memproses:[/yellow] {filename}")

    downloaded = None
    success    = False

    try:
        for attempt in range(1, MAX_RETRIES + 1):
            if abort_flag.is_set():
                break

            if attempt > 1:
                update_status(f"[magenta]Coba lagi ({attempt}/{MAX_RETRIES}):[/magenta] {filename}")
                await asyncio.sleep(1)

            page = None
            try:
                page = await context.new_page()
                
                if is_image:
                    # ==== MODE GAMBAR ====
                    await page.goto(
                        "https://translate.google.com/?sl=auto&tl=en&op=images&hl=en",
                        wait_until="domcontentloaded",
                        timeout=30000
                    )
                    await dismiss_popups(page)

                    # Target spesifik input file gambar
                    file_input = page.locator('input[type="file"][accept*="image"]').first
                    if await file_input.count() == 0:
                        file_input = page.locator('input[type="file"]').last

                    await file_input.wait_for(state="attached", timeout=10000)
                    await file_input.set_input_files(abs_path)
                    
                    update_status(f"[blue]Menerjemahkan:[/blue] {filename} (Percobaan {attempt})")
                    downloaded = await try_download_image(page, rel_path, update_status)

                else:
                    # ==== MODE DOKUMEN ====
                    await page.goto(
                        "https://translate.google.com/?sl=auto&tl=en&op=docs&hl=en",
                        wait_until="domcontentloaded",
                        timeout=30000
                    )
                    await dismiss_popups(page)

                    file_input = page.locator('input[type="file"][accept*="pdf"]').first
                    if await file_input.count() == 0:
                        file_input = page.locator('input[type="file"]').first

                    await file_input.wait_for(state="attached", timeout=10000)
                    await file_input.set_input_files(abs_path)
                    
                    update_status(f"[blue]Menerjemahkan dokumen:[/blue] {filename} (Percobaan {attempt})")

                    download_btn = page.locator('button:has-text("Download translation"), button:has-text("Download"), button[aria-label*="Download"]').first
                    try:
                        await download_btn.wait_for(state="visible", timeout=TRANSLATE_TIMEOUT * 1000)
                        async with page.expect_download(timeout=20000) as dl:
                            await download_btn.click()
                        downloaded = await dl.value
                    except Exception:
                        downloaded = None

            except Exception:
                downloaded = None
            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass

            if downloaded:
                break

        # ── Simpan hasil jika download berhasil ────────────────────────────────
        if downloaded:
            target_hasil_dir   = os.path.join(DIR_HASIL, rel_dir)
            target_selesai_dir = os.path.join(DIR_SELESAI, rel_dir)
            Path(target_hasil_dir).mkdir(parents=True, exist_ok=True)
            Path(target_selesai_dir).mkdir(parents=True, exist_ok=True)

            safe_filename   = downloaded.suggested_filename
            final_save_path = os.path.join(target_hasil_dir, safe_filename)
            await downloaded.save_as(final_save_path)

            shutil.move(file_path, os.path.join(target_selesai_dir, filename))

            # Hapus folder asal jika kosong (kecuali root mentah)
            orig_dir = os.path.dirname(file_path)
            if orig_dir != DIR_MENTAH:
                try:
                    os.rmdir(orig_dir)
                except OSError:
                    pass

            success = True
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


async def run_batch(context, files_to_process: list, failed_files: list, success_files: list, title: str = "Translating"):
    """Jalankan batch file secara paralel dengan Loading Bar yang bersih dan rapi."""
    total = len(files_to_process)
    tabs  = min(NUM_TABS, total)

    sem  = asyncio.Semaphore(tabs)
    lock = asyncio.Lock()

    # Progress bar interaktif & bersih
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
            if abort_flag.is_set():
                return
            async with sem:
                await process_file(context, file_path, progress, task_id, lock, failed_files, success_files)

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
                await asyncio.sleep(0.3)


async def amain():
    Path(DIR_MENTAH).mkdir(exist_ok=True)
    Path(DIR_HASIL).mkdir(exist_ok=True)
    Path(DIR_SELESAI).mkdir(exist_ok=True)

    # Tampilkan banner header
    console.print(Panel.fit(
        "[bold cyan]GOOGLE TRANSLATE AUTOMATOR[/bold cyan]\n"
        "[dim]Mode Paralel Tab • Fast DOM Lifecycle • Clean Progress CLI[/dim]",
        border_style="cyan"
    ))

    # Kumpulkan semua file (kecuali folder selesai)
    files_to_process = [
        str(fp) for fp in Path(DIR_MENTAH).rglob('*')
        if fp.is_file() and 'selesai' not in fp.parts
    ]

    if not files_to_process:
        console.print(f"[yellow]Tidak ada file di folder '{DIR_MENTAH}' untuk diproses.[/yellow]")
        return

    total = len(files_to_process)
    tabs = min(NUM_TABS, total)
    console.print(f"[bold]Total file:[/bold] {total} file  |  [bold]Tab paralel:[/bold] {tabs} tab  |  [bold red]Batal:[/bold red] Tekan [bold]Q[/bold] kapan saja\n")

    # Bersihkan Edge background process
    os.system('wmic process where "name=\'msedge.exe\' and commandline like \'%edge_profile%\'" call terminate >nul 2>&1')
    await asyncio.sleep(1)

    USER_DATA_DIR = os.path.join(os.getcwd(), "edge_profile")

    # Listener tombol Q di thread terpisah
    abort_thread = threading.Thread(target=_listen_abort, daemon=True)
    abort_thread.start()

    success_files = []
    failed_files  = []

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            channel="msedge",
            headless=False,
            accept_downloads=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check"
            ]
        )

        # ── Jalankan Batch Utama ──────────────────────────────────────────────
        await run_batch(context, files_to_process, failed_files, success_files, title="Translating")

        # ── Loop Retry Jika Ada File Gagal ────────────────────────────────────
        while failed_files and not abort_flag.is_set():
            console.print("\n")
            table = Table(title="Daftar File yang Ter-skip / Gagal", border_style="red")
            table.add_column("No", justify="center", style="cyan", no_wrap=True)
            table.add_column("File / Path", style="white")

            for idx, f in enumerate(failed_files, 1):
                table.add_row(str(idx), os.path.relpath(f, DIR_MENTAH))

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
                await run_batch(context, retry_list, failed_files, success_files, title="Retrying")

        await context.close()

    # ── Ringkasan Akhir ───────────────────────────────────────────────────────
    console.print("\n")
    if not failed_files and not abort_flag.is_set():
        summary_text = (
            f"[bold green]Semua {len(success_files)} file berhasil ditranslate![/bold green]\n"
            f"[dim]Hasil tersimpan di folder '{DIR_HASIL}'[/dim]"
        )
        console.print(Panel(summary_text, title="Status Akhir", border_style="green"))
    else:
        summary_text = (
            f"[bold green]Berhasil:[/bold green] {len(success_files)} file\n"
            f"[bold red]Gagal/Ter-skip:[/bold red] {len(failed_files)} file"
        )
        console.print(Panel(summary_text, title="Status Akhir", border_style="yellow"))

    # ── Bersihkan ISI Folder Mentah (folder mentah tetap ada) ─────────────────
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
