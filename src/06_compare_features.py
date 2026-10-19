import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit

df = pd.read_parquet("data/processed/trips_features.parquet").sort_values("ft_departure_date").reset_index(drop=True)
df["month"] = df.ft_departure_date.dt.month
df["zone"] = df.fz_zone_id.str[3:].astype(int)
df["gear"] = df["ft_vessel.ve_gear_type"].astype("category").cat.codes
df["catch_per_crew"] = df.ft_total_catch_kg / df.ft_crew_count

env = [c for c in df.columns if c.endswith(("_d1", "_mean3d"))]
base = ["fz_depth_m", "fz_latitude", "fz_longitude", "ft_crew_count",
        "ft_vessel.ve_size_gt", "ft_captain.cp_years_experience", "month", "zone", "gear"]

def cv(features, target):
    maes = []
    for tr, te in TimeSeriesSplit(n_splits=5).split(df):
        usable = [c for c in features if df.loc[tr, c].notna().any()]  # SST ว่างทั้งหมดในช่วงต้น
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=0)
        m.fit(df.loc[tr, usable], df.loc[tr, target])
        maes.append(mean_absolute_error(df.loc[te, target], m.predict(df.loc[te, usable])))
    return pd.Series(maes)

for target in ["ft_total_catch_kg", "catch_per_crew"]:
    a, b = cv(base, target), cv(base + env, target)
    print(f"\nเป้าหมาย: {target}  (MAE ต่อ fold, 5 fold ตามเวลา)")
    print(f"  ไม่มีอากาศ/ทะเล: {a.round(1).tolist()}  เฉลี่ย {a.mean():.2f}")
    print(f"  มีอากาศ/ทะเล:    {b.round(1).tolist()}  เฉลี่ย {b.mean():.2f}")
    print(f"  ดีขึ้น {(a.mean()-b.mean())/a.mean()*100:+.1f}%  (fold ที่ดีขึ้น {(b<a).sum()}/5)")
