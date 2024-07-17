import { CommandBarButton, DefaultButton, IButtonProps, ICommandBarStyles, IButtonStyles } from '@fluentui/react'

import styles from './Button.module.css'

interface ShareButtonProps {
  conversationId: string;
  onShareClick: (link: string) => void;
}

export const ShareButton: React.FC<ShareButtonProps> = ({  conversationId, onShareClick }) => {

  const handleShare = async (conversationId: string) => {
    try {
        const response = await fetch(`/api/share/${conversationId}`);
        const data = await response.json();
        if (data.shareableLink) {
          onShareClick(data.shareableLink);
        }
    } catch (error) {
        console.error('Error sharing conversation:', error);
    }
  }; 
  return (
    <CommandBarButton
      className={styles.shareButtonRoot}
      iconProps={{ iconName: 'Share' }}
      onClick={()=>handleShare(conversationId)}
      text="Share"
    />
  )
}

interface HistoryButtonProps extends IButtonProps {
  onClick: () => void;
  text: string;
}


export const HistoryButton: React.FC<HistoryButtonProps> = ({ onClick, text }) => {
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

export const HelpButton: React.FC<HelpButtonProps> = ({onClick, text}) => {
  const HelpButtonStyles: ICommandBarStyles & IButtonStyles = {
      root: {
          width: '80px',
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
            iconName: 'StatusCircleQuestionMark', 
            styles: {
              root: {
                  fontSize: '20px',
              },
          },
          }}
          onClick={onClick}
          styles={HelpButtonStyles}
      />
    )
}

// export const SettingsButton: React.FC<HelpButtonProps> = ({onClick, text}) => {
//   const SettingsButtonStyles: ICommandBarStyles & IButtonStyles = {
//       root: {
//           width: '100px',
//           border: `1px solid #D1D1D1`,
//         },
//         rootHovered: {
//           border: `1px solid #D1D1D1`,
//         },
//         rootPressed: {
//           border: `1px solid #D1D1D1`,
//         },
//     };

//     return (
//       <DefaultButton
//           text={text}
//           iconProps={{ 
//             iconName: 'Settings', 
//             styles: {
//               root: {
//                   fontSize: '20px',
//               },
//           },
//           }}
//           onClick={onClick}
//           styles={SettingsButtonStyles}
//       />
//     )
// }