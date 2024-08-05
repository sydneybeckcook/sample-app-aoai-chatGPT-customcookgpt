import { chatHistorySampleData } from '../constants/chatHistory'

import { ChatMessage, Conversation, ConversationRequest, CosmosDBHealth, CosmosDBStatus, UserInfo } from './models'

export async function conversationApi(options: ConversationRequest, abortSignal: AbortSignal): Promise<Response> {
  const response = await fetch('/conversation', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      messages: options.messages
    }),
    signal: abortSignal
  })

  return response
}

export async function getUserInfo(): Promise<UserInfo[]> {
  const response = await fetch('/.auth/me')
  if (!response.ok) {
    console.log('No identity provider found. Access to chat will be blocked.')
    return []
  }

  const payload = await response.json()
  return payload
}

// export const fetchChatHistoryInit = async (): Promise<Conversation[] | null> => {
export const fetchChatHistoryInit = (): Conversation[] | null => {
  // Make initial API call here

  return chatHistorySampleData
}

export const historyList = async (offset = 0): Promise<Conversation[] | null> => {
  const response = await fetch(`/history/list?offset=${offset}`, {
    method: 'GET'
  })
    .then(async res => {
      const payload = await res.json()
      if (!Array.isArray(payload)) {
        console.error('There was an issue fetching your data.')
        return null
      }
      const conversations: Conversation[] = await Promise.all(
        payload.map(async (conv: any) => {
          let convMessages: ChatMessage[] = []
          convMessages = await historyRead(conv.id)
            .then(res => {
              return res
            })
            .catch(err => {
              console.error('error fetching messages: ', err)
              return []
            })
          const conversation: Conversation = {
            id: conv.id,
            title: conv.title,
            date: conv.createdAt,
            messages: convMessages
          }
          return conversation
        })
      )
      return conversations
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      return null
    })

  return response
}

