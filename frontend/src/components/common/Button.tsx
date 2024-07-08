import { CommandBarButton, DefaultButton, IButtonProps, IButtonStyles, ICommandBarStyles } from '@fluentui/react'

import styles from './Button.module.css'

interface ButtonProps extends IButtonProps {
  onClick: () => void
  text: string | undefined
}

export const ShareButton: React.FC<ButtonProps> = ({ onClick, text }) => {
  return (
    <CommandBarButton
      className={styles.shareButtonRoot}
      iconProps={{ iconName: 'Share' }}
      onClick={onClick}
      text={text}
    />
  )
}

export const HistoryButton: React.FC<ButtonProps> = ({ onClick, text }) => {
  return (
    <DefaultButton
      className={styles.historyButtonRoot}
      text={text}
      iconProps={{ iconName: 'History' }}
      onClick={onClick}
    />
  )
}

interface HelpButtonProps extends IButtonProps {
  onClick: () => void;
  text: string;
}

export const SettingsButton: React.FC<HelpButtonProps> = ({onClick, text}) => {
  const SettingsButtonStyles: ICommandBarStyles & IButtonStyles = {
      root: {
          width: '100px',
          border: `1px solid #D1D1D1`,
        },
        rootHovered: {
          border: `1px solid #D1D1D1`,
        },
        rootPressed: {
          border: `1px solid #D1D1D1`,
        },
    };

    return (
      <DefaultButton
          text={text}
          iconProps={{ 
            iconName: 'Settings', 
            styles: {
              root: {
                  fontSize: '20px',
              },
          },
          }}
          onClick={onClick}
          styles={SettingsButtonStyles}
      />
    )
}


