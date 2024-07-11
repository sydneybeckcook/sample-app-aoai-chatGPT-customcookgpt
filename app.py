
from datetime import datetime
import copy
import json
import os
import logging
import uuid
import httpx
from dotenv import load_dotenv
from quart import (
    Blueprint,
    Quart,
    jsonify,
    make_response,
    request,
    send_from_directory,
    render_template,
    session
)

from openai import AsyncAzureOpenAI
from azure.identity.aio import (
    DefaultAzureCredential,
    get_bearer_token_provider
)
from backend.auth.auth_utils import get_authenticated_user_details
from backend.security.ms_defender_utils import get_msdefender_user_json
from backend.history.cosmosdbservice import CosmosConversationClient, CosmosPrivacyNoticeClient, CosmosSettingsClient, CosmosTokenClient
from backend.settings import (
    app_settings,
    MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION
)
from backend.utils import (
    format_as_ndjson,
    format_stream_response,
    format_non_streaming_response,
    convert_to_pf_format,
    format_pf_non_streaming_response,
)
from backend.usersettings import UserSettingsManager
from backend.tokens.token_limits import TokenLimits
from backend.tokens.token_privileges import TokenPrivileges
load_dotenv()
bp = Blueprint("routes", __name__, static_folder="static", template_folder="static")


def create_app():
    app = Quart(__name__)
    app.register_blueprint(bp)
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.secret_key = os.environ.get("QUART_SECRET_KEY")
    return app


@bp.route("/")
async def index():
    return await render_template(
        "index.html",
        title=app_settings.ui.title,
        favicon=app_settings.ui.favicon
    )


@bp.route("/favicon.ico")
async def favicon():
    return await bp.send_static_file("favicon.ico")


@bp.route("/assets/<path:path>")
async def assets(path):
    return await send_from_directory("static/assets", path)

# Debug settings
DEBUG = os.environ.get("DEBUG", "false")
if DEBUG.lower() == "true":
    logging.basicConfig(level=logging.DEBUG)

USER_AGENT = "GitHubSampleWebApp/AsyncAzureOpenAI/1.0.0"


# Frontend Settings via Environment Variables
frontend_settings = {
    "auth_enabled": app_settings.base_settings.auth_enabled,
    "feedback_enabled": (
        app_settings.chat_history and
        app_settings.chat_history.enable_feedback
    ),
    "ui": {
        "title": app_settings.ui.title,
        "logo": app_settings.ui.logo,
        "chat_logo": app_settings.ui.chat_logo or app_settings.ui.logo,
        "chat_title": app_settings.ui.chat_title,
        "chat_description": app_settings.ui.chat_description,
        "show_share_button": app_settings.ui.show_share_button,
    },
    "sanitize_answer": app_settings.base_settings.sanitize_answer,
}


# Enable Microsoft Defender for Cloud Integration
MS_DEFENDER_ENABLED = os.environ.get("MS_DEFENDER_ENABLED", "true").lower() == "true"



import logging
from quart import request, session, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO)

def get_model_configuration(selected_model):
    model_configurations = {
        "gpt-35-turbo": {
            "resource": app_settings.azure_openai.resource_v3,
            "model": app_settings.azure_openai.model_v3,
            "endpoint":app_settings.azure_openai.endpoint_v3,
            "key": app_settings.azure_openai.key_v3,
            "model_name": app_settings.azure_openai.model_name_v3
        },
        "gpt-4o": {
            "resource": app_settings.azure_openai.resource_v4,
            "model": app_settings.azure_openai.model_v4,
            "endpoint": app_settings.azure_openai.endpoint_v4,
            "key": app_settings.azure_openai.key_v4,
            "model_name": app_settings.azure_openai.model_name_v4
        }
    }
    return model_configurations.get(selected_model)

def set_model_config_in_session(selected_model):
    model_config = get_model_configuration(selected_model)
    if model_config:
        session["AZURE_OPENAI_RESOURCE"] = model_config["resource"]
        session["AZURE_OPENAI_MODEL"] = model_config["model"]
        session["AZURE_OPENAI_ENDPOINT"] = model_config["endpoint"]
        session["AZURE_OPENAI_KEY"] = model_config["key"]
        session["AZURE_OPENAI_MODEL_NAME"] = model_config["model_name"]
        session["AZURE_OPENAI_SELECTED_MODEL"] = selected_model
        session.modified = True
        
        logging.info(f"Model session set to: {selected_model}")
        logging.info(f"Session updated with model config: {model_config}")
        return True
    else:
        logging.error(f"Invalid model selected: {selected_model}")
        return False

