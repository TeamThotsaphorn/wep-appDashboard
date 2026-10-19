import os
from pprint import pprint
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
client = MongoClient(uri, serverSelectionTimeoutMS=5000)

try:
    client.admin.command("ping")
    print("เชื่อมต่อ MongoDB สำเร็จ")
    print("\nDatabases:")
    for name in client.list_database_names():
        print("-", name)

    db_name = os.getenv("MONGODB_DATABASE", "").strip()
    if not db_name:
        db_name = input("\nกรอกชื่อ Database: ").strip()
    db = client[db_name]
    print(f"\nDatabase ที่เลือก: {db_name}")

    print("\nCollections:")
    for name in db.list_collection_names():
        collection = db[name]
        print(f"\n{name}: {collection.count_documents({}):,} documents")
        sample = collection.find_one()
        if sample:
            print("Fields:", list(sample.keys()))
            print("ตัวอย่างเอกสาร 1 รายการ:")
            pprint(sample)
except Exception as exc:
    print("เชื่อมต่อหรืออ่านข้อมูลไม่สำเร็จ:", exc)
    print("ตรวจสอบว่า MongoDB Server ทำงานอยู่ และ URI/Database ถูกต้อง")
finally:
    client.close()
