import os
import time
import shutil
import re
import asyncio
import threading
import msvcrt
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

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
NUM_TABS     = 10          # Jumlah tab paralel
MAX_RETRIES  = 3           # Maksimal percobaan per file (termasuk refresh)

console = Console()

# ── Abort flag ────────────────────────────────────────────────────────────────
abort_flag = threading.Event()

def _listen_abort(progress_ref=None):
    """Thread background: menunggu tombol Q untuk membatalkan proses."""
    while not abort_flag.is_set():
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key.lower() == b'q':
                abort_flag.set()
                console.print("\n[bold red][ABORT][/bold red] Pembatalan diminta! Menghentikan semua tab...", style="red")
                break
        time.sleep(0.05)
# ─────────────────────────────────────────────────────────────────────────────

async def try_download_image(page, rel_path: str, update_status) -> object:
    """Upload gambar ke Google Translate dan download hasilnya. Return download object atau None."""
    download_btn = page.locator('button', has_text=re.compile(r"Download", re.IGNORECASE)).first
    try:
        # Timeout 30 detik untuk menunggu tombol download muncul
        await download_btn.wait_for(state="visible", timeout=30000)
        update_status(f"[cyan]Mengunduh:[/cyan] {os.path.basename(rel_path)}")
    except TimeoutError:
        return None   # Sinyal timeout agar fungsi pemanggil me-refresh halaman dan coba lagi

    try:
        async with page.expect_download(timeout=30000) as dl:
            await download_btn.click()
        return await dl.value
    except TimeoutError:
        alt_btn = page.locator('button', has_text=re.compile(r"Download translation", re.IGNORECASE)).first
        if await alt_btn.is_visible():
            try:
                async with page.expect_download(timeout=30000) as dl:
                    await alt_btn.click()
                return await dl.value
            except TimeoutError:
                pass
    return None


async def process_file(page, file_path: str, progress: Progress, task_id,
                       lock: asyncio.Lock, failed_files: list, success_files: list) -> bool:
    """
    Proses satu file. Jika timeout, refresh page dan coba lagi sampai MAX_RETRIES.
    """
    filename = os.path.basename(file_path)
    rel_path = os.path.relpath(file_path, DIR_MENTAH)
    rel_dir  = os.path.dirname(rel_path)
    ext      = Path(filename).suffix.lower()
    is_image = ext in ['.jpg', '.jpeg', '.png', '.webp']

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
                update_status(f"[magenta]Refresh & coba lagi ({attempt}/{MAX_RETRIES}):[/magenta] {filename}")
                try:
                    await page.reload(wait_until="networkidle")
                    await asyncio.sleep(1)
                except Exception:
                    pass

            try:
                if is_image:
                    # ==== MODE GAMBAR ====
                    await page.goto(
                        "https://translate.google.com/?sl=auto&tl=en&op=images&hl=en",
                        wait_until="networkidle"
                    )

                    file_input = page.locator('input[type="file"][accept*="image"]').first
                    if await file_input.count() == 0:
                        file_input = page.locator('input[type="file"]').nth(1)

                    await file_input.set_input_files(file_path)
                    update_status(f"[blue]Menerjemahkan:[/blue] {filename} (Percobaan {attempt})")

                    downloaded = await try_download_image(page, rel_path, update_status)

                else:
                    # ==== MODE DOKUMEN ====
                    await page.goto(
                        "https://translate.google.com/?sl=auto&tl=en&op=docs&hl=en",
                        wait_until="networkidle"
                    )
                    await asyncio.sleep(1)

                    file_input = page.locator('input[type="file"][accept*="pdf"]').first
                    if await file_input.count() == 0:
                        file_input = page.locator('input[type="file"]').first

                    await file_input.set_input_files(file_path)
                    update_status(f"[blue]Menerjemahkan dokumen:[/blue] {filename} (Percobaan {attempt})")

                    download_btn = page.locator('button', has_text=re.compile(r"Download", re.IGNORECASE)).first
                    try:
                        async with page.expect_download(timeout=30000) as dl:
                            await download_btn.click()
                        downloaded = await dl.value
                    except TimeoutError:
                        downloaded = None

            except Exception:
                downloaded = None

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


async def run_batch(context, files_to_process: list, failed_files: list, success_files: list, title: str = "Memproses"):
    """Jalankan batch file secara paralel dengan Loading Bar yang bersih dan rapi."""
    total = len(files_to_process)
    tabs  = min(NUM_TABS, total)

    page_pool: asyncio.Queue = asyncio.Queue()
    pages = []
    existing = context.pages
    for i in range(tabs):
        pg = existing[0] if (i == 0 and existing) else await context.new_page()
        pages.append(pg)
        await page_pool.put(pg)

    sem = asyncio.Semaphore(tabs)
    lock = asyncio.Lock()

    # Progress bar interaktif & bersih (tidak print panjang ke bawah)
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
            status_file="[dim]Memulai tab...[/dim]"
        )

        async def worker(file_path: str):
            if abort_flag.is_set():
                return
            async with sem:
                page = await page_pool.get()
                try:
                    await process_file(page, file_path, progress, task_id, lock, failed_files, success_files)
                finally:
                    await page_pool.put(page)

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

    # Tutup tab yang telah dibuat
    for pg in pages:
        try:
            await pg.close()
        except Exception:
            pass


async def amain():
    Path(DIR_MENTAH).mkdir(exist_ok=True)
    Path(DIR_HASIL).mkdir(exist_ok=True)
    Path(DIR_SELESAI).mkdir(exist_ok=True)

    # Tampilkan banner header yang rapi
    console.print(Panel.fit(
        "[bold cyan]GOOGLE TRANSLATE AUTOMATOR[/bold cyan]\n"
        "[dim]Mode 10 Tab Paralel • Auto-Refresh on Timeout (30s) • Clean CLI[/dim]",
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
            args=["--disable-blink-features=AutomationControlled"]
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
