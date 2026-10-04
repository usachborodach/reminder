import subprocess
from datetime import datetime
from pymongo import MongoClient
import pprint

# продумать, проипсикать заложить новые поля

REMOTE_CSV_PATH = '/root/myfirstvps/utilities/reminder/reminders.csv'
LOCAL_CSV_PATH = '/tmp/reminders.csv'
DEBUG_CSV_PATH = 'reminders.csv'

def main():
    # get_csv_from_vps()
    documents = csv_to_documents(DEBUG_CSV_PATH)
    documents = processing(documents)
    pprint.pprint(documents[0])
    # update_collection(documents)

def processing(documents):
    for document in documents:
        bool_map = {"0": False, "1": True}
        document['auto'] = bool_map[document['auto']]
        document['sended'] = bool_map[document['sended']]
        document['date_activation'] = datetime.strptime(document['date'], '%Y.%m.%d')
        document['date_creation'] = datetime.now()
        document['archived'] = False
        document['auto_archive'] = False
        document['card_id'] = None
    return documents

def get_csv_from_vps():
    command = ['scp', f'myfirstvps:{REMOTE_CSV_PATH}', LOCAL_CSV_PATH]
    subprocess.run(command)

def csv_to_documents(csv_path):
    file = open(csv_path)
    content = file.read()
    lines = content.splitlines()
    keys = lines.pop(0)
    keys = keys.split(';')
    documents = list()
    for line in lines:
        line = line.split(';')
        document = dict(zip(keys, line))
        documents.append(document)
    return documents

def update_collection(documents):
    client = MongoClient()
    db = client['reminder']
    collection = db['rules']
    delete_result = collection.delete_many({})
    print(f"Deleted: {delete_result.deleted_count}")
    insert_result = collection.insert_many(documents)
    print(f"Inserted: {len(insert_result.inserted_ids)}")
    client.close()

if __name__ == '__main__':
    main()