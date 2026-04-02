import requests

HABBO_API_URL = 'https://www.habbo.com.br/api/public'

class HabboService:
    def __init__(self):
        self.api_url = HABBO_API_URL

    def get_user_info(self, habbo_id: str):
        response = requests.get(f'{self.api_url}/users?name={habbo_id}')
        return response