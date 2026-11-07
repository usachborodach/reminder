import os
from datetime import datetime
from bson import json_util

base_path = os.path.dirname(__file__)
os.chdir(base_path)

def main():
    data = csv_to_documents()
    documents = processing(data)
    dump_to_json(documents)

def processing(data):
    bool_map = {"0": False, "1": True}
    documents = list()
    for item in data:
        document = dict()
        document['auto_postpone'] = bool_map[item['auto']]
        document['sended'] = bool_map[item['sended']]
        document['activate_datetime'] = datetime.strptime(item['date'], '%Y.%m.%d')
        document['create_datetime'] = datetime.now()
        document['last_send_datetime'] = None
        document['archived'] = False
        document['oneshot'] = False
        document['board'] = item['board']
        document['link_to_wekan_card'] = None
        document['periodic'] = parse_periodic(item['period'])
        documents.append(document)
    return documents

def parse_periodic(period_str):
    units_dict = {
        'd': 'day',
        'w': 'week',
        'm': 'month',
        'y': 'year'
    }
    short_unit = period_str[-1]
    return {
        'type': 'static',
        'unit': units_dict[short_unit],
        'number': int(period_str[:-1])
    }

def dump_to_json(documents):
    jsonify_data = json_util.dumps(documents, ensure_ascii=False, indent=4)
    with open('documents.json', 'w') as file:
        file.write(jsonify_data)

def csv_to_documents():
    with open('reminders.csv') as file:
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

if __name__ == '__main__':
    main()