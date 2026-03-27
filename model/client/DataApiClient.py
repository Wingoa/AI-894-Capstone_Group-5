import requests

class DataApiClient:

    def __init__(self, data_url: str):
        self.data_url = data_url

    def getFighterVector(self, fighter_id):
        resp = requests.get(f"{self.data_url}/latest/{fighter_id}")
        resp.raise_for_status()
        data = resp.json()
        return data