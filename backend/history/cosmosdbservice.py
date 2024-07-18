import uuid
from datetime import datetime
from azure.cosmos.aio import CosmosClient
from azure.cosmos import exceptions, PartitionKey
  
import os
import uuid
from datetime import datetime
from flask import Flask, request
from azure.identity import DefaultAzureCredential  
import logging

class CosmosConversationClient():
    
    def __init__(self, cosmosdb_endpoint: str, credential: any, database_name: str, convos_container_name: str, deleted_convos_container_name: str, shared_convos_container_name: str, enable_message_feedback: bool = False):
        self.cosmosdb_endpoint = cosmosdb_endpoint
        self.credential = credential
        self.database_name = database_name
        self.convos_container_name = convos_container_name
        self.deleted_convos_container_name = deleted_convos_container_name
        self.shared_convos_container_name = shared_convos_container_name

        self.cosmosdb_client = CosmosClient(self.cosmosdb_endpoint, credential=credential)
        self.database_client = self.cosmosdb_client.get_database_client(database_name)
        self.convos_container_client = self.database_client.get_container_client(convos_container_name)
        self.deleted_convos_container_client = self.database_client.get_container_client(deleted_convos_container_name)
        self.shared_convos_container_client = self.database_client.get_container_client(shared_convos_container_name)
        self.enable_message_feedback = enable_message_feedback

    async def ensure(self):
        if not self.cosmosdb_client or not self.database_client or not self.convos_container_client or not self.deleted_convos_container_client:
            return False,"CosmosDB client or database client not initialized correctly"
        
        convos_container_info = await self.convos_container_client.read()
        if not convos_container_info:
            return False, f"CosmosDB container {self.convos_container_name} not found"
        
        deleted_convos_container_info = await self.deleted_convos_container_client.read()
        if not deleted_convos_container_info:
            return False, f"CosmosDB container {self.deleted_convos_container_name} not found"
        
        shared_convos_container_info = await self.shared_convos_container_client.read()
        if not shared_convos_container_info:
            return False, f"CosmosDB container {self.shared_convos_container_name} not found"
        
        return True, "CosmosConversationClient initialized successfully"

    async def create_conversation(self, user_id, title = ''):
        conversation = {
            'id': str(uuid.uuid4()),  
            'type': 'conversation',
            'createdAt': datetime.utcnow().isoformat(),  
            'updatedAt': datetime.utcnow().isoformat(),  
            'userId': user_id,
            'title': title
        }
        ## TODO: add some error handling based on the output of the upsert_item call
        resp = await self.convos_container_client.upsert_item(conversation)  
        if resp:
            return resp
        else:
            return False
    
    async def upsert_conversation(self, conversation):
        resp = await self.convos_container_client.upsert_item(conversation)
        if resp:
            return resp
        else:
            return False

    # async def delete_conversation(self, user_id, conversation_id):
    #     conversation = await self.convos_container_client.read_item(item=conversation_id, partition_key=user_id)        
    #     if conversation:
    #         resp = await self.convos_container_client.delete_item(item=conversation_id, partition_key=user_id)
    #         return resp
    #     else:
    #         return True

    async def soft_delete_conversation(self, user_id, conversation_id):
        conversation = await self.convos_container_client.read_item(item=conversation_id, partition_key=user_id)

        if conversation: 
            resp = await self.deleted_convos_container_client.upsert_item(conversation)
            await self.convos_container_client.delete_item(item=conversation_id, partition_key=user_id)
            return resp
        else: 
            return True
        
    # async def delete_messages(self, conversation_id, user_id):
    #     ## get a list of all the messages in the conversation
    #     messages = await self.get_messages(user_id, conversation_id)
    #     response_list = []
    #     if messages:
    #         for message in messages:
    #             resp = await self.convos_container_client.delete_item(item=message['id'], partition_key=user_id)
    #             response_list.append(resp)
    #         return response_list

    async def soft_delete_messages(self, conversation_id, user_id):
        ## get a list of all the messages in the conversation
        messages = await self.get_messages(user_id, conversation_id)
        response_list = []
        if messages:
            for message in messages:
                resp = await self.deleted_convos_container_client.upsert_item(message)
                await self.convos_container_client.delete_item(item=message['id'], partition_key=user_id)
                response_list.append(resp)
            return response_list

    async def get_conversations(self, user_id, limit, sort_order = 'DESC', offset = 0):
        parameters = [
            {
                'name': '@userId',
                'value': user_id
            }
        ]
        query = f"SELECT * FROM c where c.userId = @userId and c.type='conversation' order by c.updatedAt {sort_order}"
        if limit is not None:
            query += f" offset {offset} limit {limit}" 
            
        conversations = []
        async for item in self.convos_container_client.query_items(query=query,parameters=parameters):
            conversations.append(item)
        return conversations

    async def get_conversation(self, user_id, conversation_id):
        parameters = [
            {
                'name': '@conversationId',
                'value': conversation_id
            },
            {
                'name': '@userId',
                'value': user_id
            }
        ]
        query = f"SELECT * FROM c where c.id = @conversationId and c.type='conversation' and c.userId = @userId"
        conversations=[]
        async for item in self.convos_container_client.query_items(query=query, parameters=parameters):
            conversations.append(item)
        return conversations[0] if conversations else None
 
    async def create_message(self, uuid, conversation_id, user_id, input_message: dict):
        message = {
            'id': uuid,
            'type': 'message',
            'userId' : user_id,
            'createdAt': datetime.utcnow().isoformat(),
            'updatedAt': datetime.utcnow().isoformat(),
            'conversationId' : conversation_id,
            'role': input_message['role'],
            'content': input_message['content']
        }

        if self.enable_message_feedback:
            message['feedback'] = ''
        
        resp = await self.convos_container_client.upsert_item(message)  
        if resp:
            ## update the parent conversations's updatedAt field with the current message's createdAt datetime value
            conversation = await self.get_conversation(user_id, conversation_id)
            conversation['updatedAt'] = message['createdAt']
            await self.upsert_conversation(conversation)
            return resp
        else:
            return False
    
    async def update_message_feedback(self, user_id, message_id, feedback):
        message = await self.convos_container_client.read_item(item=message_id, partition_key=user_id)
        if message:
            message['feedback'] = feedback
            resp = await self.convos_container_client.upsert_item(message)
            return resp
        else:
            return False

    async def get_messages(self, user_id, conversation_id):
        parameters = [
            {
                'name': '@conversationId',
                'value': conversation_id
            },
            {
                'name': '@userId',
                'value': user_id
            }
        ]
        query = f"SELECT * FROM c WHERE c.conversationId = @conversationId AND c.type='message' AND c.userId = @userId ORDER BY c.timestamp ASC"
        messages =[]
        async for message in self.convos_container_client.query_items(query=query, parameters=parameters):
            messages.append(message)
        return messages
 
    
    async def share_conversation(self, user_id, conversation_id):
        # Retrieve the conversation
        try:
            logging.info(f"Attempting to retrieve conversation with user_id: {user_id}, conversation_id: {conversation_id}")
            conversation = await self.convos_container_client.read_item(item=conversation_id, partition_key=user_id)
            logging.info(f"Retrieved conversation: {conversation}")
        except Exception as e:
            logging.error(f"Error retrieving conversation: {e}")
            return False

        if not conversation:
            logging.error("No conversation found.")
            return False

        # Retrieve messages associated with the conversation
        try:
            logging.info(f"Retrieving messages for user_id: {user_id}, conversation_id: {conversation_id}")
            messages = await self.get_messages(user_id, conversation_id)  # Ensure this is awaited if it's async
            logging.info(f"Retrieved messages: {messages}")
        except Exception as e:
            logging.error(f"Error retrieving messages: {e}")
            return False

        # Check if a shared conversation for this originalConversationId already exists
        existing_shared_conversation_query = "SELECT * FROM c WHERE c.originalConversationId = @conversationId"
        parameters = [{"name": "@conversationId", "value": conversation_id}]
        logging.info(f"Running query: {existing_shared_conversation_query} with parameters: {parameters}")

        existing_shared_conversations = []
        try:
            async for item in self.shared_convos_container_client.query_items(query=existing_shared_conversation_query, parameters=parameters):
                existing_shared_conversations.append(item)
                logging.info(f"Found existing shared conversation: {item}")
        except Exception as e:
            logging.error(f"Error querying shared conversations: {e}")
            return False

        if existing_shared_conversations:
            # If an existing shared conversation is found, use its ID to update
            shared_conversation_id = existing_shared_conversations[0]['id']
        else:
            # Otherwise, generate a new unique ID
            shared_conversation_id = str(uuid.uuid4())

        # Create or update the shared conversation object
        shared_conversation = {
            'id': shared_conversation_id,
            'originalConversationId': conversation_id,
            'sharedAt': datetime.utcnow().isoformat(),
            'conversation': conversation,
            'messages': messages
        }

        logging.info(f"Upserting shared conversation: {shared_conversation}")
        try:
            resp = await self.shared_convos_container_client.upsert_item(shared_conversation)
            logging.info(f"Upsert response: {resp}")
            if resp:
                logging.info(f"Successfully upserted shared conversation with ID: {shared_conversation_id}")
                return shared_conversation_id  # Return the ID of the shared conversation
            else:
                logging.error("Failed to upsert shared conversation.")
                return False
        except Exception as e:
            logging.error(f"Error upserting shared conversation: {e}")
            return False

    async def get_shared_conversation(self, shared_conversation_id):
        query = "SELECT * FROM c WHERE c.originalConversationId = @sharedConversationId"
        parameters = [{"name": "@sharedConversationId", "value": shared_conversation_id}]
        logging.info(f"Running query: {query} with parameters: {parameters}")

        conversations = []
        try:
            async for item in self.shared_convos_container_client.query_items(query=query, parameters=parameters):
                conversations.append(item)
                logging.info(f"Found conversation: {item}")
        except Exception as e:
            logging.error(f"Error querying shared conversations: {e}")
            return None

        return conversations[0] if conversations else None
    
