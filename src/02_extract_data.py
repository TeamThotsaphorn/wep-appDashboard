import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from bson import ObjectId
from bson.decimal128 import Decimal128
from pymongo import MongoClient

load_dotenv()
uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
db_name = os.getenv("MONGODB_DATABASE", "fishing_db")
collection_names = [x.strip() for x in os.getenv(
    "COLLECTIONS", "fishing_trips,fishing_zones,weather_reports,sea_conditions"
).split(",") if x.strip()]
output_dir = Path(os.getenv("OUTPUT_DIR", "data/raw_snapshot"))
output_dir.mkdir(parents=True, exist_ok=True)
client = MongoClient(uri, serverSelectionTimeoutMS=5000)

try:
    client.admin.command("ping")
    db = client[db_name]
    existing = set(db.list_collection_names())
    for name in collection_names:
        if name not in existing:
            print(f"[SKIP] ไม่พบ Collection: {name}")
            continue
        docs = list(db[name].find({}))
        if not docs:
            print(f"[EMPTY] Collection ไม่มีเอกสาร: {name}")
            continue
        df = pd.json_normalize(docs, sep=".")
        for col in df.columns:
            if df[col].map(lambda v: isinstance(v, (ObjectId, Decimal128))).any():
                df[col] = df[col].map(lambda v: None if pd.isna(v) is True else str(v))
        path = output_dir / f"{name}.parquet"
        df.to_parquet(path, index=False)
        print(f"[OK] {name}: {len(df):,} rows, {len(df.columns):,} columns")
        print(f"     บันทึก: {path}")
finally:
    client.close()