@bp.route("/change_model", methods=["POST"])
async def change_model():
    logging.info("Changing model...")
    data = await request.get_json()
    logging.info(f"data: {data}")
    selected_model = data.get("selectedModel")

    logging.info(f"Received request to change model to: {selected_model}")

    current_model = session.get("AZURE_OPENAI_SELECTED_MODEL", "gpt-35-turbo")
    logging.info(f"Current selected model: {current_model}")

    if set_model_config_in_session(selected_model):
        return jsonify({"message": "Model changed successfully", "current_model": selected_model}), 200
    else:
        return jsonify({"error": "Invalid model selected", "current_model": current_model}), 400



@bp.route("/get_user_id", methods=["GET"])
def get_user_id():
    try: 
        authenticated_user = get_authenticated_user_details(request_headers=request.headers)
        user_id = authenticated_user['user_principal_id']
        return jsonify({"userId": user_id})
    except Exception as e:
        print(f"An error occurred: {e}")  # Log the error
        return jsonify({"error": "An internal server error occurred"})


# Initialize Azure OpenAI Client
def init_openai_client():
    azure_openai_client = None
    try:
        # API version check
        logging.debug(f"from app setting: {app_settings.azure_openai.preview_api_version}")
        logging.debug(f"MINIMUM_SUPPORTED_AZURE_PREVIEW_API_VERSION: {MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION}")
        if (
            app_settings.azure_openai.preview_api_version
            < MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION
        ):
            logging.debug("Raising Value Error for api preview version")
            raise ValueError(
                f"The minimum supported Azure OpenAI preview API version is '{MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION}'"
            )

        # Endpoint
        if (
            not app_settings.azure_openai.endpoint and
            not app_settings.azure_openai.resource
        ):
            
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_RESOURCE is required"
            )

        endpoint = (
            app_settings.azure_openai.endpoint
            if app_settings.azure_openai.endpoint
            else f"https://{app_settings.azure_openai.resource}.openai.azure.com/"
        )

        # Authentication
        aoai_api_key = app_settings.azure_openai.key
        ad_token_provider = None
        if not aoai_api_key:
            logging.debug("No AZURE_OPENAI_KEY found, using Azure Entra ID auth")
            ad_token_provider = get_bearer_token_provider(
                DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
            )

        # Deployment
        deployment = session.get("AZURE_OPENAI_SELECTED_MODEL",app_settings.azure_openai.model_v3)
        if not deployment:
            raise ValueError("AZURE_OPENAI_MODEL is required")

        # Default Headers
        default_headers = {"x-ms-useragent": USER_AGENT}

        azure_openai_client = AsyncAzureOpenAI(
            api_version=app_settings.azure_openai.preview_api_version,
            api_key=aoai_api_key,
            azure_ad_token_provider=ad_token_provider,
            default_headers=default_headers,
            azure_endpoint=endpoint,
        )

        return azure_openai_client
    except Exception as e:
        logging.exception("Exception in Azure OpenAI initialization", e)
        azure_openai_client = None
        raise e


def prepare_cosmosdb_client_parameters():
    if app_settings.base_settings.is_local:
        cosmosdb_endpoint = app_settings.chat_history.local_endpoint
        cosmosdb_key = app_settings.chat_history.local_key
    else:
        cosmosdb_endpoint = f"https://{app_settings.chat_history.account}.documents.azure.com:443/"
        cosmosdb_key = app_settings.chat_history.account_key

    credentials = cosmosdb_key if cosmosdb_key else DefaultAzureCredential()

    return cosmosdb_endpoint, credentials

def init_cosmos_conversation_client():
    try:
        cosmosdb_endpoint, credentials = prepare_cosmosdb_client_parameters()
        return CosmosConversationClient(
            cosmosdb_endpoint=cosmosdb_endpoint,
            credential=credentials,
            database_name=f"{app_settings.chat_history.database}",
            convos_container_name=f"{app_settings.chat_history.conversations_container}",
            deleted_convos_container_name=f"{app_settings.chat_history.container_deleted_convos}",
            shared_convos_container_name=f"{app_settings.chat_history.container_shared_convos}",
            enable_message_feedback=app_settings.chat_history.enable_feedback
        )
    except Exception as e:
        logging.exception("Exception in CosmosConversationClient initialization", e)
        return None
    

