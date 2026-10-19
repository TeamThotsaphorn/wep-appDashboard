"""ย้าย key ของ weather_forcasting ให้เก็บ "ทุกรอบที่ดึง" แทนที่จะเก็บวันละรอบ

เดิม: unique (fc_zone_id, fc_forecast_date, fc_issue_date)  -> ดึงซ้ำในวันเดียวกันจะเขียนทับ
ใหม่: unique (fc_zone_id, fc_forecast_date, fc_run_id)      -> fc_run_id = เวลาที่ดึง (UTC) เช่น 20261018T150646Z

ขั้นตอน (ทำตามลำดับนี้ เพื่อไม่ให้มีช่วงที่ไม่มี unique index):
  1. เติม fc_run_id ให้เอกสารเดิมที่ยังไม่มี โดยคำนวณจาก fc_fetched_at ของเอกสารนั้นเอง (ไม่แก้ฟิลด์อื่น)
  2. สร้าง unique index ใหม่
  3. ลบ unique index เดิม

ใช้งาน:  python src/10_migrate_forecast_key.py            # dry-run: แสดงสิ่งที่จะทำ ไม่เขียนอะไร
         python src/10_migrate_forecast_key.py --apply    # ทำจริง
รันซ้ำได้อย่างปลอดภัย (ขั้นที่ทำแล้วจะถูกข้าม)
"""
import argparse
import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
COLLECTION = os.getenv("FORECAST_COLLECTION", "weather_forcasting")
OLD_KEYS = [("fc_zone_id", 1), ("fc_forecast_date", 1), ("fc_issue_date", 1)]
NEW_KEYS = [("fc_zone_id", 1), ("fc_forecast_date", 1), ("fc_run_id", 1)]


def run_id(dt):
    return dt.strftime("%Y%m%dT%H%M%SZ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="ทำจริง (ถ้าไม่ใส่ = dry-run)")
    args = ap.parse_args()
    db = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"),
                     serverSelectionTimeoutMS=5000)[os.getenv("MONGODB_DATABASE", "eec_seafood")]
    coll = db[COLLECTION]
    mode = "APPLY" if args.apply else "DRY-RUN (ไม่เขียนอะไร)"
    print(f"[{mode}] collection={COLLECTION} เอกสารทั้งหมด={coll.count_documents({})}")

    # 1) backfill
    missing = coll.count_documents({"fc_run_id": {"$exists": False}})
    no_fetched = coll.count_documents({"fc_run_id": {"$exists": False}, "fc_fetched_at": {"$in": [None]}})
    print(f"1) เอกสารที่ยังไม่มี fc_run_id: {missing} (ในนั้นไม่มี fc_fetched_at: {no_fetched})")
    if no_fetched:
        raise SystemExit("หยุด: มีเอกสารที่ไม่มี fc_fetched_at จึงคำนวณ fc_run_id ไม่ได้ ตรวจข้อมูลก่อน")
    groups = list(coll.aggregate([{"$match": {"fc_run_id": {"$exists": False}}},
                                  {"$group": {"_id": "$fc_fetched_at", "n": {"$sum": 1}}}]))
    for g in groups:
        print(f"   fc_fetched_at={g['_id']} -> fc_run_id={run_id(g['_id'])}  ({g['n']} แถว)")
        if args.apply:
            r = coll.update_many({"fc_run_id": {"$exists": False}, "fc_fetched_at": g["_id"]},
                                 {"$set": {"fc_run_id": run_id(g["_id"])}})
            print(f"   แก้แล้ว {r.modified_count} แถว")

    # 2) new index, 3) drop old
    idx = {tuple(v["key"].items()) if isinstance(v["key"], dict) else tuple(v["key"]): n
           for n, v in coll.index_information().items()}
    old_name = idx.get(tuple(OLD_KEYS))
    new_name = idx.get(tuple(NEW_KEYS))
    print(f"2) index ใหม่: {'มีอยู่แล้ว ' + new_name if new_name else 'ยังไม่มี -> จะสร้าง'}")
    if args.apply and not new_name:
        print("   สร้าง:", coll.create_index(NEW_KEYS, unique=True))
    print(f"3) index เดิม: {'พบ ' + old_name + ' -> จะลบ' if old_name else 'ไม่มี (ข้าม)'}")
    if args.apply and old_name:
        remaining = coll.count_documents({"fc_run_id": {"$exists": False}})
        if remaining:
            raise SystemExit(f"หยุด: ยังเหลือ {remaining} แถวที่ไม่มี fc_run_id ไม่ลบ index เดิม")
        coll.drop_index(old_name)
        print("   ลบแล้ว")
    if args.apply:
        print("index ปัจจุบัน:", list(coll.index_information()))


if __name__ == "__main__":
    main()
