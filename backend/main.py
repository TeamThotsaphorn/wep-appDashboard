"""EEC Seafood read-only API (FastAPI + PyMongo).

Run from the project root:
    .\\.venv\\Scripts\\python.exe -m uvicorn backend.main:app --reload --port 8000

Config comes from .env: MONGODB_URI, MONGODB_DATABASE, optional CORS_ORIGINS
(comma separated). Field names below come from backend/inspect_mongodb_schema.py output.
Every endpoint only reads; nothing writes to MongoDB.
"""
import os
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DB_NAME = os.getenv("MONGODB_DATABASE", "eec_seafood")
FORECAST_COLLECTION = os.getenv("FORECAST_COLLECTION", "weather_forcasting")
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8080,http://127.0.0.1:8080",
    ).split(",")
    if o.strip()
]
MAX_PAGE_SIZE = 100

_client: Optional[MongoClient] = None


def get_db():
    """Lazy client so the API can start (and report /health) even if MongoDB is down."""
    global _client
    if _client is None:
        _client = MongoClient(
            os.getenv("MONGODB_URI", "mongodb://localhost:27017/"),
            serverSelectionTimeoutMS=3000,
        )
    return _client[DB_NAME]


app = FastAPI(title="EEC Seafood API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(PyMongoError)
async def mongo_error_handler(request: Request, exc: PyMongoError):
    # Do not echo the exception text: it can contain host/URI details.
    return JSONResponse(
        status_code=503,
        content={"detail": "เชื่อมต่อ MongoDB ไม่ได้ กรุณาตรวจสอบว่า MongoDB กำลังทำงานอยู่"},
    )


# ---------- helpers ----------

def day_range(date_from: Optional[date], date_to: Optional[date], field: str) -> dict:
    """Inclusive date range on a datetime field stored as naive midnight values."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from ต้องไม่อยู่หลัง date_to")
    cond: dict[str, Any] = {}
    if date_from:
        cond["$gte"] = datetime.combine(date_from, time.min)
    if date_to:
        cond["$lte"] = datetime.combine(date_to, time.max)
    return {field: cond} if cond else {}


def iso_range(first: Any, last: Any) -> dict:
    return {
        "first": first.isoformat() if first else None,
        "last": last.isoformat() if last else None,
    }


def page_response(db_coll, query: dict, projection: dict, sort: list, page: int, page_size: int) -> dict:
    total = db_coll.count_documents(query)
    items = list(
        db_coll.find(query, {**projection, "_id": 0})
        .sort(sort)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    return {"page": page, "page_size": page_size, "total": total, "items": items}


# ---------- models ----------

class Health(BaseModel):
    status: str
    mongodb: str
    database: str
    checked_at: datetime


class Page(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[dict[str, Any]]


# ---------- endpoints ----------

@app.get("/")
def root():
    return {"service": "EEC Seafood API", "status": "running", "docs": "/docs"}


@app.get("/health", response_model=Health)
def health():
    now = datetime.now(timezone.utc)
    try:
        get_db().client.admin.command("ping")
    except PyMongoError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "mongodb": "unavailable",
                "database": DB_NAME,
                "checked_at": now.isoformat(),
            },
        )
    return Health(status="ok", mongodb="connected", database=DB_NAME, checked_at=now)


@app.get("/api/summary")
def summary():
    db = get_db()
    names = [
        "fishing_trips", "fishing_zones", "weather_reports", "sea_conditions",
        "export_orders", "catch_images", FORECAST_COLLECTION,
    ]
    counts = {n: db[n].count_documents({}) for n in names}
    agg = list(db["fishing_trips"].aggregate([
        {"$group": {
            "_id": None,
            "total_catch_kg": {"$sum": "$ft_total_catch_kg"},
            "total_revenue_thb": {"$sum": "$ft_revenue_thb"},
            "total_profit_thb": {"$sum": "$ft_profit_thb"},
            "first_departure": {"$min": "$ft_departure_date"},
            "last_departure": {"$max": "$ft_departure_date"},
        }}
    ]))
    t = agg[0] if agg else {}
    return {
        "counts": counts,
        "trips": {
            "total_catch_kg": t.get("total_catch_kg"),
            "total_revenue_thb": t.get("total_revenue_thb"),
            "total_profit_thb": t.get("total_profit_thb"),
            "departure_range": iso_range(t.get("first_departure"), t.get("last_departure")),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


TRIP_FIELDS = {
    "ft_trip_id": 1, "ft_departure_date": 1, "ft_return_date": 1, "ft_crew_count": 1,
    "ft_total_catch_kg": 1, "ft_revenue_thb": 1, "ft_profit_thb": 1,
    "ft_vessel.ve_vessel_name": 1, "ft_vessel.ve_gear_type": 1, "ft_vessel.ve_size_gt": 1,
    "ft_zone.fz_zone_id": 1, "ft_zone.fz_zone_name": 1,
}


@app.get("/api/trips", response_model=Page)
def trips(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    zone_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    query = day_range(date_from, date_to, "ft_departure_date")
    if zone_id:
        query["ft_zone.fz_zone_id"] = zone_id
    return page_response(get_db()["fishing_trips"], query, TRIP_FIELDS,
                         [("ft_departure_date", -1), ("ft_trip_id", 1)], page, page_size)


@app.get("/api/trips/monthly")
def trips_monthly(
    zone_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    query = day_range(date_from, date_to, "ft_departure_date")
    if zone_id:
        query["ft_zone.fz_zone_id"] = zone_id
    rows = get_db()["fishing_trips"].aggregate([
        {"$match": query},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m", "date": "$ft_departure_date"}},
            "trips": {"$sum": 1},
            "total_catch_kg": {"$sum": "$ft_total_catch_kg"},
        }},
        {"$sort": {"_id": 1}},
    ])
    return {"items": [{"month": r["_id"], "trips": r["trips"], "total_catch_kg": r["total_catch_kg"]}
                      for r in rows]}


ZONE_FIELDS = {
    "fz_zone_id": 1, "fz_zone_name": 1, "fz_province": 1, "fz_region": 1,
    "fz_latitude": 1, "fz_longitude": 1, "fz_depth_m": 1, "fz_main_species": 1,
    "fz_nearest_port": 1, "fz_weather_station_id": 1,
}


@app.get("/api/zones")
def zones():
    items = list(get_db()["fishing_zones"].find({}, {**ZONE_FIELDS, "_id": 0}).sort("fz_zone_id", 1))
    return {"total": len(items), "items": items}


SEA_FIELDS = {
    "sc_zone_id": 1, "sc_date": 1, "sc_wave_height_max_m": 1, "sc_swell_height_max_m": 1,
    "sc_wave_direction_deg": 1, "sc_wave_period_max_s": 1, "sc_sst_avg_c": 1,
    "sc_current_speed_avg_kmh": 1,
}
WEATHER_FIELDS = {
    "wr_station_id": 1, "wr_station_name": 1, "wr_province": 1, "wr_observed_date": 1,
    "wr_rain_mm": 1, "wr_max_temp_c": 1, "wr_min_temp_c": 1, "wr_max_wind_speed_knots": 1,
    "wr_max_wind_direction_deg": 1, "wr_humidity_pct": 1,
}


@app.get("/api/environment")
def environment(
    zone_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(30, ge=1, le=MAX_PAGE_SIZE),
):
    """Observed history only (weather_reports + sea_conditions), newest first.
    Weather rows are matched to a zone through fishing_zones.fz_weather_station_id."""
    db = get_db()
    sea_q = day_range(date_from, date_to, "sc_date")
    wx_q = day_range(date_from, date_to, "wr_observed_date")
    station_note = None
    if zone_id:
        sea_q["sc_zone_id"] = zone_id
        zone = db["fishing_zones"].find_one({"fz_zone_id": zone_id}, {"fz_weather_station_id": 1})
        if zone is None:
            raise HTTPException(404, f"ไม่พบพื้นที่ {zone_id}")
        station = zone.get("fz_weather_station_id")
        if station:
            wx_q["wr_station_id"] = station
        else:
            wx_q["wr_station_id"] = None  # zone has no station: return no weather rows
            station_note = "พื้นที่นี้ไม่มีสถานีอากาศในข้อมูล"

    def block(coll, q, fields, date_field):
        total = db[coll].count_documents(q)
        items = list(db[coll].find(q, {**fields, "_id": 0}).sort(date_field, -1).limit(limit))
        return {"total": total, "returned": len(items), "items": items}

    return {
        "kind": "observed",
        "weather": {**block("weather_reports", wx_q, WEATHER_FIELDS, "wr_observed_date"),
                    "note": station_note},
        "sea": block("sea_conditions", sea_q, SEA_FIELDS, "sc_date"),
    }


FORECAST_FIELDS = {
    "fc_zone_id": 1, "fc_region_id": 1, "fc_run_id": 1, "fc_issue_date": 1, "fc_forecast_date": 1,
    "fc_fetched_at": 1, "fc_wave_height_max_m": 1, "fc_wave_period_max_s": 1,
    "fc_wind_speed_max_knots": 1, "fc_rain_mm": 1, "fc_source": 1,
}


@app.get("/api/forecasts")
def forecasts(
    zone_id: Optional[str] = None,
    run_id: Optional[str] = Query(None, pattern=r"^\d{8}T\d{6}Z$"),
    limit: int = Query(100, ge=1, le=300),
):
    """Forecast rows (not observations) from ONE fetch run. Every fetch is kept (fc_run_id),
    so without run_id this returns the latest run; pass run_id to read an older one."""
    coll = get_db()[FORECAST_COLLECTION]
    runs = sorted(coll.distinct("fc_run_id"), reverse=True)
    if run_id is None:
        run_id = runs[0] if runs else None
    elif run_id not in runs:
        raise HTTPException(404, f"ไม่พบรอบพยากรณ์ {run_id}")
    if run_id is None:
        return {"kind": "forecast", "run_id": None, "issue_date": None, "runs": [], "total": 0, "items": []}
    query: dict[str, Any] = {"fc_run_id": run_id}
    if zone_id:
        query["fc_zone_id"] = zone_id
    total = coll.count_documents(query)
    items = list(coll.find(query, {**FORECAST_FIELDS, "_id": 0})
                 .sort([("fc_zone_id", 1), ("fc_forecast_date", 1)]).limit(limit))
    issue = items[0]["fc_issue_date"] if items else None
    return {"kind": "forecast", "run_id": run_id, "issue_date": issue, "runs": runs[:30],
            "runs_stored": len(runs), "total": total, "items": items}


@app.get("/api/exports/summary")
def exports_summary():
    rows = list(get_db()["export_orders"].aggregate([
        {"$group": {
            "_id": None,
            "orders": {"$sum": 1},
            "total_weight_kg": {"$sum": "$eo_total_weight_kg"},
            "total_value_usd": {"$sum": "$eo_total_value_usd"},
            "total_value_thb": {"$sum": "$eo_total_value_thb"},
            "first_order": {"$min": "$eo_order_date"},
            "last_order": {"$max": "$eo_order_date"},
        }}
    ]))
    r = rows[0] if rows else {}
    return {
        "orders": r.get("orders", 0),
        "total_weight_kg": r.get("total_weight_kg"),
        "total_value_usd": r.get("total_value_usd"),
        "total_value_thb": r.get("total_value_thb"),
        "order_range": iso_range(r.get("first_order"), r.get("last_order")),
    }


@app.get("/api/images")
def images():
    """Image metadata only. File ids/URLs are reduced to a has_url flag."""
    items = list(get_db()["catch_images"].find({}, {
        "ci_image_id": 1, "ci_trip_id": 1, "ci_species_ids": 1, "ci_stage": 1,
        "ci_taken_at": 1, "ci_description": 1, "ci_file_name": 1, "ci_file_url": 1,
        "ci_mime_type": 1, "ci_file_size_kb": 1, "_id": 0,
    }).sort("ci_taken_at", -1))
    for it in items:
        it["has_url"] = bool(it.pop("ci_file_url", None))
    return {"total": len(items), "items": items}