def init_cosmos_token_client():
    try:
        cosmosdb_endpoint, credentials = prepare_cosmosdb_client_parameters()
        return CosmosTokenClient(
            cosmosdb_endpoint=cosmosdb_endpoint,
            credential=credentials,
            database_name=f"{app_settings.chat_history.database_tokens}",
            token_container_name=f"{app_settings.chat_history.container_token_usage}",
            user_privilege_container_name=f"{app_settings.chat_history.container_token_user_privileges}"
        )
    except Exception as e:
        logging.exception("Exception in CosmosTokenClient initialization", e)
        return None


def init_cosmos_privacy_notice_client():
    try:
        cosmosdb_endpoint, credentials= prepare_cosmosdb_client_parameters()

        return CosmosPrivacyNoticeClient(
            cosmosdb_endpoint=cosmosdb_endpoint,
            credential=credentials,
            database_name=f"{app_settings.chat_history.database_privacy_notice}",
            responses_container_name=f"{app_settings.chat_history.container_responses}"
        )
    except Exception as e:
        logging.exception("Exception in CosmosPrivacyNoticeClient initialization", e)
        return None
    
def init_cosmos_settings_client():
    try:
        cosmosdb_endpoint, credentials= prepare_cosmosdb_client_parameters()
        return CosmosSettingsClient(
            cosmosdb_endpoint=cosmosdb_endpoint,
            credential=credentials,
            database_name=f"{app_settings.chat_history.database_settings}",
            settings_container_name=f"{app_settings.chat_history.container_settings}"
        )
    except Exception as e:
        logging.exception("Exception in CosmosSettingsClient initialization", e)
        return None


async def check_or_create_user_settings(user_id):
    logging.debug(f"check_or_create_user_settings: Starting for user_id: {user_id}")
    cosmos_settings_client = init_cosmos_settings_client()
    try:
        user_settings_manager = UserSettingsManager(cosmos_settings_client)
        logging.debug("check_or_create_user_settings: UserSettingsManager object instantiated")
        user_settings = await user_settings_manager.get_user_settings(user_id)
        logging.debug(f"check_or_create_user_settings: Retrieved settings: {user_settings}")

        if not user_settings:
            logging.debug("check_or_create_user_settings: No settings found, creating new settings")
            default_system_message = app_settings.azure_openai.system_message
            default_temperature = app_settings.azure_openai.temperature

            user_settings = await user_settings_manager.create_user_settings(user_id, default_system_message, default_temperature)
            logging.debug(f"check_or_create_user_settings: Created new settings: {user_settings}")
        logging.debug(f"user_settings: {user_settings}")
        return user_settings
    
    except Exception as e :
        logging.error(f"check_or_create_user_settings: CosmosDB error: {str(e)}. Using default user settings")
        return {
            "systemMessage": app_settings.azure_openai.system_message,
            "temperature": app_settings.azure_openai.temperature
        }
    finally:
        await cosmos_settings_client.cosmosdb_client.close()



