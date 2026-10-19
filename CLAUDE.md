# Fishing Forecast — MongoDB to Python

พยากรณ์การออกเรือ/ปริมาณจับของประมง EEC จากข้อมูลใน MongoDB ในเครื่อง ขั้นตอนติดตั้งอยู่ใน README.md

## สภาพแวดล้อม
- Windows 11, PowerShell, Python 3.14 ใน `.venv` (เรียกด้วย `.\.venv\Scripts\python.exe`)
- MongoDB ในเครื่องที่ `mongodb://localhost:27017/` ฐานข้อมูลที่ใช้คือ **`eec_seafood`** (ตั้งใน `.env`, ไม่ใช่ค่าเริ่มต้น `fishing_db` ที่ไม่มีอยู่จริง)
- ฐาน `MYFISH` ในเครื่องเดียวกันเป็นข้อมูลอีกชุด (Weather_Report, Catch_Record, order_export) ยังไม่ได้ใช้
- ผ่าน Windows console ให้ใส่ `-X utf8` ตอนรันสคริปต์ที่พิมพ์ภาษาไทย

## ลำดับสคริปต์ (รันจากโฟลเดอร์รากของโปรเจกต์)
| ไฟล์ | หน้าที่ |
|---|---|
| `src/01_test_mongodb.py` | ทดสอบการเชื่อมต่อ |
| `src/02_extract_data.py` | ส่งออก 4 collection เป็น Parquet ใน `data/raw_snapshot/` (แปลง ObjectId/Decimal128 เป็น string) |
| `src/03_profile_data.py` | โปรไฟล์ข้อมูล |
| `src/04_prepare_dataset.py` | join ทริป + โซน + ทะเล + อากาศ แล้วบันทึก `data/processed/trips_features.parquet` |
| `src/05_train_model.py` | โมเดลพยากรณ์ `ft_total_catch_kg` (แบ่งชุดฝึก/ทดสอบตามเวลา) |
| `src/06_compare_features.py` | เทียบโมเดลที่มี/ไม่มีฟีเจอร์อากาศ-ทะเล (5 fold ตามเวลา) |
| `src/07_trip_activity.py` | ทริปต่อโซน-วัน เทียบกับอากาศ/ทะเล (Poisson) |
| `src/08_make_dashboard_data.py` | สร้างไฟล์ JSON สรุปสำหรับ dashboard: `python src/08_make_dashboard_data.py <โฟลเดอร์ปลายทาง>` |
| `src/09_fetch_forecast.py` | ดึงพยากรณ์ Open-Meteo 7 วันลง `weather_forcasting` (สคริปต์เดียวที่เขียน MongoDB) |
| `src/10_migrate_forecast_key.py` | ย้าย key พยากรณ์เป็น `fc_run_id` (รันไปแล้ว) |
| `src/11_export_web_data.py` | ส่งออก JSON สรุปสำหรับ web app ไปที่ `docs/data/` |

## โครงข้อมูล (ที่ตรวจแล้ว)
- ทริป 6,353 แถว (2022-01-01 ถึง 2026-09-30) ทุกตารางเป็นรายวัน เวลา 00:00 ไม่มี timezone
- join: ทริป → `fz_zone_id` → `sea_conditions.sc_zone_id`; ทริป → `fishing_zones.fz_weather_station_id` → `weather_reports.wr_station_id`
- โซน ZON006, ZON022, ZON023 ไม่มีสถานีอากาศ (ฟีเจอร์อากาศว่าง)
- อุณหภูมิน้ำ `sc_sst_avg_c` ว่างประมาณ 89% ในปี 2022 โมเดลต้องตัดคอลัมน์ที่ว่างทั้งหมดในชุดฝึกออก (ทำไว้แล้วใน 06)
- `ft_catches` เป็นข้อมูลซ้อนกัน ถูกตัดออกจาก `trips_features.parquet`

## กฎที่ต้องรักษา
- **ห้าม data leakage**: ฟีเจอร์อากาศ/ทะเลใช้เฉพาะก่อนวันออกเรือ (`_d1` = วัน D-1, `_mean3d` = เฉลี่ย D-3..D-1) ไม่ใช้ค่าของวันออกเรือเอง
- ห้ามใช้เป็นตัวแปรทำนาย: `ft_total_catch_kg`, `ft_revenue_thb`, `ft_profit_thb`, `ft_return_date`, `ft_costs.*` (ทราบหลังทริปจบ)
- ไม่มี label "ควร/ไม่ควรออกเรือ" ในข้อมูล ห้ามสร้างเองจากทริปที่สำเร็จทั้งหมด
- ไม่แก้ข้อมูลใน MongoDB สคริปต์ทั้งหมดอ่านอย่างเดียว ยกเว้น 09/10 ที่เขียนเฉพาะ `weather_forcasting`
- ห้าม commit `.env`

## ผลที่พบ (อย่าสรุปเกินนี้)
- ตัวแปรที่มีผลเกือบทั้งหมดต่อปริมาณจับคือ `ft_crew_count`
- ฟีเจอร์อากาศ/ทะเลรายวันไม่ช่วยพยากรณ์: ปริมาณจับ MAE 330.4 → 331.9 kg, จับต่อลูกเรือ 24.27 → 24.24, จำนวนทริป deviance 0.5857 → 0.5885 (ผลต่างอยู่ในระดับความผันผวนระหว่าง fold)
- ทริปต่อโซน-วันลดลงเล็กน้อยเมื่อคลื่นสูง (0.178 → 0.136 ที่ควอไทล์บนสุด) แต่ไม่ช่วยในโมเดล
- ข้อสรุปนี้ใช้กับข้อมูลรายวันระดับโซนเท่านั้น ถ้าจะพัฒนาต่อ ต้องมีข้อมูลรายชั่วโมงใกล้เวลาออกเรือ และบันทึกการงดออกเรือพร้อมเหตุผล

