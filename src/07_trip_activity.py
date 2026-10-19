import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_poisson_deviance
from sklearn.model_selection import TimeSeriesSplit

d = "data/raw_snapshot/"
trips = pd.read_parquet("data/processed/trips_features.parquet")
zones = pd.read_parquet(d + "fishing_zones.parquet")
sea = pd.read_parquet(d + "sea_conditions.parquet")

# ตารางโซน x วัน: จำนวนทริปที่ออกเรือ (ทุกวันที่มีข้อมูลทะเลของโซนนั้น)
cnt = trips.groupby(["fz_zone_id", "ft_departure_date"]).size().rename("n_trips").reset_index()
panel = sea[["sc_zone_id", "sc_date"]].rename(columns={"sc_zone_id": "fz_zone_id", "sc_date": "ft_departure_date"})
panel = panel[panel.ft_departure_date.between(trips.ft_departure_date.min(), trips.ft_departure_date.max())]
panel = panel.merge(cnt, how="left").fillna({"n_trips": 0})

# ฟีเจอร์ D-1 ชุดเดียวกับที่ใช้ใน trips_features (ดึงจากทริปไม่ได้ครบทุกวัน จึงคำนวณใหม่)
w = pd.read_parquet(d + "weather_reports.parquet")
SEA = ["sc_wave_height_max_m", "sc_swell_height_max_m", "sc_wave_period_max_s", "sc_current_speed_avg_kmh"]
WX = ["wr_max_wind_speed_knots", "wr_rain_mm"]
s1 = sea[["sc_zone_id", "sc_date"] + SEA].copy()
s1["sc_date"] += pd.Timedelta(days=1)
w1 = w[["wr_station_id", "wr_observed_date"] + WX].copy()
w1["wr_observed_date"] += pd.Timedelta(days=1)
panel = panel.merge(zones[["fz_zone_id", "fz_weather_station_id"]], how="left")
panel = panel.merge(s1, left_on=["fz_zone_id", "ft_departure_date"], right_on=["sc_zone_id", "sc_date"], how="left")
panel = panel.merge(w1, left_on=["fz_weather_station_id", "ft_departure_date"],
                    right_on=["wr_station_id", "wr_observed_date"], how="left")
panel = panel.sort_values("ft_departure_date").reset_index(drop=True)
panel["month"] = panel.ft_departure_date.dt.month
panel["dow"] = panel.ft_departure_date.dt.dayofweek
panel["zone"] = panel.fz_zone_id.str[3:].astype(int)
env = SEA + WX
base = ["month", "dow", "zone"]
print(f"zone-day {len(panel):,}  ค่าเฉลี่ยทริป/วัน {panel.n_trips.mean():.3f}  สัดส่วนวันที่ไม่มีทริป {(panel.n_trips==0).mean():.1%}")

print("\nทริปเฉลี่ยต่อโซน-วัน แยกตามควอไทล์ของคลื่นและลม (D-1):")
for c in ["sc_wave_height_max_m", "wr_max_wind_speed_knots"]:
    q = pd.qcut(panel[c], 5, duplicates="drop")
    print(panel.groupby(q, observed=True).n_trips.mean().round(3).to_string(), "\n")

def cv(features):
    out = []
    for tr, te in TimeSeriesSplit(n_splits=5).split(panel):
        m = HistGradientBoostingRegressor(loss="poisson", max_iter=200, learning_rate=0.05, random_state=0)
        m.fit(panel.loc[tr, features], panel.loc[tr, "n_trips"])
        p = m.predict(panel.loc[te, features]).clip(1e-6)
        out.append(mean_poisson_deviance(panel.loc[te, "n_trips"], p))
    return pd.Series(out)

a, b = cv(base), cv(base + env)
print("Poisson deviance ต่อ fold (ต่ำกว่า=ดีกว่า)")
print("  ไม่มีอากาศ/ทะเล:", a.round(4).tolist(), f"เฉลี่ย {a.mean():.4f}")
print("  มีอากาศ/ทะเล:   ", b.round(4).tolist(), f"เฉลี่ย {b.mean():.4f}")
print(f"  ดีขึ้น {(a.mean()-b.mean())/a.mean()*100:+.1f}%  (fold ที่ดีขึ้น {(b<a).sum()}/5)")