async def prepare_model_args(request_body, request_headers):
    cosmos_token_client = init_cosmos_token_client()
    token_limits = TokenLimits(cosmos_token_client)


    selected_model = session.get("AZURE_OPENAI_SELECTED_MODEL", "gpt-35-turbo")
    set_model_config_in_session(selected_model)

    authenticated_user_details = get_authenticated_user_details(request_headers)
    user_id = authenticated_user_details['user_principal_id']
    user_settings = await check_or_create_user_settings(user_id)
    user_temperature = user_settings.get("temperature", app_settings.azure_openai.temperature)
    logging.debug(f"user_temperature: {user_temperature}")
    user_system_message = user_settings.get("systemMessage", app_settings.azure_openai.system_message)
    logging.debug(f"user_system_message: {user_system_message}")
    
    request_messages = request_body.get("messages", [])
    messages = []

    if not app_settings.datasource:
        messages = [
            {
                "role": "system",
                "content": user_system_message
            }
        ]

    for message in request_messages:
        if message:
            messages.append(
                {
                    "role": message["role"],
                    "content": message["content"]
                }
            )


    user_json = None
    if (MS_DEFENDER_ENABLED):
        authenticated_user_details = get_authenticated_user_details(request_headers)
        conversation_id = request_body.get("conversation_id", None)        
        user_json = get_msdefender_user_json(authenticated_user_details, request_headers, conversation_id)

    model_args = {
        "messages": messages,
        "temperature": user_temperature,
        "max_tokens": app_settings.azure_openai.max_tokens,
        "top_p": app_settings.azure_openai.top_p,
        "stop": app_settings.azure_openai.stop_sequence,
        "stream": app_settings.azure_openai.stream,
        "model": selected_model,
        "user": user_json,
    }

    if app_settings.datasource:
        logging.info(f"Request object: {request}")
        logging.info(f"Request body {request_body}")
        logging.info(f"Request headers {request_headers}")
        model_args["extra_body"] = {
            "data_sources": [
                app_settings.datasource.construct_payload_configuration(
                    request=request
                )
            ]
        }
        logging.info(f'model_args: model_args["extra_body"]["data_sources"][0]["parameters"]')
        model_args["extra_body"]["data_sources"][0]["parameters"]["role_information"] = user_system_message
        logging.info(f'model_args: model_args["extra_body"]["data_sources"][0]["parameters"]')
        

        
        

    model_args_clean = copy.deepcopy(model_args)
    if model_args_clean.get("extra_body"):
        secret_params = [
            "key",
            "connection_string",
            "embedding_key",
            "encoded_api_key",
            "api_key",
        ]
        for secret_param in secret_params:
            if model_args_clean["extra_body"]["data_sources"][0]["parameters"].get(
                secret_param
            ):
                model_args_clean["extra_body"]["data_sources"][0]["parameters"][
                    secret_param
                ] = "*****"
        authentication = model_args_clean["extra_body"]["data_sources"][0][
            "parameters"
        ].get("authentication", {})
        for field in authentication:
            if field in secret_params:
                model_args_clean["extra_body"]["data_sources"][0]["parameters"][
                    "authentication"
                ][field] = "*****"
        embeddingDependency = model_args_clean["extra_body"]["data_sources"][0][
            "parameters"
        ].get("embedding_dependency", {})
        if "authentication" in embeddingDependency:
            for field in embeddingDependency["authentication"]:
                if field in secret_params:
                    model_args_clean["extra_body"]["data_sources"][0]["parameters"][
                        "embedding_dependency"
                    ]["authentication"][field] = "*****"

    logging.debug(f"REQUEST BODY: {json.dumps(model_args_clean, indent=4)}")
    await cosmos_token_client.cosmosdb_client.close()
    return model_args


async def promptflow_request(request):
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {app_settings.promptflow.api_key}",
        }
        # Adding timeout for scenarios where response takes longer to come back
        logging.debug(f"Setting timeout to {app_settings.promptflow.response_timeout}")
        async with httpx.AsyncClient(
            timeout=float(app_settings.promptflow.response_timeout)
        ) as client:
            pf_formatted_obj = convert_to_pf_format(
                request,
                app_settings.promptflow.request_field_name,
                app_settings.promptflow.response_field_name
            )
            # NOTE: This only support question and chat_history parameters
            # If you need to add more parameters, you need to modify the request body
            response = await client.post(
                app_settings.promptflow.endpoint,
                json={
                    app_settings.promptflow.request_field_name: pf_formatted_obj[-1]["inputs"][app_settings.promptflow.request_field_name],
                    "chat_history": pf_formatted_obj[:-1],
                },
                headers=headers,
            )
        resp = response.json()
        resp["id"] = request["messages"][-1]["id"]
        return resp
    except Exception as e:
        logging.error(f"An error occurred while making promptflow_request: {e}")


async def send_chat_request(request_body, request_headers):
    filtered_messages = []
    messages = request_body.get("messages", [])
    for message in messages:
        if message.get("role") != 'tool':
            filtered_messages.append(message)
            
    request_body['messages'] = filtered_messages
    model_args = await prepare_model_args(request_body, request_headers)
    logging.debug(f"model_args: {model_args}")

    cosmos_token_client = init_cosmos_token_client()
    try:
        azure_openai_client = init_openai_client()
        raw_response = await azure_openai_client.chat.completions.with_raw_response.create(**model_args)
        response = raw_response.parse()
        logging.info(f"response: {response}")
        apim_request_id = raw_response.headers.get("apim-request-id") 

        token_limits = TokenLimits(cosmos_token_client)

        for message in model_args["messages"]:
            await token_limits.update_usage_from_message(
                request_headers=request_headers,
                message=message["content"],
                model_used=model_args["model"],
                message_type="input"
            )

    except Exception as e:
        logging.exception("Exception in send_chat_request")
        raise e
    finally:
        await cosmos_token_client.cosmosdb_client.close()

    return response, apim_request_id


