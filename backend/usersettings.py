from backend.auth.auth_utils import get_authenticated_user_details
from backend.history.cosmosdbservice import CosmosSettingsClient

class UserSettingsManager:
    def __init__(self, cosmos_settings_client: CosmosSettingsClient):
        self.cosmos_settings_client = cosmos_settings_client

    async def get_user_settings(self, user_id):
        settings = await self.cosmos_settings_client.get_settings(user_id)
        return settings

    async def create_user_settings(self, user_id, default_system_message, default_temperature):
        try:
            resp = await self.cosmos_settings_client.create_settings(user_id, default_system_message, default_temperature)
            return resp
        except ValueError as e:
            return {"error": str(e)}

    async def update_user_settings(self, user_id, system_message, temperature):
        resp = await self.cosmos_settings_client.update_settings(user_id, system_message, temperature)
        return resp