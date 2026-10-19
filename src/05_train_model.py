from pathlib import Path
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

df = pd.read_parquet("data/processed/trips_features.parquet").sort_values("ft_departure_date")
target = "ft_total_catch_kg"

# ตัวแปรที่ทราบก่อนออกเรือเท่านั้น (ไม่รวม return_date, revenue, profit, costs)
features = [c for c in df.columns if c.endswith(("_d1", "_mean3d"))] + [
    "fz_depth_m", "fz_latitude", "fz_longitude", "ft_crew_count",
    "ft_vessel.ve_size_gt", "ft_captain.cp_years_experience"]
df["month"] = df.ft_departure_date.dt.month
df["zone"] = df.fz_zone_id.str[3:].astype(int)
df["gear"] = df["ft_vessel.ve_gear_type"].astype("category").cat.codes
features += ["month", "zone", "gear"]

# แบ่งตามเวลา: 80% แรกฝึก 20% หลังทดสอบ
cut = int(len(df) * 0.8)
train, test = df.iloc[:cut], df.iloc[cut:]
print(f"train {len(train):,} ({train.ft_departure_date.min():%Y-%m-%d}..{train.ft_departure_date.max():%Y-%m-%d})")
print(f"test  {len(test):,} ({test.ft_departure_date.min():%Y-%m-%d}..{test.ft_departure_date.max():%Y-%m-%d})")

model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=0)
model.fit(train[features], train[target])
pred = model.predict(test[features])
base = pd.Series(train[target].mean(), index=test.index)

print(f"\nbaseline (ค่าเฉลี่ย) MAE {mean_absolute_error(test[target], base):,.1f} kg")
print(f"model MAE {mean_absolute_error(test[target], pred):,.1f} kg  R2 {r2_score(test[target], pred):.3f}")

from sklearn.inspection import permutation_importance
imp = permutation_importance(model, test[features], test[target], n_repeats=5, random_state=0)
print("\nความสำคัญของตัวแปร (top 10):")
print(pd.Series(imp.importances_mean, index=features).sort_values(ascending=False).head(10).round(2).to_string())