async def complete_chat_request(request_body, request_headers):
    if app_settings.base_settings.use_promptflow:
        response = await promptflow_request(request_body)
        history_metadata = request_body.get("history_metadata", {})
        return format_pf_non_streaming_response(
            response,
            history_metadata,
            app_settings.promptflow.response_field_name,
            app_settings.promptflow.citations_field_name
        )
    else:
        logging.info("Entering complete_chat_request")
        response, apim_request_id = await send_chat_request(request_body, request_headers)
        cosmos_token_client = init_cosmos_token_client()
        token_limits = TokenLimits(cosmos_token_client)

        if app_settings.datasource:
            usage_data = response.get("usage", {})
            if usage_data:
                await token_limits.update_usage_from_usage(
                    request_headers=request_headers,
                    usage_data=usage_data,
                    model_used=response.get("model", app_settings.azure_openai.model_v3)
                )

        else:
            message_content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            if message_content:
                await token_limits.update_usage_from_message(
                    request_headers=request_headers,
                    message=message_content,
                    model_used=response.get("model", app_settings.azure_openai.model_v3),
                    message_type="output"
                )

        history_metadata = request_body.get("history_metadata", {})
        await cosmos_token_client.cosmosdb_client.close()
        return format_non_streaming_response(response, history_metadata, apim_request_id)


async def stream_chat_request(request_body, request_headers):
    logging.info(f"Entering stream_chat_request")
    response, apim_request_id = await send_chat_request(request_body, request_headers)
    history_metadata = request_body.get("history_metadata", {})
    cosmos_token_client = init_cosmos_token_client()
    token_limits = TokenLimits(cosmos_token_client)
    logging.info(f"response: {response}")
    async def generate():
        async for completionChunk in response:
            logging.info(f"completionChunk: {completionChunk}")
            choices = completionChunk.choices
            if choices and choices[0].delta:
                message_content = choices[0].delta.content
                if message_content:
                    logging.info(f"message_content: {message_content}")
                    await token_limits.update_usage_from_message(
                        request_headers=request_headers,
                        message=message_content,
                        model_used=completionChunk.model,
                        message_type="output"
                    )
            yield format_stream_response(completionChunk, history_metadata, apim_request_id)
    try:
        return generate()
    finally:
        await cosmos_token_client.cosmosdb_client.close()



async def check_user_token_limits(request_headers):
    cosmos_token_client = init_cosmos_token_client()
    try:
        logging.debug("checking user token limit")
        user_details = get_authenticated_user_details(request_headers)
        user_id = user_details['user_principal_id']
        token_privileges = TokenPrivileges(cosmos_token_client)
        user_privilege_type = await token_privileges.check_user_token_privileges(request_headers)
        logging.debug(f"user_privilege_type: {user_privilege_type}")

        if user_privilege_type == 'super':
            daily_limit = app_settings.base_settings.daily_token_cost_limit_super
        else:
            daily_limit = app_settings.base_settings.daily_token_cost_limit_regular
        
        logging.debug(f"daily_limit: {daily_limit}")
        token_limits = TokenLimits(cosmos_token_client)
        today = datetime.utcnow().date().isoformat()
        current_cost = await token_limits.check_token_costs(user_id, today, today)
        logging.debug(f"current_cost: {current_cost}")

        if current_cost > daily_limit:
            logging.error(f"error: Token limit exceeded")
            return jsonify({"error": "Token limit exceeded"}), 403
        logging.debug("User's token limit not exceeded, returning None")
        return None
    finally:
        await cosmos_token_client.cosmosdb_client.close()


async def conversation_internal(request_body, request_headers):
    try:
        token_limits_error_msg = await check_user_token_limits(request_headers)
        if token_limits_error_msg:
            return token_limits_error_msg
        

        logging.info(f"conversation_internal: request_body: {request_body}")
        logging.info(f"conversation_internal: reqeust_headers: {request_headers}")
        
        if app_settings.azure_openai.stream:
            result = await stream_chat_request(request_body, request_headers)
            response = await make_response(format_as_ndjson(result))
            response.timeout = None
            response.mimetype = "application/json-lines"
            return response
        else:
            result = await complete_chat_request(request_body, request_headers)
            return jsonify(result)

    except Exception as ex:
        logging.exception(ex)
        if hasattr(ex, "status_code"):
            return jsonify({"error": str(ex)}), ex.status_code
        else:
            return jsonify({"error": str(ex)}), 500





