import json
import requests

WEKAN_URL = 'https://wekan.usachborodach.ru'

def get_token():
    auth_url = f'{WEKAN_URL}/users/login'
    auth_data = {'username': 'agorbov', 'password': 'Sven159357258'}
    response = requests.post(auth_url, data=auth_data).text
    return json.loads(response)['token']

def post_card(title, board_name, token):
    post_the_card_url = (
        f'{WEKAN_URL}/api/'
        f'boards/{ids["boards"][board_name]}/'
        f'lists/{ids["lists"][board_name]}/cards'
    )
    headers = {
        'Authorization': f'Bearer {token}'
    }
    request_data = {
        'title': title,
        'description': '',
        'authorId': ids['author'],
        'swimlaneId': f"{ids['swimlanes'][board_name]}"
    }
    response = requests.post(post_the_card_url, headers=headers, data=request_data)
    response = json.loads(response.text)
    return response['_id']

ids = {
    'boards': {
        'work': '6nEeTCXHcdq3GaqoT', 
        'home': 'eyZsGfRcPAysgBbB3'
    },
    'lists': {
        'work': 'WwR4yf6LbzKgnhaLx',
        'home': 'uj8XTX37dMJT7SByr'
    },
    'swimlanes': {
        'work': 'xbct7XafyWxqGhhWq', 
        'home': 'Qh75JghWz3eyAhY9K'
    },
    'author': 'YHrRysNZnbE5eEfrh'
}