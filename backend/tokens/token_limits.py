
import tiktoken
import logging
from datetime import datetime
import os

from backend.auth.auth_utils import get_authenticated_user_details
from backend.history.cosmosdbservice import CosmosTokenClient
from backend.settings import (
    app_settings
)
from backend.tokens.token_privileges import TokenPrivileges

class TokenLimits:
    def __init__(self, cosmos_token_client: CosmosTokenClient):
        self.cosmos_token_client = cosmos_token_client
        self.token_privileges = TokenPrivileges(cosmos_token_client)
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
        logging.info(f"update_usage_from_message: user_id: {user_id}")
        today = datetime.utcnow().date().isoformat()
        tokens = self.calculate_tokens(message)
        logging.info(f"update_usage_from_message: tokens: {tokens}")

        token_record = await self.cosmos_token_client.get_token_usage(user_id, today)

        if not token_record:
            token_record = await self.cosmos_token_client.create_token_record(user_id, today)
            if not token_record:
                return {"error": "Failed to create a new token record"}

        if model_used.startswith('gpt-35-turbo'):
            if message_type == 'input':
                token_record['gpt35InputTokens'] += tokens
            elif message_type == 'output':
                token_record['gpt35OutputTokens'] += tokens
        elif model_used.startswith('gpt-4o'):
            if message_type == 'input':
                token_record['gpt4InputTokens'] += tokens
            elif message_type == 'output':
                token_record['gpt4OutputTokens'] += tokens
        else:
            return {"error": "Unknown model"}

        return await self.cosmos_token_client.upsert_token_record(token_record)
    
    async def update_usage_from_openai_response(self, request_headers, usage_data, model_used):
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

        return await self.cosmos_token_client.upsert_token_record(token_record)

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

    async def get_todays_cost(self, user_id):
        today = datetime.utcnow().date().isoformat()
        token_record = await self.cosmos_token_client.get_token_usage(user_id, today)

        if not token_record:
            return 0

        gpt35_tokens = {
            'input': token_record.get('gpt35InputTokens', 0),
            'output': token_record.get('gpt35OutputTokens', 0)
        }
        gpt4_tokens = {
            'input': token_record.get('gpt4InputTokens', 0),
            'output': token_record.get('gpt4OutputTokens', 0)
        }

        cost_gpt35 = self.calculate_token_cost(gpt35_tokens, 'gpt-35-turbo')
        cost_gpt4 = self.calculate_token_cost(gpt4_tokens, 'gpt-4o')

        return cost_gpt35 + cost_gpt4
    
    def calculate_token_cost(self, tokens, model_used):
        if model_used.startswith('gpt-35-turbo'):
            input_cost = 0.003 / 1000  # $0.003 per 1,000 tokens
            output_cost = 0.004 / 1000  # $0.004 per 1,000 tokens
        elif model_used.startswith('gpt-4o'):
            input_cost = 0.01 / 1000  # $0.01 per 1,000 tokens
            output_cost = 0.03 / 1000  # $0.03 per 1,000 tokens
        else:
            raise ValueError("Unknown model")

        return tokens['input'] * input_cost + tokens['output'] * output_cost
    
    async def get_user_daily_limit(self, user_type):
        logging.info(f"Getting daily limit for user type: {user_type}")
        if user_type == 'regular':
            daily_limit = app_settings.base_settings.daily_token_cost_limit_regular
        elif user_type == 'super':
            daily_limit = app_settings.base_settings.daily_token_cost_limit_super
        else:
            logging.error("Unknown user privilege type")
            return {"error": "Unknown user privilege type"}
        
        logging.info(f"Daily limit for user type {user_type}: {daily_limit}")
        return daily_limit

    async def calculate_daily_usage_percentage(self, request_headers):
        logging.info("Calculating daily usage percentage")

        # Check user privileges
        user_type = await self.token_privileges.check_user_token_privileges(request_headers)
        if isinstance(user_type, dict) and "error" in user_type:
            logging.error(f"Error in user privileges: {user_type['error']}")
            return user_type

        # Get user details
        user_details = get_authenticated_user_details(request_headers)
        if not user_details:
            logging.error("User not authenticated")
            return {"error": "User not authenticated"}

        user_id = user_details['user_principal_id']
        logging.info(f"User ID: {user_id}")

        # Get the user's daily token cost limit
        daily_limit = await self.get_user_daily_limit(user_type)
        if isinstance(daily_limit, dict) and "error" in daily_limit:
            logging.error(f"Error in daily limit: {daily_limit['error']}")
            return daily_limit

        # Get today's token cost
        todays_cost = await self.get_todays_cost(user_id)
        logging.info(f"Today's token cost for user {user_id}: {todays_cost}")

        # Calculate percentage of daily limit used
        if todays_cost == 0:
            percentage_remaining = 100.0
        else:
            percentage_used = (todays_cost / daily_limit) * 100
            percentage_remaining = max(0, 100 - percentage_used)
        
        # Round to 1 digit after the decimal
        percentage_remaining = round(percentage_remaining, 1)
        
        logging.info(f"Percentage of daily limit remaining: {percentage_remaining}")

        return percentage_remaining


