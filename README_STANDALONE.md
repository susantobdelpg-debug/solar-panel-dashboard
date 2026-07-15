# Panduan Menjalankan & Membangun Standalone Windows Executable (.exe)

Solar PV KPI Dashboard dapat dikemas menjadi satu folder mandiri (standalone) yang bisa dijalankan di komputer Windows **tanpa perlu menginstal Python, pip, atau pustaka eksternal lainnya**.

---

## 📋 Catatan Penting Pengguna Akhir (.exe)

1. **Koneksi Internet Aktif:** 
   Aplikasi membutuhkan koneksi internet aktif saat dijalankan untuk mengambil data prakiraan dan historis cuaca real-time dari API publik **Open-Meteo**. Jika dijalankan secara offline, dashboard secara otomatis beralih menampilkan **Data Simulasi/Mock** dan memunculkan spanduk peringatan berwarna merah.
   
2. **Izin Windows Defender Firewall:**
   Saat pertama kali `launcher.exe` dijalankan, Windows Defender Firewall mungkin akan memunculkan dialog peringatan untuk meminta izin akses jaringan. 
   - **Mengapa ini terjadi?** Streamlit berjalan dengan meluncurkan server lokal (local host) di port `8501`.
   - **Solusi:** Pilih **"Allow Access"** (Izinkan Akses) untuk jaringan privat agar antarmuka web dashboard dapat dimuat dengan lancar di browser Anda.

---

## 🛠️ Langkah-Langkah Membangun Executable di Windows

Karena PyInstaller tidak mendukung kompilasi silang (*cross-compile*) secara langsung (membangun Windows .exe dari OS Linux/macOS dengan mudah), proses build **harus dilakukan secara langsung di komputer Windows target** dengan langkah-langkah berikut:

### Prasyarat
Instal Python (versi 3.8 s/d 3.12 direkomendasikan) di komputer Windows Anda, lalu buka **Command Prompt (cmd)** atau **PowerShell** di folder proyek (`solar_dashboard`).

### Langkah 1: Instalasi Pustaka Dependensi
Instal semua pustaka analisis data, visualisasi, dan PyInstaller:
```powershell
pip install -r requirements.txt
pip install pyinstaller
```

### Langkah 2: Menjalankan Kompilasi PyInstaller
Jalankan kompilasi menggunakan berkas konfigurasi `.spec` yang sudah disediakan:
```powershell
pyinstaller launcher.spec --noconfirm
```
*Catatan: Parameter `--noconfirm` akan otomatis menimpa folder kompilasi lama tanpa memunculkan prompt konfirmasi.*

### Langkah 3: Menemukan Hasil Build
Setelah proses kompilasi selesai (`Build complete!`), hasil standalone aplikasi akan tersedia di direktori proyek:
```text
solar_dashboard/dist/launcher/
```
Folder `launcher/` ini berisi berkas `launcher.exe` serta sub-folder `_internal/` yang menampung semua modul runtime Python, pandas, plotly, folium, dan aset frontend Streamlit.

### Langkah 4: Distribusi
Untuk mendistribusikan aplikasi ke komputer lain:
1. Klik kanan pada folder `launcher` di dalam direktori `dist`.
2. Pilih **Send to -> Compressed (zipped) folder** untuk mengompresinya menjadi berkas `.zip`.
3. Kirimkan berkas `.zip` tersebut ke pengguna akhir. Mereka hanya perlu mengekstrak `.zip` tersebut dan langsung menjalankan `launcher.exe` di dalamnya.
