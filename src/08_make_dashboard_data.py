import json, sys, pandas as pd
out = sys.argv[1]
d = "data/raw_snapshot/"
t = pd.read_parquet("data/processed/trips_features.parquet")
z = pd.read_parquet(d + "fishing_zones.parquet")
sea = pd.read_parquet(d + "sea_conditions.parquet")
def dump(name, df):
    df.to_json(f"{out}/{name}.json", orient="records", force_ascii=False, date_format="iso")
    print(name, len(df))

t["month"] = t.ft_departure_date.dt.strftime("%Y-%m-01")
m = t.groupby("month").agg(trips=("ft_trip_id","count"), catch_kg=("ft_total_catch_kg","sum"),
    revenue_thb=("ft_revenue_thb","sum"), profit_thb=("ft_profit_thb","sum")).reset_index()
m["avg_catch_kg"] = (m.catch_kg / m.trips).round(1)
dump("monthly", m.round(0).assign(avg_catch_kg=m.avg_catch_kg))

zz = t.groupby("fz_zone_id").agg(trips=("ft_trip_id","count"), catch_kg=("ft_total_catch_kg","sum"),
    profit_thb=("ft_profit_thb","sum")).reset_index()
zz = zz.merge(z[["fz_zone_id","fz_zone_name","fz_province"]], on="fz_zone_id")
zz["avg_catch_kg"] = (zz.catch_kg / zz.trips).round(1)
zz["avg_profit_thb"] = (zz.profit_thb / zz.trips).round(0)
dump("zones", zz[["fz_zone_id","fz_zone_name","fz_province","trips","catch_kg","avg_catch_kg","avg_profit_thb"]].round(0).assign(avg_catch_kg=zz.avg_catch_kg))

g = t.groupby("ft_vessel.ve_gear_type").agg(trips=("ft_trip_id","count"), avg_catch_kg=("ft_total_catch_kg","mean"),
    avg_profit_thb=("ft_profit_thb","mean")).reset_index().rename(columns={"ft_vessel.ve_gear_type":"gear"})
dump("gear", g.round(1))

# กิจกรรมการออกเรือ vs คลื่น D-1
cnt = t.groupby(["fz_zone_id","ft_departure_date"]).size().rename("n").reset_index()
p = sea.rename(columns={"sc_zone_id":"fz_zone_id","sc_date":"ft_departure_date"})
p = p[p.ft_departure_date.between(t.ft_departure_date.min(), t.ft_departure_date.max())].copy()
p["ft_departure_date"] += pd.Timedelta(days=1)
p = p.merge(cnt, how="left").fillna({"n":0})
p = p[p.ft_departure_date <= t.ft_departure_date.max()]
edges=[0,0.25,0.5,0.75,1.0,10]; labels=["<0.25","0.25-0.5","0.5-0.75","0.75-1.0",">1.0"]
p["band"]=pd.cut(p.sc_wave_height_max_m,edges,labels=labels,right=False)
w = p.groupby("band",observed=True).agg(zone_days=("n","size"), trips_per_zone_day=("n","mean")).reset_index()
w["band"]=w.band.astype(str); w["trips_per_zone_day"]=w.trips_per_zone_day.round(3)
dump("wave_activity", w)

res = [
 {"test":"ปริมาณจับรวม (kg)","metric":"MAE (kg)","without_env":330.43,"with_env":331.91},
 {"test":"ปริมาณจับต่อลูกเรือ","metric":"MAE (kg/คน)","without_env":24.27,"with_env":24.24},
 {"test":"จำนวนทริปต่อโซน-วัน","metric":"Poisson deviance","without_env":0.5857,"with_env":0.5885},
]
for r in res: r["change_pct"]=round((r["without_env"]-r["with_env"])/r["without_env"]*100,1)
dump("model_tests", pd.DataFrame(res))