## Dashboard
- เผยแพร่ที่ https://claude.ai/artifact/RbUYkgVS1PREGGFXkz2kGw (ประเภท Dashboard, ส่วนตัวจนกว่าเจ้าของกดแชร์)
- เผยแพร่ออนไลน์เชื่อม MongoDB ในเครื่องไม่ได้ จึงใช้ไฟล์ JSON สรุป 5 ชุด (monthly, zones, gear, wave_activity, model_tests) ที่อัปโหลดเป็นข้อมูลคงที่
- ตัวเลขใน `model_tests` พิมพ์มือจากผลของสคริปต์ 06/07 ไม่ได้คำนวณอัตโนมัติ ถ้ารันโมเดลใหม่ต้องอัปเดตเอง
- อัปเดตข้อมูล: รัน 02 → 04 → 08, อัปโหลด JSON ใหม่ทับไฟล์เดิมใน dashboard แล้ว update เอกสาร `datasets/<id>` (`url`, `updated`)
- แก้ dashboard ต้องอ่านคำแนะนำของประเภท Dashboard จาก artifact ก่อน (เก็บใน store ของ artifact ไม่ใช่ไฟล์ในโปรเจกต์นี้)

## Backend / Frontend / พยากรณ์ (เพิ่ม 2026-10-18)
- API: `backend/main.py` (FastAPI อ่านอย่างเดียว) รัน `.\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000` ตรวจ schema ด้วย `backend/inspect_mongodb_schema.py`
- Dashboard ใช้งานจริง: `frontend/index.html` (ต้นฉบับสำรอง `.bak`) เสิร์ฟด้วย `python -m http.server 5500 --bind 127.0.0.1` ในโฟลเดอร์ frontend (CORS อนุญาตพอร์ต 5500/8080 เท่านั้น)
- พยากรณ์อยู่ใน collection `weather_forcasting` (สะกดแบบนี้จริง) ดึงจาก Open-Meteo เท่านั้น (ไม่ใช้ TMD) ด้วย `src/09_fetch_forecast.py`
- key ของพยากรณ์คือ (`fc_zone_id`, `fc_forecast_date`, `fc_run_id`) เก็บทุกรอบที่ดึง ไม่เขียนทับ `fc_run_id` = เวลาที่ดึง UTC เช่น 20261018T150646Z (ย้ายจาก key เดิมด้วย `src/10_migrate_forecast_key.py` แล้ว) API `/api/forecasts` คืนรอบล่าสุดเป็นค่าเริ่มต้น
- ถ้าจะใช้พยากรณ์เป็นฟีเจอร์โมเดล ต้องเลือกรอบที่ `fc_fetched_at` ก่อนเวลาออกเรือเท่านั้น (กัน leakage)
- ตั้งดึงอัตโนมัติด้วย Windows Task Scheduler ชื่อ `EEC_Seafood_Fetch_Forecast` (ทุกวัน 06:00, รัน `run_forecast_fetch.bat`, log ที่ `logs/fetch_forecast.log`)
- ค่าพยากรณ์เป็นของกริด Open-Meteo (marine กับ forecast คนละกริด ไม่ใช่พิกัดโซนตรงๆ) และไม่ใช่คำแนะนำด้านความปลอดภัยในการเดินเรือ

## Web app (GitHub Pages, เพิ่ม 2026-10-19)
- อยู่ใน `docs/` (index.html + assets/app.js + assets/app.css + data/*.json) เป็นเว็บ static ไม่มี build step ใช้ d3 7.9.0 จาก cdnjs
- GitHub Pages เชื่อม MongoDB ในเครื่องไม่ได้ ตัวเลขทุกตัวมาจาก `docs/data/*.json` ที่สร้างด้วย `src/11_export_web_data.py`
- อัปเดตเว็บ: รัน `publish_web.bat` (ส่งออก JSON → commit `docs/data` → push)
- **ข้อมูลบนเว็บเป็นสาธารณะ** ห้ามส่งออกชื่อกัปตัน ชื่อเรือ ชื่อบริษัทลูกค้า และลิงก์/ไฟล์รูปภาพ (สคริปต์ 11 ตัดออกแล้ว ถ้าเพิ่มฟิลด์ใหม่ต้องตรวจซ้ำ)
- ตัวเลขผลโมเดลใน `MODEL_TESTS`/`SINGLE_SPLIT` ของสคริปต์ 11 พิมพ์มือจากผลสคริปต์ 05–07 ถ้ารันโมเดลใหม่ต้องแก้ตาม
- ทดสอบในเครื่อง: `python -m http.server 5601 --bind 127.0.0.1` ในโฟลเดอร์ docs แล้วเปิด http://127.0.0.1:5601 (เปิดแบบ file:// ไม่ได้ เพราะต้อง fetch JSON)
- Repo: https://github.com/TeamThotsaphorn/wep-appDashboard (public, branch main) · Pages: https://teamthotsaphorn.github.io/wep-appDashboard/ (Source = main /docs)
