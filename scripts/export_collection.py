import os
from bson.json_util import dumps
from pymongo import MongoClient

base_path = os.path.dirname(__file__)
os.chdir(base_path)

client = MongoClient()
db = client['reminder']
collection = db['reminders']
cursor = collection.find({})
documents = list(cursor)
json_str = dumps(documents, ensure_ascii=False, indent=4)
with open('documents.json', 'w') as file:
    file.write(json_str)

client.close()