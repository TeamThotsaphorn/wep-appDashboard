# Fishing Forecast — MongoDB to Python

ชุดเริ่มต้นสำหรับเชื่อม MongoDB ในเครื่องกับ Python เพื่อสำรวจข้อมูลและเตรียมข้อมูลสำหรับระบบพยากรณ์การออกเรือ

## ไฟล์ในโฟลเดอร์
- `src/01_test_mongodb.py` — ทดสอบการเชื่อมต่อ แสดง Database, Collections และตัวอย่างเอกสาร
- `src/02_extract_data.py` — ส่งออกข้อมูลจาก MongoDB เป็น Parquet เพื่อวิเคราะห์ โดยไม่แก้ไขข้อมูลต้นฉบับ
- `src/03_profile_data.py` — สรุปจำนวนแถว คอลัมน์ ค่าว่าง และชนิดข้อมูล
- `src/04_prepare_dataset.py` — ตรวจสอบฟิลด์ก่อนเชื่อมข้อมูล โดยไม่เดาชื่อฟิลด์และไม่ทำ join อัตโนมัติ
- `.env.example` — ตัวอย่างการตั้งค่า
- `requirements.txt` — ไลบรารีที่ต้องติดตั้ง

## 1. เตรียมสภาพแวดล้อม (Windows 11)
ติดตั้ง Python 3.10+ และตรวจสอบว่า MongoDB Server ทำงานอยู่ จากนั้นเปิด Terminal ในโฟลเดอร์นี้:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

หาก PowerShell ไม่อนุญาตให้ activate ให้ใช้ Command Prompt:
```bat
.venv\Scripts\activate.bat
```

## 2. ตั้งค่า MongoDB
คัดลอก `.env.example` เป็น `.env` แล้วแก้ `MONGODB_URI` และ `MONGODB_DATABASE` ให้ตรงกับการเชื่อมต่อใน MongoDB Compass

ค่าเริ่มต้น `mongodb://localhost:27017/` และ Database `fishing_db` เป็นเพียงตัวอย่าง ต้องเปลี่ยนให้ตรงกับเครื่องจริง หากมี username/password ให้ใส่ไว้ใน `.env` ของตนเอง และห้าม commit ไฟล์ `.env` ที่มีข้อมูลลับขึ้น GitHub

## 3. ทดสอบการเชื่อมต่อ
```powershell
python src/01_test_mongodb.py
```

## 4. ส่งออกข้อมูลเพื่อวิเคราะห์
```powershell
python src/02_extract_data.py
```
ข้อมูลจะถูกบันทึกเป็น Parquet ใน `data/raw_snapshot/` โดยไม่แก้ไข MongoDB หากชื่อ Collection ไม่ตรง ให้แก้ `COLLECTIONS` ใน `.env`

## 5. ตรวจสอบคุณภาพข้อมูล
```powershell
python src/03_profile_data.py
```

## 6. เตรียมชุดข้อมูลร่วม
```powershell
python src/04_prepare_dataset.py
```
สคริปต์จะแสดงชื่อฟิลด์เพื่อให้ตรวจสอบก่อน join เพราะต้องยืนยันรหัสพื้นที่ timestamp/timezone หน่วยความสูงคลื่นและความเร็วลม รวมถึงเวลาที่ใช้ตัดสินใจออกเรือ

**ป้องกัน data leakage:** อย่าใช้ข้อมูลสภาพอากาศ/ทะเลที่เกิดหลังเวลาออกเรือเป็นตัวแปรทำนายก่อนออกเรือ

## หมายเหตุสำหรับการสร้างโมเดล
ข้อมูลทริปที่ออกเรือจริงอาจใช้พยากรณ์ปริมาณสัตว์น้ำหรือระยะเวลาทริปได้ หากตัวแปรครบ แต่การพยากรณ์ว่า “ควร/ไม่ควรออกเรือ” ต้องมี Target ที่น่าเชื่อถือ เช่น ผลการตัดสินใจหรือบันทึกการยกเลิก ไม่ควรสร้าง label เองจากทริปที่สำเร็จทั้งหมด

ข้อมูลอากาศและทะเลในชุดข้อมูลเดิมที่แนบมาเป็นรายวัน จึงต้องตรวจสอบความละเอียดของเวลาให้ตรงกับเป้าหมายก่อนใช้ประเมินการออกเรือจริง ค่าขีดจำกัดคลื่น/ลมต้องอ้างอิงข้อกำหนดเรือและประกาศทางการ ไม่ใช่เกณฑ์ตัวอย่างที่รับรองความปลอดภัย

## Web app (GitHub Pages)
หน้าเว็บอยู่ในโฟลเดอร์ `docs/` อ่านข้อมูลสรุปจาก `docs/data/*.json` ซึ่งส่งออกจาก MongoDB ด้วย:
```powershell
python -X utf8 src/11_export_web_data.py
```
GitHub Pages เป็นเว็บ static จึงไม่ได้เชื่อม MongoDB สด ต้องส่งออกและ push ใหม่เพื่ออัปเดตข้อมูล (`publish_web.bat` ทำทั้งสองขั้นตอน)

ข้อมูลบนเว็บเป็นสาธารณะ สคริปต์จึงไม่ส่งออกชื่อกัปตัน ชื่อเรือ ชื่อบริษัทลูกค้า และลิงก์รูปภาพ

ทดสอบในเครื่อง:
```powershell
cd docs
python -m http.server 5601 --bind 127.0.0.1
```
แล้วเปิด http://127.0.0.1:5601
