import { Conversation as ConversationModel } from '../../api/models'
import { useEffect, useState, useContext, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { CommandBarButton, IconButton, Dialog, DialogType, Stack } from '@fluentui/react'
import { ErrorCircleRegular } from '@fluentui/react-icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import DOMPurify from 'dompurify'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { nord } from 'react-syntax-highlighter/dist/esm/styles/prism'
import styles from './SharedConversation.module.css'
import { AppStateContext } from '../../state/AppProvider'
import {
  ChatMessage,
  ConversationRequest,
  conversationApi,
  Citation,
  ToolMessageContent,
  AzureSqlServerExecResults,
  ChatResponse,
  getUserInfo,
  Conversation,
  historyGenerate,
  historyUpdate,
  historyClear,
  ChatHistoryLoadingState,
  CosmosDBStatus,
  ErrorMessage,
  ExecResults,
  getSharedConversation
} from '../../api'
import { Answer } from '../../components/Answer'
import { XSSAllowTags } from '../../constants/sanatizeAllowables'
import uuid from 'react-uuid'
import { isEmpty } from 'lodash'
import { Oval } from 'react-loader-spinner'

const enum messageStatus {
  NotRunning = 'Not Running',
  Processing = 'Processing',
  Done = 'Done'
}

const SharedConversation = () => {
  let { sharedConversationId } = useParams<{ sharedConversationId: string }>()
  const [conversation, setConversation] = useState<ConversationModel | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [activeCitation, setActiveCitation] = useState<Citation>()
  const [isCitationPanelOpen, setIsCitationPanelOpen] = useState<boolean>(false)
  const [error, setError] = useState<string>('')
  const appStateContext = useContext(AppStateContext)
  const [execResults, setExecResults] = useState<ExecResults[]>([])
  const [processMessages, setProcessMessages] = useState<messageStatus>(messageStatus.NotRunning)
  const [errorMsg, setErrorMsg] = useState<ErrorMessage | null>()
  const isSharedConversation = true;

  useEffect(() => {
    const fetchUserId = async () => {
      try {
        const response = await fetch('/get_user_id')
        if (response.ok) {
          const data = await response.json()
          appStateContext?.dispatch({
            type: 'UPDATE_CURRENT_USER_ID',
            payload: data.userId
          })
        }
      } catch (error) {
        console.error('Error fetching user ID:', error)
      }
    }
    fetchUserId()
  }, [])

  const errorDialogContentProps = {
    type: DialogType.close,
    title: errorMsg?.title,
    closeButtonAriaLabel: 'Close',
    subText: errorMsg?.subtitle
  }

  const modalProps = {
    titleAriaId: 'labelId',
    subtitleAriaId: 'subTextId',
    isBlocking: true,
    styles: { main: { maxWidth: 450 } }
  }

  const [ASSISTANT, TOOL, ERROR] = ['assistant', 'tool', 'error']
  const NO_CONTENT_ERROR = 'No content in messages object.'

  useEffect(() => {
    appStateContext?.dispatch({ type: 'TOGGLE_RIGHT_WRAPPER_BUTTONS', payload: true })

    return () => {
      appStateContext?.dispatch({ type: 'TOGGLE_RIGHT_WRAPPER_BUTTONS', payload: false })
    }
  }, [])

  useEffect(() => {
    const fetchConversation = async () => {
      if (!sharedConversationId) {
        setError('No shared conversation ID provided.')
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        console.log(`Fetching shared conversation with ID: ${sharedConversationId}`)
        const data = await getSharedConversation(sharedConversationId)
        if (!data) {
          const errorMessage = `Failed to fetch conversation with ID: ${sharedConversationId}`
          console.error(errorMessage)
          setError(errorMessage)
          return
        }
        console.log('Fetched conversation data:', data)
        setConversation(data)
        setMessages(data.messages || [])
      } catch (error) {
        console.error('Error fetching conversation:', error)
        setError('Error fetching conversation')
      } finally {
        setIsLoading(false)
      }
    }

    fetchConversation()
  }, [sharedConversationId])

  const onShowCitation = (citation: Citation) => {
    setActiveCitation(citation)
    setIsCitationPanelOpen(true)
  }

  const onViewSource = (citation: Citation, event: React.MouseEvent<HTMLElement, MouseEvent>) => {
    event.preventDefault()

    if (citation.url && !citation.url.includes('blob.core')) {
      window.open(citation.url, '_blank')
    } else if (citation.title) {
      const cleanedTitle = citation.title.replace(/-Rev\d+|\.pdf/g, '')
      const url = `https://plmdata-cinc.cookgroup.nao/documents/${cleanedTitle}`
      window.open(url, '_blank')
    }
  }

  const parseCitationFromMessage = (message: ChatMessage) => {
    if (message?.role && message?.role === 'tool') {
      try {
        const toolMessage = JSON.parse(message.content) as ToolMessageContent
        return toolMessage.citations
      } catch {
        return []
      }
    }
    return []
  }

  const parsePlotFromMessage = (message: ChatMessage) => {
    if (message?.role && message?.role === 'tool') {
      try {
        const execResults = JSON.parse(message.content) as AzureSqlServerExecResults
        const codeExecResult = execResults.all_exec_results.at(-1)?.code_exec_result
        if (codeExecResult === undefined) {
          return null
        }
        return codeExecResult
      } catch {
        return null
      }
    }
    return null
  }

  let assistantMessage = {} as ChatMessage
  let toolMessage = {} as ChatMessage
  let assistantContent = ''

  const processResultMessage = (resultMessage: ChatMessage, userMessage: ChatMessage, conversationId?: string) => {
    if (resultMessage.content.includes('all_exec_results')) {
      const parsedExecResults = JSON.parse(resultMessage.content) as AzureSqlServerExecResults
      setExecResults(parsedExecResults.all_exec_results)
    }

    if (resultMessage.role === ASSISTANT) {
      assistantContent += resultMessage.content
      assistantMessage = resultMessage
      assistantMessage.content = assistantContent

      if (resultMessage.context) {
        toolMessage = {
          id: uuid(),
          role: TOOL,
          content: resultMessage.context,
          date: new Date().toISOString()
        }
      }
    }

    if (resultMessage.role === TOOL) toolMessage = resultMessage

    if (!conversationId) {
      isEmpty(toolMessage)
        ? setMessages([...messages, userMessage, assistantMessage])
        : setMessages([...messages, userMessage, toolMessage, assistantMessage])
    } else {
      isEmpty(toolMessage)
        ? setMessages([...messages, assistantMessage])
        : setMessages([...messages, toolMessage, assistantMessage])
    }
  }

  if (error) {
    return <p>{`There was an error fetching the shared conversation: ${error}`}</p>
  }

  if (isLoading) {
    return (
      <div className={styles.loaderContainer}>
        <Oval color="#0078D4" height={80} width={80} />
      </div>
    )
  }

  if (!conversation) {
    return <p>Conversation not found.</p>
  }

  return (
    <div className={styles.container} role="main">
      <div className={styles.titleContainer}>
        <div className={styles.title}>Shared Conversation</div>
      </div>

      {!messages || messages.length < 1 ? (
        <Stack className={styles.chatEmptyState}>
          <h1 className={styles.chatEmptyStateTitle}>No messages in this conversation.</h1>
        </Stack>
      ) : (
        <div className={styles.chatMessageStream} style={{ marginBottom: isLoading ? '40px' : '0px' }} role="log">
          {messages.map((answer, index) => (
            <>
              {answer.role === 'user' ? (
                <div className={styles.chatMessageUser} tabIndex={0}>
                  <div className={styles.chatMessageUserMessage}>{answer.content}</div>
                </div>
              ) : answer.role === 'assistant' ? (
                <div className={styles.chatMessageGpt}>
                  <Answer
                    answer={{
                      answer: answer.content,
                      citations: parseCitationFromMessage(messages[index - 1]),
                      plotly_data: parsePlotFromMessage(messages[index - 1]),
                      message_id: answer.id,
                      exec_results: execResults
                    }}
                    onCitationClicked={c => onShowCitation(c)}
                    onExectResultClicked={() => {}}
                    isSharedConversation={isSharedConversation}
                  />
                </div>
              ) : answer.role === 'error' ? (
                <div className={styles.chatMessageError}>
                  <Stack horizontal className={styles.chatMessageErrorContent}>
                    <ErrorCircleRegular className={styles.errorIcon} style={{ color: 'rgba(182, 52, 67, 1)' }} />
                    <span>Error</span>
                  </Stack>
                  <div
                    className={styles.chatMessageErrorContent}
                    dangerouslySetInnerHTML={{ __html: answer.content }}></div>
                </div>
              ) : null}
            </>
          ))}
        </div>
      )}

      {messages && messages.length > 0 && isCitationPanelOpen && activeCitation && (
        <Stack.Item className={styles.citationPanel} tabIndex={0} role="tabpanel" aria-label="Citations Panel">
          <Stack
            aria-label="Citations Panel Header Container"
            horizontal
            className={styles.citationPanelHeaderContainer}
            horizontalAlign="space-between"
            verticalAlign="center">
            <span aria-label="Citations" className={styles.citationPanelHeader}>
              Citations
            </span>
            <IconButton
              iconProps={{ iconName: 'Cancel' }}
              aria-label="Close citations panel"
              onClick={() => setIsCitationPanelOpen(false)}
            />
          </Stack>
          <h5
            className={styles.citationPanelTitle}
            tabIndex={0}
            title={
              activeCitation.url && !activeCitation.url.includes('blob.core')
                ? activeCitation.url
                : activeCitation.title ?? ''
            }
            onClick={event => onViewSource(activeCitation, event)}>
            {activeCitation.title}
          </h5>
          <div tabIndex={0}>
            <ReactMarkdown
              linkTarget="_blank"
              className={styles.citationPanelContent}
              children={DOMPurify.sanitize(activeCitation.content, { ALLOWED_TAGS: XSSAllowTags })}
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
            />
          </div>
        </Stack.Item>
      )}
    </div>
  )
}

export default SharedConversation
