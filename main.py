import os
import time
import shutil
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError

# Konfigurasi Direktori
DIR_MENTAH = "mentah"
DIR_HASIL = "hasil"
DIR_SELESAI = "mentah/selesai"

def main():
    Path(DIR_MENTAH).mkdir(exist_ok=True)
    Path(DIR_HASIL).mkdir(exist_ok=True)
    Path(DIR_SELESAI).mkdir(exist_ok=True)

    # 1. Mendeteksi file per folder menggunakan Path.rglob agar lebih akurat membaca sub-folder
    files_to_process = []
    mentah_path = Path(DIR_MENTAH)
    
    for file_path in mentah_path.rglob('*'):
        if file_path.is_file():
            # Lewati file yang berada di dalam folder 'selesai'
            if 'selesai' in file_path.parts:
                continue
            files_to_process.append(str(file_path))

    if not files_to_process:
        print(f"Tidak ada file di folder '{DIR_MENTAH}' untuk diproses.")
        return

    print(f"Ditemukan {len(files_to_process)} file untuk diterjemahkan.")

    # Folder untuk menyimpan sesi login
    USER_DATA_DIR = os.path.join(os.getcwd(), "edge_profile")

    # Mencegah layar blank: Matikan proses Edge di latar belakang yang masih mengunci profil ini
    # (Hanya mematikan Edge yang menggunakan folder edge_profile, Edge utama Anda aman)
    print("Membersihkan background process Edge...")
    os.system(f'wmic process where "name=\'msedge.exe\' and commandline like \'%edge_profile%\'" call terminate >nul 2>&1')
    time.sleep(2)

    with sync_playwright() as p:
        # Menggunakan persistent context agar sesi login tersimpan
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            channel="msedge",
            headless=False,
            accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # Ambil halaman pertama dari context
        page = context.pages[0] if context.pages else context.new_page()
        # Skip login verification; proceeding directly.
        print("\nLogin check skipped; proceeding without authentication.")

        for file_path in files_to_process:
            filename = os.path.basename(file_path)
            
            # Mendapatkan path relatif (agar struktur folder dipertahankan di folder hasil)
            rel_path = os.path.relpath(file_path, DIR_MENTAH)
            rel_dir = os.path.dirname(rel_path)
            
            print(f"\nMemproses: {rel_path} ...")

            ext = Path(filename).suffix.lower()
            is_image = ext in ['.jpg', '.jpeg', '.png', '.webp']

            try:
                if is_image:
                    # ==== MODE GAMBAR ====
                    page.goto("https://translate.google.com/?sl=auto&tl=en&op=images&hl=en", wait_until="networkidle")
                    time.sleep(2)
                    
                    # Memilih input spesifik untuk gambar untuk menghindari Strict Mode
                    file_input = page.locator('input[type="file"][accept*="image"]').first
                    if file_input.count() == 0:
                        file_input = page.locator('input[type="file"]').nth(1)

                    file_input.set_input_files(file_path)
                    print("  - Gambar berhasil diunggah. Menunggu proses terjemahan...")
                    # Wait briefly for translation to start
                    time.sleep(2)
                    # Attempt to locate the download button (common labels)
                    download_btn = page.locator('button', has_text=re.compile(r"Download", re.IGNORECASE)).first
                    if not download_btn.is_visible():
                        # Fallback to generic submit button if specific not visible
                        download_btn = page.locator('button[type="submit"]').first
                    # Wait for the download button to become visible (translation may take time)
                    try:
                        download_btn.wait_for(state="visible", timeout=30000)
                    except TimeoutError:
                        print("  - Peringatan: Tidak dapat mengkonfirmasi status terjemahan (Mungkin teks tidak terdeteksi atau koneksi lambat). Melanjutkan unduhan...")
                    # Klik tombol Download dan tunggu download (timeout 8000ms)
                    downloaded = None
                    try:
                        with page.expect_download(timeout=8000) as dl:
                            download_btn.click()
                        downloaded = dl.value
                    except TimeoutError:
                        print("  - Timeout menunggu download, mencoba lagi...")
                        try:
                            with page.expect_download(timeout=20000) as dl:
                                download_btn.click()
                            downloaded = dl.value
                        except TimeoutError:
                            print("  - Gagal mengunduh file setelah dua percobaan.")
                    # fallback to alternative button text if still not downloaded
                    if not downloaded:
                        alt_btn = page.locator('button', has_text=re.compile(r"Download translation", re.IGNORECASE)).first
                        if alt_btn.is_visible():
                            try:
                                with page.expect_download(timeout=8000) as dl:
                                    alt_btn.click()
                                downloaded = dl.value
                            except TimeoutError:
                                print("  - Timeout pada fallback download button.")
                    if downloaded:
                        target_hasil_dir = os.path.join(DIR_HASIL, rel_dir)
                        target_selesai_dir = os.path.join(DIR_SELESAI, rel_dir)
                        Path(target_hasil_dir).mkdir(parents=True, exist_ok=True)
                        Path(target_selesai_dir).mkdir(parents=True, exist_ok=True)
                        safe_filename = downloaded.suggested_filename
                        final_save_path = os.path.join(target_hasil_dir, safe_filename)
                        downloaded.save_as(final_save_path)
                        print(f"  - Sukses! Hasil disimpan di: {final_save_path}")
                        shutil.move(file_path, os.path.join(target_selesai_dir, filename))
                    else:
                        print("  - Tidak ada file yang diunduh; melewati penyimpanan.")                    
                else:
                    # ==== MODE DOKUMEN ====
                    page.goto("https://translate.google.com/?sl=auto&tl=en&op=docs&hl=en", wait_until="networkidle")
                    time.sleep(2)
                    
                    # Memilih input spesifik untuk dokumen (.pdf) untuk menghindari Strict Mode
                    file_input = page.locator('input[type="file"][accept*="pdf"]').first
                    if file_input.count() == 0:
                        file_input = page.locator('input[type="file"]').first
                    
                    file_input.set_input_files(file_path)
                    print("  - Dokumen berhasil diunggah.")                    # Klik tombol download dan tunggu download (timeout 8000ms)
                    download_btn = page.locator('button', has_text=re.compile(r"Download", re.IGNORECASE)).first
                    downloaded = None
                    try:
                        with page.expect_download(timeout=8000) as dl:
                            download_btn.click()
                        downloaded = dl.value
                    except TimeoutError:
                        print("  - Timeout menunggu download, mencoba lagi...")
                        try:
                            with page.expect_download(timeout=20000) as dl:
                                download_btn.click()
                            downloaded = dl.value
                        except TimeoutError:
                            print("  - Gagal mengunduh file setelah dua percobaan.")
                    if downloaded:
                        target_hasil_dir = os.path.join(DIR_HASIL, rel_dir)
                        target_selesai_dir = os.path.join(DIR_SELESAI, rel_dir)
                        Path(target_hasil_dir).mkdir(parents=True, exist_ok=True)
                        Path(target_selesai_dir).mkdir(parents=True, exist_ok=True)
                        safe_filename = downloaded.suggested_filename
                        final_save_path = os.path.join(target_hasil_dir, safe_filename)
                        downloaded.save_as(final_save_path)
                        print(f"  - Suksus! Hasil disimpan di: {final_save_path}")
                        shutil.move(file_path, os.path.join(target_selesai_dir, filename))
                        # Hapus folder asal jika kosong (kecuali folder mentah utama)
                        orig_dir = os.path.dirname(file_path)
                        if orig_dir != DIR_MENTAH:
                            try:
                                os.rmdir(orig_dir)
                            except OSError:
                                pass
                    else:
                        print("  - Tidak ada file yang diunduh; melewati penyimpanan.")
                    translate_btn = page.locator('button', has_text=re.compile(r"Translate", re.IGNORECASE)).first
                    if not translate_btn.is_visible():
                        translate_btn = page.locator('button[type="submit"]').first
                    



            except Exception as e:
                print(f"  - Terjadi kesalahan: {e}")
            
            time.sleep(3)

        print("\nSemua file telah diproses.")
        # Tutup konteks browser
        context.close()
        # Verifikasi apakah semua file sumber telah diproses (folder mentah kosong terkecuali folder selesai)
        remaining = [p for p in Path(DIR_MENTAH).rglob('*') if p.is_file()]
        if not remaining:
            try:
                shutil.rmtree(DIR_MENTAH)
                print("Folder 'mentah' telah dihapus karena semua file telah diproses.")
            except Exception as e:
                print(f"Gagal menghapus folder 'mentah': {e}")
        else:
            print("Beberapa file masih tersisa di folder 'mentah', tidak dihapus.")
        print("Folder sumber selesai diproses telah dihapus (jika kosong).")
if __name__ == "__main__":
    main()