class CosmosTokenClient():

    def __init__(self, cosmosdb_endpoint: str, credential: any, database_name: str, token_container_name: str, user_privilege_container_name: str):
        self.cosmosdb_endpoint = cosmosdb_endpoint
        self.credential = credential
        self.database_name = database_name
        self.token_container_name = token_container_name
        self.user_privilege_container_name = user_privilege_container_name
        self.cosmosdb_client = CosmosClient(self.cosmosdb_endpoint, credential=credential)
        self.database_client = self.cosmosdb_client.get_database_client(database_name)
        self.token_container_client = self.database_client.get_container_client(token_container_name)
        self.user_privilege_container_client = self.database_client.get_container_client(user_privilege_container_name)

    async def ensure(self):
        try:
            if not self.cosmosdb_client or not self.database_client or not self.token_container_client or not self.user_privilege_container_client:
                return False
            
            token_container_info = await self.token_container_client.read()
            if not token_container_info:
                return False
            
            user_privilege_container_info = await self.user_privilege_container_client.read()
            if not user_privilege_container_info:
                return False
            
            return True
        except:
            return False
        
    async def create_token_record(self, user_id, date):
        token_record = {
            'id': f"{user_id}_{date}",  # Composite key
            'userId': user_id,
            'date': date,
            'gpt35InputTokens': 0,
            'gpt35OutputTokens': 0,
            'gpt4InputTokens': 0,
            'gpt4OutputTokens': 0
        }
        resp = await self.token_container_client.upsert_item(token_record)  
        if resp:
            return resp
        else:
            return False
        
    async def create_user_privilege_record(self, user_id, user_name, user_type):
        privilege_record = {
            'id': str(uuid.uuid4()),
            'userId': user_id,
            'name': user_name,
            'userType': user_type  # 'regular' or 'super'
        }
        resp = await self.user_privilege_container_client.upsert_item(privilege_record)  
        if resp:
            return resp
        else:
            return False
    
    async def upsert_token_record(self, record):
        resp = await self.token_container_client.upsert_item(record)
        if resp:
            return resp
        else:
            return False
        
    async def upsert_user_privilege_record(self, record):
        resp = await self.user_privilege_container_client.upsert_item(record)
        if resp:
            return resp
        else:
            return False

    async def get_token_usage(self, user_id, date):
        query = "SELECT * FROM c WHERE c.userId = @userId AND c.date = @date"
        parameters = [
            {"name": "@userId", "value": user_id},
            {"name": "@date", "value": date}
        ]

        items = []
        async for item in self.token_container_client.query_items(query=query, parameters=parameters):
            items.append(item)
        return items[0] if items else None
    
    async def get_user_privilege_type(self, user_id):
        query = f"SELECT c.userType FROM c WHERE c.userId = @userId"
        parameters = [{"name":"@userId", "value":user_id}]
        items = []
        async for item in self.user_privilege_container_client.query_items(query=query, parameters=parameters):
            items.append(item)
        if items:
            return items[0]['userType']
        else:
            return None
    
    async def update_token_usage(self, user_id, date, gpt35_input_tokens=0, gpt35_output_tokens=0, gpt4_input_tokens=0, gpt4_output_tokens=0):
        record = await self.get_token_usage(user_id, date)
        if record:
            record['gpt35InputTokens'] += gpt35_input_tokens
            record['gpt35OutputTokens'] += gpt35_output_tokens
            record['gpt4InputTokens'] += gpt4_input_tokens
            record['gpt4OutputTokens'] += gpt4_output_tokens
            return await self.token_container_client.upsert_item(record)
        else:
            return await self.create_token_record(user_id, date)

    async def delete_token_record(self, user_id, date):
        record_id = f"{user_id}_{date}"
        return await self.token_container_client.delete_item(item=record_id, partition_key=user_id)
    
    async def query_token_usage(self, user_id, start_date, end_date):
        query = f"SELECT * FROM c WHERE c.userId = @userId AND (c.date BETWEEN @startDate AND @endDate)"
        parameters=[
            {"name":"@userId", "value": user_id},
            {"name":"@startDate", "value": start_date},
            {"name":"@endDate", "value": end_date}
        ]
        items  =[]
        async for item in self.token_container_client.query_items(query=query, parameters=parameters):
            items.append(item)
        return items
        

