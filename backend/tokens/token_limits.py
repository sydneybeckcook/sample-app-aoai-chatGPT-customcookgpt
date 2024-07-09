
import tiktoken
import logging
from datetime import datetime

from backend.auth.auth_utils import get_authenticated_user_details
from backend.history.cosmosdbservice import CosmosTokenClient

class TokenLimits:
    def __init__(self, cosmos_token_client: CosmosTokenClient):
        self.cosmos_token_client = cosmos_token_client
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def calculate_tokens(self, message: str) -> int:
        if not isinstance(message, str):
            logging.error(f"Invalid message type: {type(message)} - {message}")
            raise TypeError(f"Expected string or buffer, got {type(message)}")
        return len(self.encoding.encode(message))

    async def update_usage_from_message(self, request_headers, message, model_used, message_type):
        user_details = get_authenticated_user_details(request_headers)
        if not user_details:
            return {"error": "User not authenticated"}

        user_id = user_details['user_principal_id']
        today = datetime.utcnow().date().isoformat()
        tokens = self.calculate_tokens(message)

        token_record = await self.cosmos_token_client.get_token_usage(user_id, today)

        if not token_record:
            token_record = await self.cosmos_token_client.create_token_record(user_id, today)
            if not token_record:
                return {"error": "Failed to create a new token record"}

        if model_used.startswith('gpt-35-turbo-16k'):
            if message_type == 'input':
                token_record['gpt35InputTokens'] += tokens
            elif message_type == 'output':
                token_record['gpt35OutputTokens'] += tokens
        elif model_used.startswith('gpt-4'):
            if message_type == 'input':
                token_record['gpt4InputTokens'] += tokens
            elif message_type == 'output':
                token_record['gpt4OutputTokens'] += tokens
        else:
            return {"error": "Unknown model"}

        await self.cosmos_token_client.upsert_token_record(token_record)
    
    async def update_usage_from_usage(self, request_headers, usage_data, model_used):
        today = datetime.utcnow().date().isoformat()
        user_details = get_authenticated_user_details(request_headers)
        user_id = user_details['user_principal_id']

        token_record = await self.cosmos_token_client.get_token_usage(user_id, today)

        if not token_record:
            token_record = await self.cosmos_token_client.create_token_record(user_id, today)
            if not token_record:
                raise Exception("Failed to create a new token record")

        if model_used.startswith('gpt-35-turbo'):
            token_record['gpt35InputTokens'] += usage_data['prompt_tokens']
            token_record['gpt35OutputTokens'] += usage_data['completion_tokens']
        elif model_used.startswith('gpt-4o'):
            token_record['gpt4InputTokens'] += usage_data['prompt_tokens']
            token_record['gpt4OutputTokens'] += usage_data['completion_tokens']
        else:
            raise ValueError("Unknown model")

        await self.cosmos_token_client.upsert_token_record(token_record)

    async def check_token_costs(self, user_id, start_date, end_date):
        gpt4_input_cost = 0.01 / 1000  # $0.01 per 1,000 tokens
        gpt4_output_cost = 0.03 / 1000  # $0.03 per 1,000 tokens
        gpt35_input_cost = 0.003 / 1000  # $0.003 per 1,000 tokens
        gpt35_output_cost = 0.004 / 1000  # $0.004 per 1,000 tokens

        token_records = await self.cosmos_token_client.query_token_usage(user_id, start_date, end_date)

        total_cost = 0
        for record in token_records:
            total_cost += (record['gpt4InputTokens'] * gpt4_input_cost +
                           record['gpt4OutputTokens'] * gpt4_output_cost +
                           record['gpt35InputTokens'] * gpt35_input_cost +
                           record['gpt35OutputTokens'] * gpt35_output_cost)

        return total_cost