export const historyRead = async (convId: string): Promise<ChatMessage[]> => {
  const response = await fetch('/history/read', {
    method: 'POST',
    body: JSON.stringify({
      conversation_id: convId
    }),
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(async res => {
      if (!res) {
        return []
      }
      const payload = await res.json()
      const messages: ChatMessage[] = []
      if (payload?.messages) {
        payload.messages.forEach((msg: any) => {
          const message: ChatMessage = {
            id: msg.id,
            role: msg.role,
            date: msg.createdAt,
            content: msg.content,
            feedback: msg.feedback ?? undefined
          }
          messages.push(message)
        })
      }
      return messages
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      return []
    })
  return response
}

export const historyGenerate = async (
  options: ConversationRequest,
  abortSignal: AbortSignal,
  convId?: string
): Promise<Response> => {
  let body
  if (convId) {
    body = JSON.stringify({
      conversation_id: convId,
      messages: options.messages
    })
  } else {
    body = JSON.stringify({
      messages: options.messages
    })
  }
//   const response = await fetch('/history/generate', {
//     method: 'POST',
//     headers: {
//       'Content-Type': 'application/json'
//     },
//     body: body,
//     signal: abortSignal
//   })
//     .then(res => {
//       return res
//     })
//     .catch(_err => {
//       console.error('There was an issue fetching your data.')
//       return new Response()
//     })
//   return response
// }

  // Simulated mock response with status 200
  const mockResponseData = [
    '{"history_metadata":{"conversation_id":"d7d349a0-562d-4cd0-94cc-4f8e23a6d4d0"}, "apim-request-id":"c1950af5-e810-46b8-bb3a-4590f7740088","choices":[{"messages":[{"content":"{\\"citations\\": [], \\"intent\\": \\"[\\"One sentence jokes\\", \\"Short jokes for entertainment\\"]\\"}","role":"tool"},{"content":"I\'m sorry, but I couldn\'t find any jokes in the retrieved documents. Would you like me to try coming up with a joke for you?","role":"assistant"}]}],"created":1722607174,"id":"c02e458a-f007-4ab3-ad4a-7b5ac999a1c6","model":"gpt-35-turbo","object":"extensions.chat.completion","error":"Connies fake error message"}',
    ''
  ].join('\n');

  const mockResponse = new Response(
    mockResponseData,
    {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    }
  );

  return mockResponse;
}
// export const historyGenerate = async (
//   options: ConversationRequest,
//   abortSignal: AbortSignal,
//   convId?: string
// ): Promise<Response> => {
//   let body;
//   if (convId) {
//     body = JSON.stringify({
//       conversation_id: convId,
//       messages: options.messages
//     });
//   } else {
//     body = JSON.stringify({
//       messages: options.messages
//     });
//   }

//   // Simulate different error responses
//   // const mockNetworkErrorResponse = () => { throw new TypeError('Network Error'); };
//   const mockSyntaxErrorResponse = new Response(
//     new ReadableStream({
//       start(controller) {
//         const encoder = new TextEncoder();
//         // Incomplete JSON string to cause SyntaxError
//         controller.enqueue(encoder.encode('{"choices":[{"messages":[{"content":'));
//         controller.close();
//       }
//     }),
//     {
//       headers: { 'Content-Type': 'application/json' }
//     }
//   );

//   //This one to simulate the if response.ok is false and does not use the default by sending "simulated error for testing"
//   const mockErrorResponse = new Response(
//     JSON.stringify({ error: "Simulated error for testing" }),
//     {
//       status: 500,
//       headers: { 'Content-Type': 'application/json' }
//     }
//   );

//   // This one to simulate a successful resposne bod but response has error
//   // Simulate a response with content and an error field to trigger the error handling
//   const mocksuccessfulErrorResponse = new Response(
//     JSON.stringify({
//       choices: [
//         {
//           messages: [
//             {
//               content: "This is a valid message."
//             }
//           ]
//         }
//       ],
//       error: "Simulated error for testing"
//     }),
//     {
//       status: 200,
//       headers: { 'Content-Type': 'application/json' }
//     }
//   );

//     const mockNoContentResponse = new Response(
//       JSON.stringify({
//         choices: [{}] // Simulating no content in choices
//       }),
//       {
//         status: 200,
//         headers: { 'Content-Type': 'application/json' }
//       }
//     );
  

//   // Uncomment the line below for the type of error you want to test
//   return mockNetworkErrorResponse(); // Uncomment to simulate a network error
//   // return mockSyntaxErrorResponse; // Uncomment to simulate a syntax error
//   // return mockErrorResponse; // Default to simulate a generic error for response no ok
//   // return mocksuccessfulErrorResponse; // Uncomment to simulate body with error error
//   // return mockNoContentResponse; //Uncomment to simulat no content error
// };




export const historyUpdate = async (messages: ChatMessage[], convId: string): Promise<Response> => {
  const response = await fetch('/history/update', {
    method: 'POST',
    body: JSON.stringify({
      conversation_id: convId,
      messages: messages
    }),
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(async res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500
      }
      return errRes
    })
  return response
}

export const historyDelete = async (convId: string): Promise<Response> => {
  const response = await fetch('/history/delete', {
    method: 'DELETE',
    body: JSON.stringify({
      conversation_id: convId
    }),
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500
      }
      return errRes
    })
  return response
}

export const historyDeleteAll = async (): Promise<Response> => {
  const response = await fetch('/history/delete_all', {
    method: 'DELETE',
    body: JSON.stringify({}),
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500
      }
      return errRes
    })
  return response
}

export const historyClear = async (convId: string): Promise<Response> => {
  const response = await fetch('/history/clear', {
    method: 'POST',
    body: JSON.stringify({
      conversation_id: convId
    }),
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500
      }
      return errRes
    })
  return response
}

export const historyRename = async (convId: string, title: string): Promise<Response> => {
  const response = await fetch('/history/rename', {
    method: 'POST',
    body: JSON.stringify({
      conversation_id: convId,
      title: title
    }),
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500
      }
      return errRes
    })
  return response
}

