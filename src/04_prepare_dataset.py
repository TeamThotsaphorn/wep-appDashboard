from pathlib import Path
import pandas as pd

input_dir = Path("data/raw_snapshot")
output_path = Path("data/processed/trips_features.parquet")
required_files = [
    "fishing_trips.parquet", "fishing_zones.parquet",
    "weather_reports.parquet", "sea_conditions.parquet",
]
missing_files = [name for name in required_files if not (input_dir / name).exists()]
if missing_files:
    print("ยังขาดไฟล์เหล่านี้:")
    for name in missing_files:
        print("-", name)
    print("\nตั้งค่า COLLECTIONS ใน .env แล้วรัน src/02_extract_data.py")
    raise SystemExit(1)

trips, zones, weather, sea = (pd.read_parquet(input_dir / n) for n in required_files)

SEA_COLS = ["sc_wave_height_max_m", "sc_swell_height_max_m", "sc_wave_period_max_s",
            "sc_sst_avg_c", "sc_current_speed_avg_kmh"]
WX_COLS = ["wr_max_wind_speed_knots", "wr_rain_mm", "wr_max_temp_c", "wr_humidity_pct"]


def add_lag_features(df, key, date_col, cols):
    """ฟีเจอร์ที่ทราบก่อนวันออกเรือ: ค่าวัน D-1 และค่าเฉลี่ย D-3..D-1 (ไม่รวมวัน D)"""
    # ทำบนปฏิทินรายวันต่อกลุ่ม เพื่อให้ shift ตรงกับวันจริงแม้มีวันขาด
    parts = []
    for k, g in df.groupby(key):
        g = g.set_index(date_col)[cols].asfreq("D")
        lag = g.shift(1)
        res = lag.add_suffix("_d1")
        res = res.join(lag.rolling(3, min_periods=1).mean().add_suffix("_mean3d"))
        res[key] = k
        parts.append(res.reset_index())
    return pd.concat(parts, ignore_index=True)


sea_f = add_lag_features(sea, "sc_zone_id", "sc_date", SEA_COLS)
wx_f = add_lag_features(weather, "wr_station_id", "wr_observed_date", WX_COLS)

zone_cols = ["fz_zone_id", "fz_weather_station_id", "fz_depth_m", "fz_latitude", "fz_longitude"]
trips = trips.drop(columns=["_id", "ft_catches"]).rename(columns={"ft_zone.fz_zone_id": "fz_zone_id"})
df = trips.merge(zones[zone_cols], on="fz_zone_id", how="left", validate="m:1")
df = df.merge(sea_f, left_on=["fz_zone_id", "ft_departure_date"],
              right_on=["sc_zone_id", "sc_date"], how="left", validate="m:1")
df = df.merge(wx_f, left_on=["fz_weather_station_id", "ft_departure_date"],
              right_on=["wr_station_id", "wr_observed_date"], how="left", validate="m:1")
df = df.drop(columns=["sc_zone_id", "sc_date", "wr_station_id", "wr_observed_date"])

assert len(df) == len(trips), "จำนวนแถวเปลี่ยนหลัง join"
output_path.parent.mkdir(parents=True, exist_ok=True)
df.to_parquet(output_path, index=False)

print(f"บันทึก {output_path}: {len(df):,} rows, {len(df.columns)} columns")
feat = [c for c in df.columns if c.endswith(("_d1", "_mean3d"))]
print("\nสัดส่วนค่าว่างของฟีเจอร์:")
print(df[feat].isna().mean().round(3).to_string())
print("""
หมายเหตุ:
- ฟีเจอร์อากาศ/ทะเลใช้เฉพาะข้อมูลก่อนวันออกเรือ (D-1 และค่าเฉลี่ย D-3..D-1)
- คอลัมน์ผลลัพธ์ (ft_total_catch_kg, ft_revenue_thb, ft_profit_thb, ft_return_date, ft_costs.*)
  ห้ามใช้เป็นตัวแปรทำนาย
- ยังไม่มี label 'ควร/ไม่ควรออกเรือ' ในข้อมูล
""")
