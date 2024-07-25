import { useContext, useEffect, useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { Dialog, Stack, TextField, DefaultButton, Slider, ChoiceGroup, IChoiceGroupOption } from '@fluentui/react'
import { CopyRegular } from '@fluentui/react-icons'

// import {getOrCreateUserSettings, updateUserSettings } from '../../api'
import { CosmosDBStatus, getDatasource, upsertDatasource, checkCreateDatasource } from '../../api'
import Contoso from '../../assets/Contoso.svg'
// import { SettingsButton } from '../../components/common/Button'
import { HistoryButton, ShareButton, HelpButton, DataButton } from '../../components/common/Button'
import CookLogo from '../../assets/CookLogo.svg'
import { AppStateContext } from '../../state/AppProvider'
import PrivacyNotice from '../../constants/privacyNotice'
import DatasourceSelect from '../../constants/datasourceSelect'

import styles from './Layout.module.css'

const Layout = () => {
  const [isSharePanelOpen, setIsSharePanelOpen] = useState<boolean>(false)
  // const [isSettingsPanelOpen, setIsSettingsPanelOpen] = useState<boolean>(false)
  const [copyClicked, setCopyClicked] = useState<boolean>(false)
  const [copyText, setCopyText] = useState<string>('Copy URL')
  const [shareLabel, setShareLabel] = useState<string | undefined>('Share')
  const [isHelpPanelOpen, setIsHelpPanelOpen] = useState<boolean>(false)
  const [isDataPanelOpen, setIsDataPanelOpen] = useState<boolean>(false)
  const [selectedKey, setSelectedKey] = useState<string | undefined>(undefined);;
  const [hideHistoryLabel, setHideHistoryLabel] = useState<string>('Hide chat history')
  const [showHistoryLabel, setShowHistoryLabel] = useState<string>('Show chat history')
  const [logo, setLogo] = useState('')
  const appStateContext = useContext(AppStateContext)
  const currentConversationId = appStateContext?.state.currentConversationId
  const currentUserId = appStateContext?.state.currentUserId
  const [shareableLink, setShareableLink] = useState('')
  const ui = appStateContext?.state.frontendSettings?.ui
  const [isDataChecked, setIsDataChecked] = useState(false);
  // const defaultSystemMessage = import.meta.env.VITE_AZURE_OPENAI_SYSTEM_MESSAGE || "You are an AI assistant that helps Cook Medical employees find information.";
  // const defaultTemperature = import.meta.env.VITE_AZURE_OPENAI_TEMPERATURE || "0.7";
  // const [systemMessage, setSystemMessage] = useState(defaultSystemMessage);
  // const [temperature, setTemperature] = useState(defaultTemperature);

  // const options: IChoiceGroupOption[] = [
  //   { key: 'none', text: 'None' },
  //   { key: 'cinc_qms', text: 'CINC QMS' },
  //   { key: 'cmh_qms', text: 'CMH QMS' },
  //   { key: 'marketing', text: 'Marketing' },
  //   { key: 'hr', text: 'HR' },
  //   { key: 'rd', text: 'R&D' },
  // ];

  const handleShareClick = (link: string) => {
    setShareableLink(link)
    setIsSharePanelOpen(true)
  }

  const handleSharePanelDismiss = () => {
    setIsSharePanelOpen(false)
    setCopyClicked(false)
    setCopyText('Copy URL')
  }

  const handleCopyClick = () => {
    navigator.clipboard.writeText(window.location.href)
    setCopyClicked(true)
  }

  const handleHistoryClick = () => {
    appStateContext?.dispatch({ type: 'TOGGLE_CHAT_HISTORY' })
  }

  // const handleSettingsClick = async () => {
  //   setIsSettingsPanelOpen(true);
  //   console.log('currentUserId:', {currentUserId})
  //   if (currentUserId) {
  //     console.log('currentUserId:', 'true')
  //     const settings = await getOrCreateUserSettings(currentUserId);
  //     console.log("settings", settings)
  //     if (settings) {
  //         setSystemMessage(settings.systemMessage);
  //         setTemperature(settings.temperature);
  //     }
  //   }
  // }

  // const handleSettingsPanelDismiss = () => {
  //   console.log('Dismissing settings panel with values:', { currentUserId, systemMessage, temperature });
  //   setIsSettingsPanelOpen(false);

  //   if (currentUserId) {
  //       console.log("Updating User Settings with values:", { currentUserId, systemMessage, temperature })
  //       updateUserSettings(currentUserId, systemMessage, parseFloat(temperature));
  //   }
  // }

  // const handleSystemMessageChange = (event: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>, newValue?: string) => {
  //   setSystemMessage(newValue || '');
  // }

  // const handleTemperatureChange = (newValue: number) => {
  //   setTemperature(newValue.toString());
  // }

  // const resetToDefaults = () => {
  //   setSystemMessage(defaultSystemMessage);
  //   setTemperature(defaultTemperature);
  // }

  const handleHelpClick = () => {
    setIsHelpPanelOpen(true)
  }

  const handleHelpPanelDismiss = () => {
    setIsHelpPanelOpen(false)
  }
  useEffect(() => {
    const fetchDatasource = async () => {
      try {
        console.log('Fetching datasource');
        const response = await getDatasource();
        console.log('Response:', response);
        if (!response.ok) {
          console.error('Network response was not ok');
          throw new Error('Network response was not ok');

        } 
        const data = await response.json()
        console.log('Response data:', data);
        
        if (data.retrieved_datasource) {
          console.log('Setting selected key:', data.retrieved_datasource);
          setSelectedKey(data.retrieved_datasource);
        }else{
          setSelectedKey("none");
        }
      } catch (error) {
          console.error('Failed to retrieve datasource:', error);
          setSelectedKey("none")
        }
    };

    fetchDatasource();
  }, []);



  const handleDataClick = async () => {
    setIsDataPanelOpen(true);
    try {
      console.log('Fetching datasource');
      const response = await getDatasource();
      console.log('Response:', response);
      if (!response.ok) {
        console.error('Network response was not ok');
        throw new Error('Network response was not ok');

      } 
      const data = await response.json()
      console.log('Response data:', data);
      
      if (data.retrieved_datasource) {
        console.log('Setting selected key:', data.retrieved_datasource);
        setSelectedKey(data.retrieved_datasource);
      }else{
        setSelectedKey("none");
      }
    } catch (error) {
        console.error('Failed to retrieve datasource:', error);
        setSelectedKey("none")
      }
  }

  const handleDataPanelDismiss = async () => {
    if (selectedKey) {
      console.log('Selected key to upsert:', selectedKey);
      try {
        const response = await upsertDatasource(selectedKey);
        console.log('Upsert response:', response);
        if (!response.ok) {
          console.error('Network response was not ok');
          throw new Error('Network response was not ok');
        }
        console.log('Datasource upserted successfully');
      } catch (error) {
        console.error('Failed to upsert datasource:', error);
      }
    }
    setIsDataPanelOpen(false);
    console.log('Datasource panel closed');
  };

  useEffect(() => {
    if (copyClicked) {
      setCopyText('Copied URL')
    }
  }, [copyClicked])

  useEffect(() => { }, [appStateContext?.state.isCosmosDBAvailable.status])

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 480) {
        setShareLabel(undefined)
        setHideHistoryLabel('Hide history')
        setShowHistoryLabel('Show history')
      } else {
        setShareLabel('Share')
        setHideHistoryLabel('Hide chat history')
        setShowHistoryLabel('Show chat history')
      }
    }

    window.addEventListener('resize', handleResize)
    handleResize()

    return () => window.removeEventListener('resize', handleResize)
  }, [])

  useEffect(() => {
    const checkDatasource = async () => {
      try {
        const response = await checkCreateDatasource();
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const data = await response.json();
        if (data.exists) {
          console.log('Datasource settings already exist');
        } else {
          console.log('Datasource settings created');
        }
        setIsDataChecked(true);
      } catch (error) {
        console.error('Failed to check/create datasource:', error);
      }
    };

    checkDatasource();
  }, []);

  return (
    <div className={styles.layout}>
      <PrivacyNotice />
      <header className={styles.header} role={'banner'}>
        <Stack horizontal verticalAlign="center" horizontalAlign="space-between">
          <img src={ui?.logo ? ui.logo : CookLogo} className={styles.headerIcon} aria-hidden="true" alt="" />
          <Link to="/" className={styles.headerTitleContainer}>
            <h1 className={styles.headerTitle}>Custom CookGPT Beta</h1>
          </Link>
          <Stack horizontal tokens={{ childrenGap: 4 }} className={styles.shareButtonContainer}>
            {appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured && ui?.show_chat_history_button !== false && (
              <HistoryButton
                onClick={handleHistoryClick}
                text={appStateContext?.state?.isChatHistoryOpen ? hideHistoryLabel : showHistoryLabel}
              />
            )}
            {!appStateContext?.state.hideRightWrapperButtons && <DataButton onClick={handleDataClick} text="Data Settings" />}
            {!appStateContext?.state.hideRightWrapperButtons && <HelpButton onClick={handleHelpClick} text="Help" />}
            {/* {!appStateContext?.state.hideRightWrapperButtons && (
              <SettingsButton onClick={handleSettingsClick} text="Settings" />
            )} */}
            {ui?.show_share_button && currentConversationId && (
              <ShareButton conversationId={currentConversationId} onShareClick={handleShareClick} />
            )}
          </Stack>
        </Stack>
      </header>
      <Outlet />
      <Dialog
        onDismiss={handleSharePanelDismiss}
        hidden={!isSharePanelOpen}
        styles={{
          main: [
            {
              selectors: {
                ['@media (min-width: 480px)']: {
                  maxWidth: '600px',
                  background: '#FFFFFF',
                  boxShadow: '0px 14px 28.8px rgba(0, 0, 0, 0.24), 0px 0px 8px rgba(0, 0, 0, 0.2)',
                  borderRadius: '8px',
                  maxHeight: '200px',
                  minHeight: '100px'
                }
              }
            }
          ]
        }}
        dialogContentProps={{
          title: 'Share this convesation',
          showCloseButton: true
        }}>
        <Stack horizontal verticalAlign="center" style={{ gap: '8px' }}>
          <TextField className={styles.urlTextBox} defaultValue={shareableLink} readOnly />
          <div
            className={styles.copyButtonContainer}
            role="button"
            tabIndex={0}
            aria-label="Copy"
            onClick={handleCopyClick}
            onKeyDown={e => (e.key === 'Enter' || e.key === ' ' ? handleCopyClick() : null)}>
            <CopyRegular className={styles.copyButton} />
            <span className={styles.copyButtonText}>{copyText}</span>
          </div>
        </Stack>
      </Dialog>
      <Dialog
        onDismiss={handleHelpPanelDismiss}
        hidden={!isHelpPanelOpen}
        dialogContentProps={{
          title: 'Help'
        }}
        styles={{
          main: [
            {
              selectors: {
                ['@media (min-width: 480px)']: {
                  maxWidth: '800px',
                  background: '#FFFFFF',
                  boxShadow: '0px 14px 28.8px rgba(0, 0, 0, 0.24), 0px 0px 8px rgba(0, 0, 0, 0.2)',
                  borderRadius: '8px',
                  maxHeight: '800px'
                }
              }
            }
          ]
        }}>
        <div>
          <p>
            Please email <a href="mailto:CookGPT@cookmedical.com">CookGPT@cookmedical.com</a> if you need any help or
            encounter any errors.
            <br></br>
            <br></br>
            Please use the "Share" button to include any conversations in your email.
          </p>
          <br></br>
        </div>
      </Dialog>
      <DatasourceSelect
        isOpen={isDataPanelOpen}
        onDismiss={handleDataPanelDismiss} 
        selectedKey={selectedKey}
        setSelectedKey={setSelectedKey}
      />
      {/*
      <Dialog
        onDismiss={handleDataPanelDismiss}
        hidden={!isDataPanelOpen}
        dialogContentProps={{
          title: 'Datasource Settings'
        }}
        styles={{
          main: [
            {
              selectors: {
                ['@media (min-width: 480px)']: {
                  maxWidth: '800px',
                  background: '#FFFFFF',
                  boxShadow: '0px 14px 28.8px rgba(0, 0, 0, 0.24), 0px 0px 8px rgba(0, 0, 0, 0.2)',
                  borderRadius: '8px',
                  maxHeight: '800px'
                }
              }
            }
          ]
        }}
      >
        <div>
          <ChoiceGroup
            label="Select a datasource"
            options={options}
            selectedKey={selectedKey}
            onChange={onChangeDataSource}
            required
          />
        </div>
      </Dialog>
      */}
      {/* <Dialog
        onDismiss={handleSettingsPanelDismiss}
        hidden={!isSettingsPanelOpen}
        dialogContentProps={{
          title: 'Settings'
        }}
        styles={{
          main: [
            {
              selectors: {
                ['@media (min-width: 700px)']: {
                  maxWidth: '900px',
                  background: '#FFFFFF',
                  boxShadow: '0px 14px 28.8px rgba(0, 0, 0, 0.24), 0px 0px 8px rgba(0, 0, 0, 0.2)',
                  borderRadius: '8px',
                  maxHeight: '800px'
                }
              }
            }
          ]
        }}>
        <div>
          <TextField
            label="System Message"
            multiline
            rows={3}
            value={systemMessage}
            onChange={handleSystemMessageChange}
          />
          <br></br>
          <Slider
            label="Temperature"
            min={0}
            max={1}
            step={0.1}
            value={parseFloat(temperature)}
            onChange={handleTemperatureChange}
            showValue
          />
          <br></br>
          <br></br>
          <DefaultButton
            text="Reset to Defaults"
            onClick={resetToDefaults}
            styles={{
              root: {
                backgroundColor: 'red',
                borderColor: 'red',
                color: 'white'
              },
              rootHovered: {
                backgroundColor: 'darkred',
                borderColor: 'darkred',
                color: 'white'
              }
            }}
          />
        </div>
      </Dialog> */}
    </div>
  )
}

export default Layout
