import os
import time
import shutil
import re
import asyncio
import threading
import msvcrt
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

# ── Konfigurasi ───────────────────────────────────────────────────────────────
DIR_MENTAH  = "mentah"
DIR_HASIL   = "hasil"
DIR_SELESAI = "mentah/selesai"
NUM_TABS    = 10          # Jumlah tab paralel

# ── Abort flag ────────────────────────────────────────────────────────────────
abort_flag = threading.Event()
print_lock = threading.Lock()

def log(msg: str):
    with print_lock:
        print(msg)

def _listen_abort():
    """Thread background: menunggu tombol Q untuk membatalkan proses."""
    while not abort_flag.is_set():
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key.lower() == b'q':
                abort_flag.set()
                log("\n\n[ABORT] Proses dibatalkan! Menunggu tab aktif selesai...")
                break
        time.sleep(0.05)
# ─────────────────────────────────────────────────────────────────────────────

async def process_file(page, file_path: str, total: int, done: list, lock: asyncio.Lock):
    """Proses satu file (gambar/dokumen) menggunakan Playwright async."""
    filename = os.path.basename(file_path)
    rel_path = os.path.relpath(file_path, DIR_MENTAH)
    rel_dir  = os.path.dirname(rel_path)
    ext      = Path(filename).suffix.lower()
    is_image = ext in ['.jpg', '.jpeg', '.png', '.webp']

    log(f"\n[>>] Memproses: {rel_path}")

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
            log(f"  [{rel_path}] Diunggah. Menunggu terjemahan...")

            # Tunggu tombol Download muncul (terjemahan selesai)
            download_btn = page.locator('button', has_text=re.compile(r"Download", re.IGNORECASE)).first
            try:
                await download_btn.wait_for(state="visible", timeout=60000)
                log(f"  [{rel_path}] Terjemahan selesai! Mengunduh...")
            except TimeoutError:
                download_btn = page.locator('button[type="submit"]').first
                log(f"  [{rel_path}] Tombol Download tidak ditemukan, mencoba fallback...")

            downloaded = None
            try:
                async with page.expect_download(timeout=30000) as dl:
                    await download_btn.click()
                downloaded = await dl.value
            except TimeoutError:
                log(f"  [{rel_path}] Timeout, mencoba 'Download translation'...")
                alt_btn = page.locator('button', has_text=re.compile(r"Download translation", re.IGNORECASE)).first
                if await alt_btn.is_visible():
                    try:
                        async with page.expect_download(timeout=30000) as dl:
                            await alt_btn.click()
                        downloaded = await dl.value
                    except TimeoutError:
                        log(f"  [{rel_path}] Gagal mengunduh file.")
                else:
                    log(f"  [{rel_path}] Gagal mengunduh file.")

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
            log(f"  [{rel_path}] Dokumen diunggah. Menunggu terjemahan...")

            download_btn = page.locator('button', has_text=re.compile(r"Download", re.IGNORECASE)).first
            downloaded = None
            try:
                async with page.expect_download(timeout=30000) as dl:
                    await download_btn.click()
                downloaded = await dl.value
            except TimeoutError:
                log(f"  [{rel_path}] Timeout, mencoba lagi...")
                try:
                    async with page.expect_download(timeout=30000) as dl:
                        await download_btn.click()
                    downloaded = await dl.value
                except TimeoutError:
                    log(f"  [{rel_path}] Gagal mengunduh setelah dua percobaan.")

        # ── Simpan hasil ──────────────────────────────────────────────────────
        if downloaded:
            target_hasil_dir   = os.path.join(DIR_HASIL, rel_dir)
            target_selesai_dir = os.path.join(DIR_SELESAI, rel_dir)
            Path(target_hasil_dir).mkdir(parents=True, exist_ok=True)
            Path(target_selesai_dir).mkdir(parents=True, exist_ok=True)

            safe_filename   = downloaded.suggested_filename
            final_save_path = os.path.join(target_hasil_dir, safe_filename)
            await downloaded.save_as(final_save_path)
            log(f"  [OK] {rel_path} --> {final_save_path}")

            shutil.move(file_path, os.path.join(target_selesai_dir, filename))

            # Hapus folder asal jika kosong (kecuali root mentah)
            orig_dir = os.path.dirname(file_path)
            if orig_dir != DIR_MENTAH:
                try:
                    os.rmdir(orig_dir)
                except OSError:
                    pass
        else:
            log(f"  [SKIP] {rel_path}: Tidak ada file yang diunduh.")

    except asyncio.CancelledError:
        raise
    except Exception as e:
        log(f"  [!] Kesalahan pada {rel_path}: {e}")

    # Update counter progress
    async with lock:
        done[0] += 1
        log(f"[{done[0]}/{total}] selesai")


