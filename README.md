# Dashboard KPI Sistem Panel Surya (rekonstruksi)

Dashboard ini dibangun ulang agar sesuai spesifikasi di presentasi "Analisis KPI Sistem
Panel Surya pada Beberapa Lokasi di Indonesia": panel 2 m², efisiensi 20%, sumber data
Open-Meteo, 6 lokasi (Jakarta, Bandung, Bali/Denpasar, Semarang, Medan, Balikpapan).

## Cara menjalankan

```bash
pip install -r requirements.txt
streamlit run app.py
```

Dashboard butuh akses internet ke `api.open-meteo.com`. Jika API tidak terjangkau
(mis. lingkungan sandbox tanpa internet), aplikasi otomatis jatuh ke **mode simulasi**
dan menampilkan banner peringatan merah — data pada mode ini BUKAN data cuaca nyata,
hanya untuk keperluan demo tampilan.

## Apa yang berbeda dari versi sebelumnya (temuan review)

1. **Performance Ratio yang sebenarnya.** KPI "Performance Ratio (true)" sekarang
   dihitung sebagai energi aktual (setelah rugi suhu & sistem) dibagi energi ideal pada
   iradiasi yang SAMA — bukan sekadar rasio daya puncak terhadap kapasitas nameplate
   400 Wp. Rasio ke nameplate tetap ditampilkan terpisah agar bisa dibandingkan dengan
   angka di presentasi versi lama.
2. **Model rugi-rugi (losses) eksplisit**, bukan janji kosong: de-rate suhu sel
   (model NOCT + koefisien daya c-Si) dan de-rate sistem (inverter/kabel/soiling,
   `SYSTEM_DERATE` di `config.py`) sekarang benar-benar dihitung per jam, bukan hanya
   disebut di slide metodologi tanpa implementasi.
3. **Tab perbandingan antar lokasi** (checkbox di sidebar) — semua 6 kota dihitung
   dengan model & rentang waktu yang sama, ditampilkan dalam satu tabel + bar chart,
   supaya klaim "lokasi paling potensial" punya dasar yang bisa diaudit langsung dari
   dashboard, bukan hanya dari tabel manual di slide.
4. **Semua asumsi terpusat dan terlihat di UI** (`utils/config.py` + kotak kuning di
   dashboard): faktor emisi CO₂, tarif listrik, NOCT, koefisien suhu, de-rate sistem.
   Nilai-nilai ini adalah ASUMSI dan perlu diverifikasi/dikutip sumbernya sebelum
   dipakai di laporan akhir — terutama faktor emisi grid dan tarif listrik yang
   sangat memengaruhi angka CO₂ saved & penghematan biaya.

## Keterbatasan yang masih ada (perlu didiskusikan lebih lanjut)

- Ini adalah **model berbasis data cuaca** (irradiance → estimasi daya panel), bukan
  pembacaan sensor/inverter nyata. Untuk skripsi/paper, sebaiknya dinyatakan eksplisit
  sebagai estimasi model, dan idealnya divalidasi terhadap data logger aktual jika ada.
- Periode data historis (30 hari default) masih pendek untuk klaim potensi tahunan;
  `PAST_DAYS` di `config.py` bisa diperbesar (Open-Meteo forecast API mendukung
  `past_days` hingga 92 hari; untuk periode lebih panjang perlu Historical/Archive API
  terpisah).
- Faktor emisi CO₂ dan tarif listrik adalah default yang perlu dicek ulang ke sumber
  resmi terbaru (Kementerian ESDM/PLN) dan dikutip di laporan.

## Struktur proyek

```
app.py                     # UI Streamlit
utils/config.py            # semua konstanta & asumsi (lokasi, spek panel, faktor konversi)
utils/open_meteo_api.py    # fetch + fallback simulasi jika API tak terjangkau
utils/kpi.py                # model output PV + perhitungan KPI
```
