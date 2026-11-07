import os
from pymongo import MongoClient
from bson import json_util


base_path = os.path.dirname(__file__)
os.chdir(base_path)


def main():
    documents = load_documents()
    update_collection(documents)


def load_documents():
    with open('documents.json') as file:
        json_str = file.read()
        
    return json_util.loads(json_str)


def update_collection(documents):
    client = MongoClient()
    db = client['reminder']
    collection = db['reminders']

    delete_result = collection.delete_many({})
    print(f"Deleted: {delete_result.deleted_count}")

    insert_result = collection.insert_many(documents)
    print(f"Inserted: {len(insert_result.inserted_ids)}")

    client.close()


if __name__ == '__main__':
    main()