export const historyEnsure = async (): Promise<CosmosDBHealth> => {
  const response = await fetch('/history/ensure', {
    method: 'GET'
  })
    .then(async res => {
      const respJson = await res.json()
      let formattedResponse
      if (respJson.message) {
        formattedResponse = CosmosDBStatus.Working
      } else {
        if (res.status === 500) {
          formattedResponse = CosmosDBStatus.NotWorking
        } else if (res.status === 401) {
          formattedResponse = CosmosDBStatus.InvalidCredentials
        } else if (res.status === 422) {
          formattedResponse = respJson.error
        } else {
          formattedResponse = CosmosDBStatus.NotConfigured
        }
      }
      if (!res.ok) {
        return {
          cosmosDB: false,
          status: formattedResponse
        }
      } else {
        return {
          cosmosDB: true,
          status: formattedResponse
        }
      }
    })
    .catch(err => {
      console.error('There was an issue fetching your data.')
      return {
        cosmosDB: false,
        status: err
      }
    })
  return response
}

// export const getOrCreateUserSettings = async (userId: string) => {
//   try {
//       const response = await fetch(`/api/settings/${userId}`);
//       if (!response.ok) {
//           throw new Error('Network response was not ok');
//       }
//       return await response.json();
//   } catch (error) {
//       console.error('Error fetching settings:', error);
//   }
// };

// export const updateUserSettings = async (userId: string, systemMessage: string, temperature: number) => {
//   console.log(`Updating user settings for userId: ${userId} with systemMessage: ${systemMessage} and temperature: ${temperature}`);
//   try {
//       const response = await fetch(`/api/settings/${userId}`, {
//           method: 'POST',
//           headers: {
//               'Content-Type': 'application/json',
//           },
//           body: JSON.stringify({ systemMessage, temperature }),
//       });
//       if (!response.ok) {
//           const errorText = await response.text();
//           console.error('Error updating settings:', response.status, response.statusText, errorText);
//           throw new Error('Network response was not ok');
//       }
//       return await response.json();
//   } catch (error) {
//       console.error('Error updating settings:', error);
//   }
// };


export const frontendSettings = async (): Promise<Response | null> => {
  const response = await fetch('/frontend_settings', {
    method: 'GET'
  })
    .then(res => {
      return res.json()
    })
    .catch(_err => {
      console.error('There was an issue fetching your data.')
      return null
    })

  return response
}
export const historyMessageFeedback = async (messageId: string, feedback: string): Promise<Response> => {
  const response = await fetch('/history/message_feedback', {
    method: 'POST',
    body: JSON.stringify({
      message_id: messageId,
      message_feedback: feedback
    }),
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(res => {
      return res
    })
    .catch(_err => {
      console.error('There was an issue logging feedback.')
      const errRes: Response = {
        ...new Response(),
        ok: false,
        status: 500
      }
      return errRes
    })
  return response
}

export const getSharedConversation = async (sharedConversationId: string): Promise<Conversation | null> => {
  const response = await fetch(`/api/get_shared_conversation/${sharedConversationId}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(async res => {
      if (!res.ok) {
        const errorMessage = `Failed to fetch conversation: ${res.statusText}`;
        console.error(errorMessage);
        throw new Error(errorMessage);
      }
      return res.json();
    })
    .catch(err => {
      console.error('There was an issue fetching the shared conversation:', err);
      return null;
    });

  return response;
};

// Function to share a conversation
export const shareConversation = async (conversationId: string): Promise<string | null> => {
  const response = await fetch(`/api/share/${conversationId}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(async res => {
      if (!res.ok) {
        const errorMessage = `Failed to share conversation: ${res.statusText}`;
        console.error(errorMessage);
        throw new Error(errorMessage);
      }
      const data = await res.json();
      return data.shareableLink;
    })
    .catch(err => {
      console.error('There was an issue sharing the conversation:', err);
      return null;
    });

  return response;
};



export const sendErrorToBackend = async (
  error_message: string,
  user_message: string,
  user_id?: string,
  conversation_id?: string | null
): Promise<Response> => {
  const payload = {
    error_message: error_message,
    user_message: user_message,
    user_id: user_id || null,
    conversation_id: conversation_id || null
  };
  
  try {
    const response = await fetch('/api/upsert_error', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      throw new Error(`Failed to upsert error: ${response.statusText}`);
    }
    
    return response;
  } catch (error) {
    console.error('Error sending error message to backend:', error);
    throw error;
  }
};