# Google Translate Automator

Script Python untuk menterjemahkan file secara otomatis menggunakan Google Translate melalui browser automation (Playwright).

## Fitur
- Terjemahkan gambar (.jpg, .jpeg, .png, .webp)
- Terjemahkan dokumen PDF
- Proses batch semua file dalam folder mentah/ secara rekursif
- Simpan hasil ke folder hasil/
- Hapus otomatis folder mentah/ setelah semua file selesai

## Persyaratan
- Python 3.8+
- Microsoft Edge
- Playwright

## Instalasi
pip install playwright
playwright install msedge

## Cara Penggunaan
1. Letakkan file ke folder mentah/
2. Jalankan: python main.py atau klik run_translate.bat
3. Hasil tersimpan di folder hasil/