@bp.route("/conversation", methods=["POST"])
async def conversation():
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()

    return await conversation_internal(request_json, request.headers)


@bp.route("/frontend_settings", methods=["GET"])
def get_frontend_settings():
    try:
        return jsonify(frontend_settings), 200
    except Exception as e:
        logging.exception("Exception in /frontend_settings")
        return jsonify({"error": str(e)}), 500


@bp.route('/api/settings/<user_id>', methods=['GET', 'POST'])
async def user_settings(user_id):
    cosmos_settings_client = init_cosmos_settings_client()
    try:
        user_settings_manager = UserSettingsManager(cosmos_settings_client)
        if request.method == 'GET':
            settings = await user_settings_manager.get_user_settings(user_id)
            if settings is None: 
                logging.info(f"Creating default settings for user_id: {user_id}")
                await user_settings_manager.create_user_settings(user_id, app_settings.azure_openai.system_message, app_settings.azure_openai.temperature)
            logging.info(f"Fetched settings for user_id: {user_id} - {settings}")
            return jsonify(settings)

        elif request.method == 'POST':
            new_settings = await request.json
            logging.info(f"Received new settings for user_id: {user_id} - {new_settings}")
            system_message = new_settings.get('systemMessage', app_settings.azure_openai.system_message)
            temperature = new_settings.get('temperature', app_settings.azure_openai.temperature)
            logging.info(f"Updating settings for user_id: {user_id} - system_message: {system_message}, temperature: {temperature}")
            updated_settings = await user_settings_manager.update_user_settings(user_id, system_message, temperature)
            logging.info(f"Updated settings for user_id: {user_id} - {updated_settings}")
            return jsonify(updated_settings)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        await cosmos_settings_client.cosmosdb_client.close()
    

## Conversation History API ##
@bp.route("/history/generate", methods=["POST"])
async def add_conversation():
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    try:
        # make sure cosmos is configured
        cosmos_conversation_client= init_cosmos_conversation_client()
        if not cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        # check for the conversation_id, if the conversation is not set, we will create a new one
        history_metadata = {}
        if not conversation_id:
            title = await generate_title(request_json["messages"])
            conversation_dict = await cosmos_conversation_client.create_conversation(
                user_id=user_id, title=title
            )
            conversation_id = conversation_dict["id"]
            history_metadata["title"] = title
            history_metadata["date"] = conversation_dict["createdAt"]

        ## Format the incoming message object in the "chat/completions" messages format
        ## then write it to the conversation history in cosmos
        messages = request_json["messages"]
        if len(messages) > 0 and messages[-1]["role"] == "user":
            createdMessageValue = await cosmos_conversation_client.create_message(
                uuid=str(uuid.uuid4()),
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-1],
            )
            if createdMessageValue == "Conversation not found":
                raise Exception(
                    "Conversation not found for the given conversation ID: "
                    + conversation_id
                    + "."
                )
        else:
            raise Exception("No user message found")

        await cosmos_conversation_client.cosmosdb_client.close()

        # Submit request to Chat Completions for response
        request_body = await request.get_json()
        history_metadata["conversation_id"] = conversation_id
        request_body["history_metadata"] = history_metadata
        return await conversation_internal(request_body, request.headers)

    except Exception as e:
        logging.exception("Exception in /history/generate")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/update", methods=["POST"])
async def update_conversation():
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    try:
        # make sure cosmos is configured
        cosmos_conversation_client= init_cosmos_conversation_client()
        if not cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        # check for the conversation_id, if the conversation is not set, we will create a new one
        if not conversation_id:
            raise Exception("No conversation_id found")

        ## Format the incoming message object in the "chat/completions" messages format
        ## then write it to the conversation history in cosmos
        messages = request_json["messages"]
        if len(messages) > 0 and messages[-1]["role"] == "assistant":
            if len(messages) > 1 and messages[-2].get("role", None) == "tool":
                # write the tool message first
                await cosmos_conversation_client.create_message(
                    uuid=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    user_id=user_id,
                    input_message=messages[-2],
                )
            # write the assistant message
            await cosmos_conversation_client.create_message(
                uuid=messages[-1]["id"],
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-1],
            )
        else:
            raise Exception("No bot messages found")

        # Submit request to Chat Completions for response
        await cosmos_conversation_client.cosmosdb_client.close()
        response = {"success": True}
        return jsonify(response), 200

    except Exception as e:
        logging.exception("Exception in /history/update")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/message_feedback", methods=["POST"])
