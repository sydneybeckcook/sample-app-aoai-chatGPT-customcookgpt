import { Conversation as ConversationModel } from '../../api/models';
import 'react-tooltip/dist/react-tooltip.css'
import { useEffect, useState, useContext, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { Stack, IconButton } from '@fluentui/react';
import { ErrorCircleRegular } from '@fluentui/react-icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import DOMPurify from 'dompurify';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { nord } from 'react-syntax-highlighter/dist/esm/styles/prism';
import styles from './SharedConversation.module.css';
import UserIcon from '../../assets/user.svg';
import RobotIcon from '../../assets/robot.svg';
import { AppStateContext } from '../../state/AppProvider';
import { ChatMessage, Citation, ToolMessageContent, AzureSqlServerExecResults } from '../../api';
import { Answer } from '../../components/Answer';
import { XSSAllowTags } from '../../constants/sanatizeAllowables'


const SharedConversation = () => {
    let { sharedConversationId } = useParams<{ sharedConversationId: string }>();
    const [conversation, setConversation] = useState<ConversationModel | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [activeCitation, setActiveCitation] = useState<Citation>();
    const [isCitationPanelOpen, setIsCitationPanelOpen] = useState<boolean>(false);
    const [error, setError] = useState<string>("");
    const appStateContext = useContext(AppStateContext);

    useEffect(() => {
        appStateContext?.dispatch({ type: 'TOGGLE_RIGHT_WRAPPER_BUTTONS', payload: true });
    
        return () => {
            appStateContext?.dispatch({ type: 'TOGGLE_RIGHT_WRAPPER_BUTTONS', payload: false });
        };
    }, []);

    useEffect(() => {
        const fetchConversation = async () => {
            try {
                setIsLoading(true);
                console.log(`Fetching shared conversation with ID: ${sharedConversationId}`);
                const response = await fetch(`/api/get_shared_conversation/${sharedConversationId}`);
                if (!response.ok) {
                    const errorMessage = `Failed to fetch conversation: ${response.statusText}`;
                    console.error(errorMessage);
                    setError(errorMessage);
                    return;
                }
                const data = await response.json();
                console.log('Fetched conversation data:', data);
                setConversation(data);
                setMessages(data.messages || []);
            } catch (error) {
                console.error('Error fetching conversation:', error);
                setError('Error fetching conversation');
            } finally {
                setIsLoading(false);
            }
        };

        fetchConversation();
    }, [sharedConversationId]);

    const onShowCitation = (citation: Citation) => {
        setActiveCitation(citation);
        setIsCitationPanelOpen(true);
    };

    const onViewSource = (citation: Citation, event: React.MouseEvent<HTMLElement, MouseEvent>) => {
        event.preventDefault();
    
        if (citation.url && !citation.url.includes('blob.core')) {
          window.open(citation.url, '_blank');
        } else if (citation.title) {
          const cleanedTitle = citation.title.replace(/-Rev\d+|\.pdf/g, '');
          const url = `https://plmdata-cinc.cookgroup.nao/documents/${cleanedTitle}`;
          window.open(url, "_blank");
        }
      };
    
    const parseCitationFromMessage = (message: ChatMessage) => {
    if (message?.role && message?.role === "tool") {
        try {
        const toolMessage = JSON.parse(message.content) as ToolMessageContent;
        return toolMessage.citations;
        } catch {
        return [];
        }
    }
    return [];
    };
    
    const parsePlotFromMessage = (message: ChatMessage) => {
        if (message?.role && message?.role === "tool") {
          try {
            const execResults = JSON.parse(message.content) as AzureSqlServerExecResults;
            const codeExecResult = execResults.all_exec_results.at(-1)?.code_exec_result;
            if (codeExecResult === undefined) {
              return null;
            }
            return codeExecResult;
          } catch {
            return null;
          }
        }
        return null;
      };

    if (error) {
    return <p>{error}</p>;
    }

    if (isLoading) {
    return <p>Loading conversation...</p>;
    }

    if (!conversation) {
    return <p>Conversation not found.</p>;
    }

    return (
        <div className={styles.container} role="main">
          <div className={styles.titleContainer}>
            <div className={styles.title}>Shared Conversation</div>
          </div>
          {messages.map((answer, index) => (
            <div key={index}>
              {answer.role === "user" ? (
                <div className={styles.chatMessageUser} tabIndex={0}>
                  <Stack horizontal className={styles.userMessageAndIcon}>
                    <img src={UserIcon} className={styles.userIcon} alt="User" />
                    <div className={styles.chatMessageUserMessage}>{answer.content}</div>
                  </Stack>
                </div>
              ) : answer.role === "assistant" ? (
                <div className={styles.chatMessageGpt}>
                  <Stack horizontal className={styles.gptMessageAndIcon}>
                    <img src={RobotIcon} className={styles.gptIcon} alt="Assistant" />
                    <Answer
                      answer={{
                        answer: answer.content,
                        citations: parseCitationFromMessage(messages[index - 1]),
                        plotly_data: parsePlotFromMessage(messages[index - 1]),
                        message_id: answer.id,
                        feedback: answer.feedback,
                      }}
                      onCitationClicked={(c) => onShowCitation(c)}
                      onExectResultClicked={() => {}}
                    />
                  </Stack>
                </div>
              ) : answer.role === "error" ? (
                <div className={styles.chatMessageError}>
                  <Stack horizontal className={styles.chatMessageErrorContent}>
                    <ErrorCircleRegular className={styles.errorIcon} style={{ color: "rgba(182, 52, 67, 1)" }} />
                    <span>Error</span>
                  </Stack>
                  <div
                    className={styles.chatMessageErrorContent}
                    dangerouslySetInnerHTML={{ __html: answer.content }}
                  ></div>
                </div>
              ) : null}
            </div>
          ))}
          {messages && messages.length > 0 && isCitationPanelOpen && activeCitation && (
            <Stack.Item className={styles.citationPanel} tabIndex={0} role="tabpanel" aria-label="Citations Panel">
              <Stack
                aria-label="Citations Panel Header Container"
                horizontal
                className={styles.citationPanelHeaderContainer}
                horizontalAlign="space-between"
                verticalAlign="center"
              >
                <span aria-label="Citations" className={styles.citationPanelHeader}>
                  Citations
                </span>
                <IconButton
                  iconProps={{ iconName: "Cancel" }}
                  aria-label="Close citations panel"
                  onClick={() => setIsCitationPanelOpen(false)}
                />
              </Stack>
              <h5
                className={styles.citationPanelTitle}
                tabIndex={0}
                title={
                  activeCitation.url && !activeCitation.url.includes("blob.core")
                    ? activeCitation.url
                    : activeCitation.title ?? ""
                }
                onClick={(event) => onViewSource(activeCitation, event)}
              >
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
      );
    }

export default SharedConversation;