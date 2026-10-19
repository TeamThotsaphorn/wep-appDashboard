"""ส่งออกข้อมูลจาก MongoDB เป็น JSON สำหรับ web app ใน docs/ (GitHub Pages)

GitHub Pages เป็นเว็บ static เชื่อม MongoDB ในเครื่องไม่ได้ สคริปต์นี้จึงสรุปข้อมูลเป็นไฟล์ JSON
ใน docs/data/ แล้วค่อย commit + push เพื่ออัปเดตเว็บ

อ่านอย่างเดียว ไม่แก้ MongoDB และไม่ส่งออกข้อมูลระบุตัวบุคคล:
- ไม่มีชื่อกัปตัน ชื่อเรือ ชื่อบริษัทลูกค้า และลิงก์/ไฟล์รูปภาพ
- คำสั่งซื้อส่งออกสรุปเป็นรายเดือน/ประเทศ/ชนิดสัตว์น้ำเท่านั้น

ใช้งาน:  python -X utf8 src/11_export_web_data.py
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
OUT = Path("docs/data")
FORECAST_COLLECTION = os.getenv("FORECAST_COLLECTION", "weather_forcasting")

# ผลจาก src/06_compare_features.py และ src/07_trip_activity.py (รัน 2026-10-18)
# ถ้ารันโมเดลใหม่ ให้แก้ตัวเลขชุดนี้ด้วย
MODEL_TESTS = [
    {"test": "ปริมาณจับรวมต่อเที่ยว", "metric": "MAE (kg)", "without_env": 330.43, "with_env": 331.91, "folds_better": 2},
    {"test": "ปริมาณจับต่อลูกเรือ", "metric": "MAE (kg/คน)", "without_env": 24.27, "with_env": 24.24, "folds_better": 3},
    {"test": "จำนวนเที่ยวต่อโซน-วัน", "metric": "Poisson deviance", "without_env": 0.5857, "with_env": 0.5885, "folds_better": 1},
]
SINGLE_SPLIT = {"baseline_mae": 686.6, "model_mae": 328.0, "r2": 0.452,
                "train": "2022-01-01 – 2025-10-03", "test": "2025-10-03 – 2026-09-30"}


def r(x, n=1):
    return None if x is None else round(float(x), n)


def day(d):
    return d.strftime("%Y-%m-%d") if d else None


def dump(name, obj):
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  {path}  {path.stat().st_size / 1024:,.0f} KB")


def main():
    client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"), serverSelectionTimeoutMS=5000)
    db = client[os.getenv("MONGODB_DATABASE", "eec_seafood")]
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    # ---------- zones ----------
    zones = list(db.fishing_zones.find({}, {"_id": 0}).sort("fz_zone_id", 1))
    zone_region = {z["fz_zone_id"]: z["fz_region"]["rg_region_id"] for z in zones}
    regions = {z["fz_region"]["rg_region_id"]: z["fz_region"]["rg_region_name"] for z in zones}

    # ---------- trips (ไม่มีชื่อกัปตัน/ชื่อเรือ) ----------
    trips, species = [], {}
    sp_month = defaultdict(lambda: [0.0, 0.0])  # (species, month) -> kg, thb
    for t in db.fishing_trips.find({}, {"_id": 0}).sort("ft_departure_date", 1):
        trips.append([
            t["ft_trip_id"], day(t["ft_departure_date"]), day(t["ft_return_date"]),
            t["ft_zone"]["fz_zone_id"], t["ft_vessel"]["ve_gear_type"], t["ft_vessel"]["ve_size_gt"],
            t["ft_crew_count"], r(t["ft_total_catch_kg"]), r(t["ft_revenue_thb"], 0),
            r(t["ft_profit_thb"], 0), r(t["ft_costs"]["ft_total_cost"], 0),
        ])
        m = t["ft_departure_date"].strftime("%Y-%m")
        for c in t.get("ft_catches") or []:
            species[c["tc_species_id"]] = {"name": c["sp_name_th"], "category": c["sp_category"]}
            acc = sp_month[(c["tc_species_id"], m)]
            acc[0] += c["tc_weight_kg"] or 0
            acc[1] += c["tc_value_thb"] or 0
    dump("trips", {
        "columns": ["id", "departure", "return", "zone", "gear", "size_gt", "crew",
                    "catch_kg", "revenue_thb", "profit_thb", "cost_thb"],
        "rows": trips,
    })
    dump("species", {
        "species": species,
        "monthly": [[sp, m, r(kg), r(thb, 0)] for (sp, m), (kg, thb) in sorted(sp_month.items())],
        "columns": ["species", "month", "catch_kg", "value_thb"],
    })

    zone_out = [{
        "id": z["fz_zone_id"], "name": z["fz_zone_name"], "province": z.get("fz_province"),
        "region": z["fz_region"]["rg_region_id"], "lat": z["fz_latitude"], "lon": z["fz_longitude"],
        "depth_m": z["fz_depth_m"], "species": z.get("fz_main_species", []),
        "port": z.get("fz_nearest_port"), "station": z.get("fz_weather_station_id"),
    } for z in zones]
    dump("zones", {"regions": regions, "zones": zone_out})

    # ---------- สภาพแวดล้อมย้อนหลัง: เฉลี่ยรายเดือนต่อภูมิภาค ----------
    sea = db.sea_conditions.aggregate([
        {"$group": {
            "_id": {"r": "$sc_region_id", "m": {"$dateToString": {"format": "%Y-%m", "date": "$sc_date"}}},
            "wave": {"$avg": "$sc_wave_height_max_m"}, "wave_max": {"$max": "$sc_wave_height_max_m"},
            "sst": {"$avg": "$sc_sst_avg_c"}, "current": {"$avg": "$sc_current_speed_avg_kmh"},
            "n": {"$sum": 1},
        }},
        {"$sort": {"_id.m": 1, "_id.r": 1}},
    ])
    wx = db.weather_reports.aggregate([
        {"$group": {
            "_id": {"r": "$wr_region_id", "m": {"$dateToString": {"format": "%Y-%m", "date": "$wr_observed_date"}}},
            "wind": {"$avg": "$wr_max_wind_speed_knots"}, "rain": {"$avg": "$wr_rain_mm"},
            "temp": {"$avg": "$wr_max_temp_c"}, "n": {"$sum": 1},
        }},
        {"$sort": {"_id.m": 1, "_id.r": 1}},
    ])
    dump("environment", {
        "sea": [[s["_id"]["r"], s["_id"]["m"], r(s["wave"], 2), r(s["wave_max"], 2), r(s["sst"], 2),
                 r(s["current"], 2), s["n"]] for s in sea],
        "sea_columns": ["region", "month", "wave_avg_m", "wave_max_m", "sst_avg_c", "current_avg_kmh", "days"],
        "weather": [[w["_id"]["r"], w["_id"]["m"], r(w["wind"], 2), r(w["rain"], 2), r(w["temp"], 2), w["n"]]
                    for w in wx],
        "weather_columns": ["region", "month", "wind_avg_kn", "rain_avg_mm", "temp_max_avg_c", "reports"],
    })

    # ---------- พยากรณ์ (รอบล่าสุด + ประวัติจำนวนรอบ) ----------
    fc = db[FORECAST_COLLECTION]
    runs = sorted(fc.distinct("fc_run_id"), reverse=True)
    latest = runs[0] if runs else None
    rows = list(fc.find({"fc_run_id": latest}, {"_id": 0}).sort([("fc_zone_id", 1), ("fc_forecast_date", 1)])) if latest else []
    dump("forecast", {
        "run_id": latest, "runs_stored": len(runs), "recent_runs": runs[:14],
        "fetched_at": rows[0]["fc_fetched_at"].replace(tzinfo=timezone.utc).isoformat() if rows else None,
        "source": rows[0].get("fc_source") if rows else None,
        "columns": ["zone", "date", "wave_m", "period_s", "wind_kn", "rain_mm"],
        "rows": [[x["fc_zone_id"], x["fc_forecast_date"], x.get("fc_wave_height_max_m"),
                  x.get("fc_wave_period_max_s"), x.get("fc_wind_speed_max_knots"), x.get("fc_rain_mm")] for x in rows],
    })

    # ---------- ส่งออก (ไม่มีชื่อลูกค้า) ----------
    orders = list(db.export_orders.find({}, {"_id": 0, "eo_customer.cu_company_name": 0}))
    ex_month = defaultdict(lambda: [0, 0.0, 0.0])
    ex_country = defaultdict(lambda: [0, 0.0, 0.0])
    ex_species = defaultdict(lambda: [0.0, 0.0])
    for o in orders:
        m = o["eo_order_date"].strftime("%Y-%m")
        c = o["eo_customer"]["cu_country"]
        for acc in (ex_month[m], ex_country[c]):
            acc[0] += 1
            acc[1] += o.get("eo_total_weight_kg") or 0
            acc[2] += o.get("eo_total_value_thb") or 0
        for it in o.get("eo_items") or []:
            a = ex_species[it.get("sp_name_th") or it.get("oi_species_id")]
            a[0] += it.get("oi_weight_kg") or 0
            a[1] += (it.get("oi_value_usd") or 0) * (o.get("eo_exchange_rate") or 0)
    dump("exports", {
        "monthly": [[m, n, r(kg), r(thb, 0)] for m, (n, kg, thb) in sorted(ex_month.items())],
        "monthly_columns": ["month", "orders", "weight_kg", "value_thb"],
        "countries": sorted([[c, n, r(kg), r(thb, 0)] for c, (n, kg, thb) in ex_country.items()], key=lambda x: -x[3]),
        "country_columns": ["country", "orders", "weight_kg", "value_thb"],
        "species": sorted([[s, r(kg), r(thb, 0)] for s, (kg, thb) in ex_species.items()], key=lambda x: -x[2]),
        "species_columns": ["species", "weight_kg", "value_thb"],
    })

    # ---------- กิจกรรมออกเรือเทียบคลื่นวันก่อนหน้า ----------
    trip_days = defaultdict(int)
    for t in trips:
        trip_days[(t[3], t[1])] += 1
    first, last = trips[0][1], trips[-1][1]
    bands = [(0, .25, "<0.25"), (.25, .5, "0.25–0.5"), (.5, .75, "0.5–0.75"), (.75, 1.0, "0.75–1.0"), (1.0, 99, ">1.0")]
    acc = {b[2]: [0, 0] for b in bands}
    for s in db.sea_conditions.find({}, {"_id": 0, "sc_zone_id": 1, "sc_date": 1, "sc_wave_height_max_m": 1}):
        nxt = day(s["sc_date"] + timedelta(days=1))  # คลื่นวันนี้ = ข้อมูล D-1 ของวันรุ่งขึ้น
        w = s.get("sc_wave_height_max_m")
        if w is None or not (first <= nxt <= last):
            continue
        for lo, hi, name in bands:
            if lo <= w < hi:
                acc[name][0] += 1
                acc[name][1] += trip_days.get((s["sc_zone_id"], nxt), 0)
                break
    dump("model", {
        "tests": MODEL_TESTS, "single_split": SINGLE_SPLIT,
        "wave_activity": [{"band": b, "zone_days": n, "trips_per_zone_day": round(k / n, 3) if n else None}
                          for b, (n, k) in acc.items()],
    })

    # ---------- meta ----------
    counts = {n: db[n].estimated_document_count() for n in [
        "fishing_trips", "fishing_zones", "weather_reports", "sea_conditions",
        "export_orders", "catch_images", FORECAST_COLLECTION]}
    dump("meta", {
        "generated_at": now.isoformat(), "database": db.name, "counts": counts,
        "trip_range": [first, last], "forecast_collection": FORECAST_COLLECTION,
    })
    client.close()


if __name__ == "__main__":
    main()
