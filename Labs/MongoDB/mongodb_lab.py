"""MongoDB Lab (Document Store) using PyMongo.

Covers CRUD, Aggregation Pipeline, and the 3 end-of-lesson exercises:
1. Insert 5 orders with varying schemas and query by SKU.
2. Aggregate revenue by city.
3. Benchmark explain('executionStats') before and after indexing on 10,000 random documents.

Usage:
    python mongodb_lab.py
"""
import os
import random
from pymongo import ASCENDING, MongoClient

URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(URI)
db = client["shop"]


def run_exercises():
    orders = db["orders"]
    bench = db["orders_bench"]
    orders.drop()
    bench.drop()

    # Base documents from lesson
    orders.insert_many([
        {
            "_id": 1001,
            "customer": {"name": "Linh", "city": "Hanoi"},
            "status": "paid",
            "items": [
                {"sku": "BK-01", "title": "Python Basics", "qty": 2, "price": 12.5},
                {"sku": "BK-07", "title": "SQL in Practice", "qty": 1, "price": 18.0},
            ],
            "tags": ["student", "first-order"],
        },
        {
            "_id": 1002,
            "customer": {"name": "Nam", "city": "Da Nang"},
            "status": "shipped",
            "items": [{"sku": "BK-03", "title": "Data Viz", "qty": 1, "price": 22.0}],
        },
        {
            "_id": 1003,
            "customer": {"name": "Mai", "city": "Hanoi"},
            "status": "paid",
            "items": [{"sku": "BK-01", "title": "Python Basics", "qty": 1, "price": 12.5}],
            "coupon": "WELCOME10",
        },
    ])

    # Exercise 1: Add 5 orders with different shapes & find all orders containing SKU 'BK-01'
    orders.insert_many([
        {
            "_id": 1004,
            "customer": {"name": "Hung", "city": "Hue", "tier": "gold"},
            "status": "paid",
            "items": [
                {"sku": "BK-01", "title": "Python Basics", "qty": 3, "price": 12.5},
                {"sku": "BK-09", "title": "MongoDB Guide", "qty": 1, "price": 25.0},
            ],
            "note": "Deliver in office hours",
        },
        {
            "_id": 1005,
            "customer": {"name": "An", "city": "HCMC", "phone": "0901234567"},
            "status": "shipped",
            "items": [{"sku": "BK-05", "title": "Graph Databases", "qty": 2, "price": 30.0}],
            "giftWrap": True,
        },
        {
            "_id": 1006,
            "customer": {"name": "Binh", "city": "Hanoi"},
            "status": "pending",
            "items": [
                {"sku": "BK-03", "title": "Data Viz", "qty": 1, "price": 22.0},
                {"sku": "BK-01", "title": "Python Basics", "qty": 1, "price": 12.5},
            ],
            "paymentMethod": "COD",
        },
        {
            "_id": 1007,
            "customer": {"name": "Chi", "city": "Da Nang"},
            "status": "paid",
            "items": [{"sku": "BK-11", "title": "Cassandra Internals", "qty": 1, "price": 35.0}],
            "coupon": "FREESHIP",
            "discount": 5.0,
        },
        {
            "_id": 1008,
            "customer": {"name": "Duc", "city": "HCMC"},
            "status": "shipped",
            "items": [
                {"sku": "BK-07", "title": "SQL in Practice", "qty": 2, "price": 18.0},
                {"sku": "BK-09", "title": "MongoDB Guide", "qty": 1, "price": 25.0},
            ],
            "tags": ["vip", "fast-delivery"],
        },
    ])

    print("=== Exercise 1: Orders containing SKU 'BK-01' ===")
    for doc in orders.find(
        {"items.sku": "BK-01"},
        {"_id": 1, "customer.name": 1, "customer.city": 1, "status": 1},
    ).sort("_id", ASCENDING):
        print(doc)

    # Exercise 2: Aggregation - Revenue by city (for paid & shipped orders)
    print("\n=== Exercise 2: Revenue by city ===")
    pipeline = [
        {"$match": {"status": {"$in": ["paid", "shipped"]}}},
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$customer.city",
                "orderIds": {"$addToSet": "$_id"},
                "units": {"$sum": "$items.qty"},
                "revenue": {"$sum": {"$multiply": ["$items.qty", "$items.price"]}},
            }
        },
        {
            "$project": {
                "_id": 0,
                "city": "$_id",
                "orderCount": {"$size": "$orderIds"},
                "units": 1,
                "revenue": {"$round": ["$revenue", 2]},
            }
        },
        {"$sort": {"revenue": -1, "city": 1}},
    ]
    for row in orders.aggregate(pipeline):
        print(row)

    # Exercise 3: Explain before and after index on 10,000 random documents
    cities = ["Hanoi", "HCMC", "Da Nang", "Hue", "Can Tho"]
    statuses = ["paid", "shipped", "pending", "cancelled"]
    random.seed(42)
    docs = [
        {
            "_id": i,
            "customer": {"name": f"User_{i}", "city": random.choice(cities)},
            "status": random.choice(statuses),
            "amount": round(random.uniform(10.0, 200.0), 2),
        }
        for i in range(1, 10001)
    ]
    bench.insert_many(docs)

    query_filter = {"customer.city": "Hanoi", "status": "paid"}
    before = bench.find(query_filter).explain()["executionStats"]
    print("\n=== Exercise 3: Explain BEFORE Index (10,000 docs) ===")
    print(
        f"stage={before['executionStages']['stage']}, "
        f"nReturned={before['nReturned']}, "
        f"docsExamined={before['totalDocsExamined']}, "
        f"keysExamined={before['totalKeysExamined']}, "
        f"timeMs={before['executionTimeMillis']}"
    )

    bench.create_index([("customer.city", ASCENDING), ("status", ASCENDING)])
    after = bench.find(query_filter).explain()["executionStats"]
    print("\n=== Exercise 3: Explain AFTER Index ===")
    print(
        f"stage={after['executionStages']['stage']}, "
        f"inputStage={after['executionStages'].get('inputStage', {}).get('stage')}, "
        f"nReturned={after['nReturned']}, "
        f"docsExamined={after['totalDocsExamined']}, "
        f"keysExamined={after['totalKeysExamined']}, "
        f"timeMs={after['executionTimeMillis']}"
    )


if __name__ == "__main__":
    try:
        run_exercises()
    finally:
        client.close()