async def update_message():
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]
    cosmos_conversation_client= init_cosmos_conversation_client()

    ## check request for message_id
    request_json = await request.get_json()
    message_id = request_json.get("message_id", None)
    message_feedback = request_json.get("message_feedback", None)
    try:
        if not message_id:
            return jsonify({"error": "message_id is required"}), 400

        if not message_feedback:
            return jsonify({"error": "message_feedback is required"}), 400

        ## update the message in cosmos
        updated_message = await cosmos_conversation_client.update_message_feedback(
            user_id, message_id, message_feedback
        )
        if updated_message:
            return (
                jsonify(
                    {
                        "message": f"Successfully updated message with feedback {message_feedback}",
                        "message_id": message_id,
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "error": f"Unable to update message {message_id}. It either does not exist or the user does not have access to it."
                    }
                ),
                404,
            )

    except Exception as e:
        logging.exception("Exception in /history/message_feedback")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/delete", methods=["DELETE"])
async def delete_conversation():
    ## get the user id from the request headers
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    try:
        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400

        ## make sure cosmos is configured
        cosmos_conversation_client= init_cosmos_conversation_client()
        if not cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        ## delete the conversation messages from cosmos first
        deleted_messages = await cosmos_conversation_client.delete_messages(
            conversation_id, user_id
        )

        ## Now delete the conversation
        deleted_conversation = await cosmos_conversation_client.delete_conversation(
            user_id, conversation_id
        )

        await cosmos_conversation_client.cosmosdb_client.close()

        return (
            jsonify(
                {
                    "message": "Successfully deleted conversation and messages",
                    "conversation_id": conversation_id,
                }
            ),
            200,
        )
    except Exception as e:
        logging.exception("Exception in /history/delete")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/list", methods=["GET"])
async def list_conversations():
    offset = request.args.get("offset", 0)
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    ## make sure cosmos is configured
    cosmos_conversation_client= init_cosmos_conversation_client()
    if not cosmos_conversation_client:
        raise Exception("CosmosDB is not configured or not working")

    ## get the conversations from cosmos
    conversations = await cosmos_conversation_client.get_conversations(
        user_id, offset=offset, limit=25
    )
    await cosmos_conversation_client.cosmosdb_client.close()
    if not isinstance(conversations, list):
        return jsonify({"error": f"No conversations for {user_id} were found"}), 404

    ## return the conversation ids

    return jsonify(conversations), 200


@bp.route("/history/read", methods=["POST"])
async def get_conversation():
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400

    ## make sure cosmos is configured
    cosmos_conversation_client= init_cosmos_conversation_client()
    if not cosmos_conversation_client:
        raise Exception("CosmosDB is not configured or not working")

    ## get the conversation object and the related messages from cosmos
    conversation = await cosmos_conversation_client.get_conversation(
        user_id, conversation_id
    )
    ## return the conversation id and the messages in the bot frontend format
    if not conversation:
        return (
            jsonify(
                {
                    "error": f"Conversation {conversation_id} was not found. It either does not exist or the logged in user does not have access to it."
                }
            ),
            404,
        )

    # get the messages for the conversation from cosmos
    conversation_messages = await cosmos_conversation_client.get_messages(
        user_id, conversation_id
    )

    ## format the messages in the bot frontend format
    messages = [
        {
            "id": msg["id"],
            "role": msg["role"],
            "content": msg["content"],
            "createdAt": msg["createdAt"],
            "feedback": msg.get("feedback"),
        }
        for msg in conversation_messages
    ]

    await cosmos_conversation_client.cosmosdb_client.close()
    return jsonify({"conversation_id": conversation_id, "messages": messages}), 200


