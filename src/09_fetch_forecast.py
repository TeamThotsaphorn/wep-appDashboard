"""ดึงพยากรณ์ทะเล/อากาศ 7 วันจาก Open-Meteo ให้ทุกโซนประมง แล้วเก็บลง MongoDB (weather_forcasting)

เก็บ 1 เอกสารต่อ (โซน, วันที่พยากรณ์, รอบที่ดึง fc_run_id) ดึงกี่ครั้งก็เก็บทุกรอบ ไม่เขียนทับรอบเก่า
(ต้องรัน src/10_migrate_forecast_key.py --apply หนึ่งครั้งก่อน เพื่อเปลี่ยน unique index)
ใช้ตรวจความแม่นยำภายหลัง และใช้เฉพาะพยากรณ์ที่ออกก่อนวันออกเรือได้ (ไม่ทำให้เกิด leakage)

ใช้งาน:  python src/09_fetch_forecast.py            # ดึงครั้งเดียว
         python src/09_fetch_forecast.py --loop 180  # ดึงซ้ำทุก 180 นาที
         python src/09_fetch_forecast.py --dry-run   # ดึง+ตรวจข้อมูลแต่ไม่เขียน MongoDB (แสดงว่าจะเพิ่ม/อัปเดตกี่แถว)
"""
import argparse
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

load_dotenv()
COLLECTION = os.getenv("FORECAST_COLLECTION", "weather_forcasting")
DAYS = 7
CHUNK = 12  # จำนวนพิกัดต่อคำขอ (กัน URL ยาวเกินไป)
# ช่วงค่าที่ยอมรับได้ ค่านอกช่วงถือว่าผิดปกติและไม่บันทึก
LIMITS = {"fc_wave_height_max_m": (0, 20), "fc_wave_period_max_s": (0, 30),
          "fc_wind_speed_max_knots": (0, 150), "fc_rain_mm": (0, 1000)}


def check(doc):
    """คืนเหตุผลที่ไม่ควรบันทึก หรือ None ถ้าผ่าน (ค่า None บางตัวยอมรับ แต่ทุกตัวเป็น None ไม่ยอมรับ)"""
    vals = {k: doc[k] for k in LIMITS}
    if all(v is None for v in vals.values()):
        return "ทุกตัวแปรเป็น null"
    for k, v in vals.items():
        if v is not None and not LIMITS[k][0] <= v <= LIMITS[k][1]:
            return f"{k}={v} นอกช่วง {LIMITS[k]}"
    return None


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.load(r)
    return data if isinstance(data, list) else [data]


def fetch_once(db, dry_run=False):
    zones = list(db["fishing_zones"].find({}, {"fz_zone_id": 1, "fz_latitude": 1, "fz_longitude": 1,
                                              "fz_region.rg_region_id": 1}))
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ")  # รหัสรอบที่ดึง ทุกครั้งที่ดึงจะได้ค่าใหม่ จึงไม่เขียนทับรอบเก่า
    ops, planned, rejected = [], [], []
    for i in range(0, len(zones), CHUNK):
        part = zones[i:i + CHUNK]
        lat = ",".join(str(z["fz_latitude"]) for z in part)
        lon = ",".join(str(z["fz_longitude"]) for z in part)
        tz = "timezone=Asia%2FBangkok&forecast_days=" + str(DAYS)
        marine = get(f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}"
                     f"&daily=wave_height_max,wave_period_max&{tz}")
        wx = get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                 f"&daily=wind_speed_10m_max,precipitation_sum&wind_speed_unit=kn&{tz}")
        for z, m, w in zip(part, marine, wx):
            md, wd = m["daily"], w["daily"]
            issue = now.astimezone().strftime("%Y-%m-%d")  # วันที่ออกพยากรณ์ (เวลาท้องถิ่น)
            for k, day in enumerate(md["time"]):
                key = {"fc_zone_id": z["fz_zone_id"], "fc_forecast_date": day, "fc_run_id": run_id}
                doc = {
                    "fc_issue_date": issue,
                    "fc_region_id": z.get("fz_region", {}).get("rg_region_id"),
                    "fc_fetched_at": now,
                    "fc_wave_height_max_m": md["wave_height_max"][k],
                    "fc_wave_period_max_s": md["wave_period_max"][k],
                    "fc_wind_speed_max_knots": wd["wind_speed_10m_max"][k],
                    "fc_rain_mm": wd["precipitation_sum"][k],
                    "fc_source": "open-meteo",
                }
                why = check(doc)
                if why:
                    rejected.append((key, why))
                    continue
                ops.append(UpdateOne(key, {"$set": doc}, upsert=True))
                planned.append((key, doc))
    for key, why in rejected:
        print(f"  ข้าม {key['fc_zone_id']} {key['fc_forecast_date']}: {why}")
    if dry_run:
        prev = db[COLLECTION].find_one({"fc_run_id": {"$exists": True}}, {"fc_run_id": 1, "_id": 0},
                                       sort=[("fc_run_id", -1)])
        prev_id = prev["fc_run_id"] if prev else None
        old = {}
        if prev_id:
            old = {(d["fc_zone_id"], d["fc_forecast_date"]): d
                   for d in db[COLLECTION].find({"fc_run_id": prev_id}, {"_id": 0})}
        changed = sum(1 for k, d in planned
                      if (k["fc_zone_id"], k["fc_forecast_date"]) in old
                      and any(old[(k["fc_zone_id"], k["fc_forecast_date"])].get(f) != d[f] for f in LIMITS))
        print(f"[DRY-RUN ไม่ได้เขียนอะไร] ดึงได้ {len(planned)} แถว ข้าม {len(rejected)} แถว | "
              f"ถ้าบันทึกจะเพิ่มรอบใหม่ {run_id} จำนวน {len(planned)} แถว (ไม่ทับรอบเก่า) | "
              f"เทียบกับรอบล่าสุด {prev_id}: ค่าต่างกัน {changed} แถว")
        return
    res = db[COLLECTION].bulk_write(ops, ordered=False)
    print(f"[{now.astimezone():%Y-%m-%d %H:%M}] รอบ {run_id}: {len(zones)} โซน x {DAYS} วัน: "
          f"เพิ่ม {res.upserted_count}, อัปเดต {res.modified_count}, ข้าม(ไม่ผ่านการตรวจ) {len(rejected)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, metavar="MINUTES", help="ดึงซ้ำทุก N นาที")
    ap.add_argument("--dry-run", action="store_true", help="ดึงและตรวจข้อมูลแต่ไม่เขียน MongoDB")
    args = ap.parse_args()
    client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"), serverSelectionTimeoutMS=5000)
    db = client[os.getenv("MONGODB_DATABASE", "fishing_db")]
    if not args.dry_run:
        db[COLLECTION].create_index([("fc_zone_id", 1), ("fc_forecast_date", 1), ("fc_run_id", 1)], unique=True)
    while True:
        try:
            fetch_once(db, args.dry_run)
        except Exception as e:  # เครือข่ายหลุดชั่วคราวไม่ควรหยุดลูป
            print("ดึงไม่สำเร็จ:", e)
            if not args.loop:
                raise
        if not args.loop or args.dry_run:
            break
        time.sleep(args.loop * 60)


if __name__ == "__main__":
    main()