async def amain():
    Path(DIR_MENTAH).mkdir(exist_ok=True)
    Path(DIR_HASIL).mkdir(exist_ok=True)
    Path(DIR_SELESAI).mkdir(exist_ok=True)

    # Kumpulkan semua file (kecuali folder selesai)
    files_to_process = [
        str(fp) for fp in Path(DIR_MENTAH).rglob('*')
        if fp.is_file() and 'selesai' not in fp.parts
    ]

    if not files_to_process:
        print(f"Tidak ada file di folder '{DIR_MENTAH}' untuk diproses.")
        return

    total = len(files_to_process)
    tabs  = min(NUM_TABS, total)
    print(f"Ditemukan {total} file. Menggunakan {tabs} tab paralel.")

    # Hentikan Edge lama yang memakai profil ini
    print("Membersihkan background process Edge...")
    os.system('wmic process where "name=\'msedge.exe\' and commandline like \'%edge_profile%\'" call terminate >nul 2>&1')
    await asyncio.sleep(2)

    USER_DATA_DIR = os.path.join(os.getcwd(), "edge_profile")

    # Mulai thread abort listener
    abort_thread = threading.Thread(target=_listen_abort, daemon=True)
    abort_thread.start()

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            channel="msedge",
            headless=False,
            accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        # Buat pool page dengan asyncio.Queue (thread-safe untuk async)
        page_pool: asyncio.Queue = asyncio.Queue()
        pages = []
        existing = context.pages
        for i in range(tabs):
            pg = existing[0] if (i == 0 and existing) else await context.new_page()
            pages.append(pg)
            await page_pool.put(pg)

        print(f"\nProses dimulai dengan {tabs} tab paralel. Tekan [Q] untuk membatalkan.\n")

        done    = [0]
        counter_lock = asyncio.Lock()

        # Semaphore untuk batasi jumlah task aktif sekaligus
        sem = asyncio.Semaphore(tabs)

        async def worker(file_path: str):
            if abort_flag.is_set():
                return
            async with sem:
                page = await page_pool.get()
                try:
                    await process_file(page, file_path, total, done, counter_lock)
                finally:
                    await page_pool.put(page)

        # Buat semua task dan jalankan sekaligus
        tasks = [asyncio.create_task(worker(fp)) for fp in files_to_process]

        # Tunggu sambil cek abort setiap 0.5 detik
        while tasks:
            done_tasks   = [t for t in tasks if t.done()]
            active_tasks = [t for t in tasks if not t.done()]
            tasks = active_tasks

            if abort_flag.is_set():
                log("[ABORT] Membatalkan semua task...")
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                break

            if tasks:
                await asyncio.sleep(0.5)

        # Tutup semua tab lalu context
        for pg in pages:
            try:
                await pg.close()
            except Exception:
                pass
        await context.close()

    print("\nSemua proses selesai.")

    # Verifikasi & hapus ISI folder mentah jika semua file selesai (folder mentah tetap ada)
    remaining = [
        p for p in Path(DIR_MENTAH).rglob('*')
        if p.is_file() and 'selesai' not in p.parts
    ]
    if not remaining:
        # Hapus semua subfolder dan file di dalam mentah (kecuali folder mentah itu sendiri)
        for item in Path(DIR_MENTAH).iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except Exception as e:
                print(f"Gagal menghapus {item}: {e}")
        print("Isi folder 'mentah' telah dihapus. Folder 'mentah' tetap ada.")
    else:
        print(f"Beberapa file ({len(remaining)}) masih tersisa di folder 'mentah', tidak dihapus.")


def main():
    asyncio.run(amain())

if __name__ == "__main__":
    main()