@bp.route("/history/rename", methods=["POST"])
async def rename_conversation():
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400

    ## make sure cosmos is configured
    cosmos_conversation_client= init_cosmos_conversation_client()
    if not cosmos_conversation_client:
        raise Exception("CosmosDB is not configured or not working")

    ## get the conversation from cosmos
    conversation = await cosmos_conversation_client.get_conversation(
        user_id, conversation_id
    )
    if not conversation:
        return (
            jsonify(
                {
                    "error": f"Conversation {conversation_id} was not found. It either does not exist or the logged in user does not have access to it."
                }
            ),
            404,
        )

    ## update the title
    title = request_json.get("title", None)
    if not title:
        return jsonify({"error": "title is required"}), 400
    conversation["title"] = title
    updated_conversation = await cosmos_conversation_client.upsert_conversation(
        conversation
    )

    await cosmos_conversation_client.cosmosdb_client.close()
    return jsonify(updated_conversation), 200


@bp.route("/history/delete_all", methods=["DELETE"])
async def delete_all_conversations():
    ## get the user id from the request headers
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    # get conversations for user
    try:
        ## make sure cosmos is configured
        cosmos_conversation_client= init_cosmos_conversation_client()
        if not cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        conversations = await cosmos_conversation_client.get_conversations(
            user_id, offset=0, limit=None
        )
        if not conversations:
            return jsonify({"error": f"No conversations for {user_id} were found"}), 404

        # delete each conversation
        for conversation in conversations:
            ## delete the conversation messages from cosmos first
            deleted_messages = await cosmos_conversation_client.delete_messages(
                conversation["id"], user_id
            )

            ## Now delete the conversation
            deleted_conversation = await cosmos_conversation_client.delete_conversation(
                user_id, conversation["id"]
            )
        await cosmos_conversation_client.cosmosdb_client.close()
        return (
            jsonify(
                {
                    "message": f"Successfully deleted conversation and messages for user {user_id}"
                }
            ),
            200,
        )

    except Exception as e:
        logging.exception("Exception in /history/delete_all")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/clear", methods=["POST"])
async def clear_messages():
    ## get the user id from the request headers
    authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    user_id = authenticated_user["user_principal_id"]

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    try:
        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400

        ## make sure cosmos is configured
        cosmos_conversation_client= init_cosmos_conversation_client()
        if not cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        ## delete the conversation messages from cosmos
        deleted_messages = await cosmos_conversation_client.delete_messages(
            conversation_id, user_id
        )

        return (
            jsonify(
                {
                    "message": "Successfully deleted messages in conversation",
                    "conversation_id": conversation_id,
                }
            ),
            200,
        )
    except Exception as e:
        logging.exception("Exception in /history/clear_messages")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/ensure", methods=["GET"])
async def ensure_cosmos():
    if not app_settings.chat_history:
        return jsonify({"error": "CosmosDB is not configured"}), 404

    try:
        cosmos_conversation_client= init_cosmos_conversation_client()
        success, err = await cosmos_conversation_client.ensure()
        logging.info(err)
        if not cosmos_conversation_client or not success:
            if err:
                return jsonify({"error": err}), 422
            return jsonify({"error": "CosmosDB is not configured or not working"}), 500

        await cosmos_conversation_client.cosmosdb_client.close()
        return jsonify({"message": "CosmosDB is configured and working"}), 200
    except Exception as e:
        logging.exception("Exception in /history/ensure")
        cosmos_exception = str(e)
        if "Invalid credentials" in cosmos_exception:
            return jsonify({"error": cosmos_exception}), 401
        elif "Invalid CosmosDB database name" in cosmos_exception:
            return (
                jsonify(
                    {
                        "error": f"{cosmos_exception} {app_settings.chat_history.database} for account {app_settings.chat_history.account}"
                    }
                ),
                422,
            )
        elif "Invalid CosmosDB container name" in cosmos_exception:
            return (
                jsonify(
                    {
                        "error": f"{cosmos_exception}: {app_settings.chat_history.conversations_container}"
                    }
                ),
                422,
            )
        else:
            return jsonify({"error": "CosmosDB is not working"}), 500


async def generate_title(conversation_messages) -> str:
    ## make sure the messages are sorted by _ts descending
    title_prompt = "Summarize the conversation so far into a 4-word or less title. Do not use any quotation marks or punctuation. Do not include any other commentary or description."

    messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in conversation_messages
    ]
    messages.append({"role": "user", "content": title_prompt})

    try:
        azure_openai_client = init_openai_client()
        response = await azure_openai_client.chat.completions.create(
            model=app_settings.azure_openai.model_v3,
            messages=messages, 
            temperature=1, 
            max_tokens=64
        )

        title = response.choices[0].message.content
        return title
    except Exception as e:
        logging.exception("Exception while generating title", e)
        return messages[-2]["content"]


app = create_app()
