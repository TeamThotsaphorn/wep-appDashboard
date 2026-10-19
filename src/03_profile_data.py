from pathlib import Path
import pandas as pd

input_dir = Path("data/raw_snapshot")
files = sorted(input_dir.glob("*.parquet"))
if not files:
    print("ยังไม่พบไฟล์ Parquet ใน data/raw_snapshot/")
    print("ให้รัน python src/02_extract_data.py ก่อน")
    raise SystemExit(0)

for path in files:
    df = pd.read_parquet(path)
    print("\n" + "=" * 70)
    print(f"ไฟล์: {path.name}")
    print(f"จำนวนแถว: {len(df):,}")
    print(f"จำนวนคอลัมน์: {len(df.columns):,}")
    print("\nชนิดข้อมูล:")
    print(df.dtypes.to_string())
    missing = df.isna().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    print("\nจำนวนค่าว่างต่อคอลัมน์:")
    print(missing.to_string() if not missing.empty else "ไม่พบค่าว่างจากการตรวจพื้นฐาน")
    print("\nชื่อคอลัมน์:")
    print(", ".join(map(str, df.columns)))
