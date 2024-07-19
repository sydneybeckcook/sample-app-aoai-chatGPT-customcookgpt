
from backend.auth.auth_utils import get_authenticated_user_details
from backend.history.cosmosdbservice import CosmosTokenClient

class TokenPrivileges:
    def __init__(self, cosmos_token_client: CosmosTokenClient):
        self.cosmos_token_client = cosmos_token_client

    async def check_user_token_privileges(self, request_headers):
        user_details = get_authenticated_user_details(request_headers)
        if not user_details:
            return {"error": "User not authenticated"}

        user_id = user_details['user_principal_id']
        user_name = user_details['user_name']

        user_type = await self.cosmos_token_client.get_user_privilege_type(user_id)
        
        if user_type is None:
            user_type = 'regular'
            await self.cosmos_token_client.create_user_privilege_record(user_id, user_name, user_type)

        return user_type
