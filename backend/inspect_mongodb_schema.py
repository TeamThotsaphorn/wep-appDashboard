"""Read-only MongoDB schema inspector for the EEC Seafood project.

Reads MONGODB_URI / MONGODB_DATABASE from .env (falls back to localhost / eec_seafood).
Prints collection names, document counts, and field paths with BSON/Python types
found in a sample of documents. It never prints field values, only types, and it
never writes, updates or deletes anything.

Run from the project root:
    .\\.venv\\Scripts\\python.exe -X utf8 backend\\inspect_mongodb_schema.py
Optional: --sample 100   (documents sampled per collection, default 100)
"""
import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("MONGODB_DATABASE", "eec_seafood")
EXPECTED = [
    "fishing_trips", "fishing_zones", "weather_reports", "sea_conditions",
    "export_orders", "catch_images", "weather_forecasts", "marine_forecasts",
]
MAX_ARRAY_ITEMS = 5  # array elements inspected per document


def type_name(value):
    return type(value).__name__


def walk(value, path, out):
    """Record the type seen at each field path. Arrays use `path[]` for elements."""
    out[path][type_name(value)] += 1
    if isinstance(value, dict):
        for k, v in value.items():
            walk(v, f"{path}.{k}" if path else k, out)
    elif isinstance(value, list):
        for item in value[:MAX_ARRAY_ITEMS]:
            walk(item, f"{path}[]", out)


def inspect_collection(coll, sample_size):
    docs = list(coll.find({}).limit(sample_size))
    fields = defaultdict(lambda: defaultdict(int))
    for d in docs:
        for k, v in d.items():
            walk(v, k, fields)
    return len(docs), fields


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=100)
    args = ap.parse_args()

    client = MongoClient(URI, serverSelectionTimeoutMS=4000)
    try:
        client.admin.command("ping")
    except PyMongoError as e:
        print(f"[ERROR] Cannot connect to MongoDB: {type(e).__name__}")
        sys.exit(1)
    print("[OK] MongoDB connection (ping) succeeded")

    dbs = client.list_database_names()
    print(f"Databases on server: {dbs}")
    if DB_NAME not in dbs:
        print(f"[ERROR] Database '{DB_NAME}' not found")
        sys.exit(1)
    db = client[DB_NAME]

    actual = sorted(db.list_collection_names())
    print(f"\nDatabase: {DB_NAME}")
    print(f"Collections found ({len(actual)}): {actual}")
    missing = [c for c in EXPECTED if c not in actual]
    extra = [c for c in actual if c not in EXPECTED]
    print(f"Expected but missing: {missing or 'none'}")
    print(f"Present but not in handover list: {extra or 'none'}")

    for name in actual:
        coll = db[name]
        total = coll.count_documents({})
        n, fields = inspect_collection(coll, args.sample)
        print("\n" + "=" * 70)
        print(f"{name}  |  documents: {total}  |  sampled: {n} (types from sample only)")
        print("-" * 70)
        for path in sorted(fields):
            types = ", ".join(f"{t}x{c}" for t, c in sorted(fields[path].items()))
            print(f"  {path:<45} {types}")
        idx = [i["name"] for i in coll.list_indexes()]
        print(f"  indexes: {idx}")


if __name__ == "__main__":
    main()
