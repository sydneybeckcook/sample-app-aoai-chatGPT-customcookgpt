# Error Messages Feature

## Edit date
Last update: 8/8/2024. I did not have time before internship end to make the error messages all that robust. Details of some issues will be in the Considerations section below.

## Overview
Error messages are slightly enhanced, slightly clearer in the chat interface and they are inserted into CosmosDB. The key part is that we use sendErrorBackend function in various parts (detailed below) in Chat.tsx to send the error message to be inserted into CosmosDB along with some other contructed and/or retrieved information about the error like the user message that caused this error, error message id, userid, conversation, date. 

## Updates

- **`cosmosdbservice.py`**: 
  - Added `CosmosErrorClient` class to handle upserting of error messages into CosmosDB.

- **`settings.py`**:  
  - Add `database_errors: str` and `container_errors: str` to `_ChatHistorySettings` class.

- **`.env`**:  
  - Added `AZURE_COSMOSDB_DATABASE_ERRORS=db_errors_dev`.
  - Added `AZURE_COSMOSDB_CONTAINER_ERRORS=error_info_dev`.

- **`app.py`**: 
  - Added the following methods:
    - `init_cosmos_errors_client()`: Make instance of `CosmosErrorClient`.
    - `log_error()`: View function for route `/api/upsert_error`.

- **`api.ts`**:  
  - Added `sendErrorToBackend()` service function for route `/api/upsert_error

- **`Chat.tsx`**: 
  - `makeApiRequestWithCosmosDB()`:
    - Added `sendErrorToBackend()` call every time there is a return due to an error 
    - Added `userId` variable that is populated using the current user id from the app state context
        - In case `userId` undefined, I used the string "none"
    - In case that it follows clearly from the function logic that there is no `conversationId`, the last parameter passed to `sendErrorToBackend()` is "none" to reflect this
    - `errorResponseMessage`, `errorChatMsg.content` are the variables to look for in the function that reflect the slight enhancement of the error messages
  - `useLayoutEffect(() => {...}, [processMessages])`
    - `handleErrors`:
        - Wrapper for `sendErrorToBackend()` to use specifically in this useLayoutEffect hook
            - Why wrapper? This hook could not accomodate await sendErrorToBackend, I needed to make handleErrors async in order to handle that
            - Also, since this hook handles the effects whenever the processMessages state changes, errors in here, so far in my investigation, occur after `makeApiRequestWithCosmosDB()` that is why I use "n/a" for the user_message parameter. Ie, `makeApiRequestWithCosmosDB()` is when the user types in a question and sends it, and the processMessage state is only updated after the user does this, so there is no user message when this hook is triggered
    - Call `handleErrors` every time there is a return due to an error
    - `errorChatMsg.content`, `errorMessage` are the variables to look for in the function if you want to enhance the error messages
        - I barely enhanced any error messages here because it didn't feel that appropriate/what already exists looks ok
        - Added  `Also, ${errorMessage}` within message before throwing the error in the block that checks if messages do not exist in the current chat in the app state context
  
            
## Considerations
More testing needs to be done. Beyond mocking various errors to send to makeApiRequestWithCosmosDB it would be beneficial if they were real errors from openai and see if it causes any unintended behavior and see if those are caught by the outer catch block in makeApiRequestWithCosmosDB appropriately.
As of 8/8/24, there is an issue when deployed locally with a getting response back from gpt35turbo on caibot001. The error message from openai is Access denied due to Virutal Network/Firewall rules and status code 403. 
This error does not happen when using gpt4o on caibot002. I also don't remember encountering this issue when I tested the code on 8/3/24. 
At the very least, the upsert error messages seems to be working correctly.