class CosmosPrivacyNoticeClient:

    def __init__(self, cosmosdb_endpoint: str, credential: any, database_name: str, responses_container_name: str):
        self.cosmosdb_endpoint = cosmosdb_endpoint
        self.credential = credential
        self.database_name = database_name
        self.responses_container_name = responses_container_name
        self.cosmosdb_client = CosmosClient(self.cosmosdb_endpoint, credential=credential)
        self.database_client = self.cosmosdb_client.get_database_client(database_name)
        self.response_container_client = self.database_client.get_container_client(responses_container_name)

    async def check_user_response(self, user_id):
        query = f"SELECT * FROM c WHERE c.userId = @userId"
        parameters = [{"name": "@userId", "value": user_id}]
        items=[]
        async for item in self.response_container_client.query_items(query=query, parameters=parameters):
            items.append(item)
        return items[0] if items else None

    async def record_user_response(self, user_id, date, response):
        try:
            response_record = {
                'id': str(uuid.uuid4()),
                'userId': user_id,
                'date': date, 
                'response': response
            }
            print(f"response_record: {response_record}")
            resp = await self.response_container_client.upsert_item(response_record)
            return resp
        except Exception as e:
            print(f"Error in record_user_response: {e}")
            return {"error": str(e)}

class CosmosSettingsClient:

    def __init__(self, cosmosdb_endpoint: str, credential: any, database_name: str, settings_container_name: str):
        self.cosmosdb_endpoint = cosmosdb_endpoint
        self.credential = credential
        self.database_name = database_name
        self.settings_container_name = settings_container_name
        self.cosmosdb_client = CosmosClient(self.cosmosdb_endpoint, credential=credential)
        self.database_client = self.cosmosdb_client.get_database_client(database_name)
        self.settings_container_client = self.database_client.get_container_client(settings_container_name)

    async def get_settings(self, user_id):
        query = f"SELECT * FROM c WHERE c.userId = @userId AND c.type = 'userSettings'"
        parameters = [{"name": "@userId", "value": user_id}]
        settings =[]
        async for setting in self.settings_container_client.query_items(query=query, parameters=parameters):
            settings.append(setting)
        return settings[0] if settings else None

    async def update_settings(self, user_id, system_message, temperature):
        settings_document = await self.get_settings(user_id)
        if settings_document:
            settings_document['systemMessage'] = system_message
            settings_document['temperature'] = temperature
        resp = await self.settings_container_client.upsert_item(settings_document)
        return resp
    
    async def create_settings(self, user_id, default_system_message, default_temperature):
        existing_settings = await self.get_settings(user_id)
        if existing_settings is not None:
            raise ValueError("Settings already exist for this user")

        new_settings_document = {
            "id": "user-settings-" + str(user_id),
            "type": "userSettings",
            "userId": user_id,
            "systemMessage": default_system_message,
            "temperature": default_temperature
        }
        resp = await self.settings_container_client.upsert_item(new_settings_document)
        return resp

