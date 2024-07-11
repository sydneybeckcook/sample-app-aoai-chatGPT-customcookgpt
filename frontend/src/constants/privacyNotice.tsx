import React, { useState, useEffect } from 'react';
import { Dialog } from '@fluentui/react';

const PrivacyNotice: React.FC = () => {
    const [privacyNotice, setPrivacyNotice] = useState<string>('');
    const [isDialogOpen, setIsDialogOpen] = useState<boolean>(false);

    useEffect(() => {
        fetch('/check_privacy_response')
            .then(response => response.json())
            .then(data => {
                if (!data.hasResponded) {
                    setIsDialogOpen(true);
                    fetchPrivacyNotice();
                }
            })
            .catch(error => console.error('Error:', error));
    }, []);

    const fetchPrivacyNotice = () => {
        fetch('/privacy_notice')
            .then(response => response.text())
            .then(text => {
                setPrivacyNotice(text);
                setIsDialogOpen(true);
            })
            .catch(error => console.error('Error:', error));
    };

    const handleAccept = () => {
        fetch('/record_privacy_response', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ response: 'accept' })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            setIsDialogOpen(false);
        })
        .catch((error) => {
            console.error('Error:', error);
        });
    };    

    const titleStyles = {
        title: {
            paddingBottom: 0,
        },
    };

    return (
        <Dialog
            hidden={!isDialogOpen}
            dialogContentProps={{
                title: "Privacy Notice",
                showCloseButton: false,
                styles: titleStyles,
            }}
            modalProps={{
                isBlocking: true,
                styles: { main: { maxWidth: 450 } },
            }}
            styles={{
                main: {
                    maxWidth: '600px',
                    background: "#FFFFFF",
                    boxShadow: "0px 14px 28.8px rgba(0, 0, 0, 0.24), 0px 0px 8px rgba(0, 0, 0, 0.2)",
                    borderRadius: "8px",
                    maxHeight: '200px',
                    minHeight: '100px',
                    selectors: {
                        '@media (min-width: 480px)': {
                            maxWidth: '600px',
                        }
                    }
                }
            }}
        >
            <p>{privacyNotice}</p>
            <button onClick={handleAccept}>Accept</button>
        </Dialog>
    );
};

export default PrivacyNotice;