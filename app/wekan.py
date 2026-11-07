import logging

import requests

logger = logging.getLogger(__name__)


class WekanClient:
    def __init__(self, url, login, password, author_id, boards):
        self.url = (url or '').rstrip('/')
        self.login = login
        self.password = password
        self.author_id = author_id
        self.boards = boards or {}
        self._token = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        resp = requests.post(
            f'{self.url}/users/login',
            data={'username': self.login, 'password': self.password},
            timeout=15,
        )
        resp.raise_for_status()
        self._token = resp.json()['token']
        return self._token

    def post_card(self, title: str, board: str, description: str = '') -> str:
        if not self.url:
            raise RuntimeError('WEKAN_URL is not configured')
        board_conf = self.boards.get(board)
        if not board_conf:
            raise ValueError(f'Unknown board: {board}')

        token = self._get_token()
        url = (
            f'{self.url}/api/'
            f'boards/{board_conf["board_id"]}/'
            f'lists/{board_conf["list_id"]}/cards'
        )
        headers = {'Authorization': f'Bearer {token}'}
        data = {
            'title': title,
            'description': description,
            'authorId': self.author_id,
            'swimlaneId': board_conf['swimlane_id'],
        }
        resp = requests.post(url, headers=headers, data=data, timeout=30)
        resp.raise_for_status()
        return resp.json()['_id']