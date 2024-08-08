import React from 'react';
import { Dialog, ChoiceGroup, IChoiceGroupOption } from '@fluentui/react';
import styles from './DatasourceSelect.module.css';

interface DatasourceSelectProps {
  isOpen: boolean;
  onDismiss: () => void;
  selectedKey: string | undefined;
  setSelectedKey: React.Dispatch<React.SetStateAction<string | undefined>>;
  validationMessage?: string;
}

const DatasourceSelect: React.FC<DatasourceSelectProps> = ({ 
  isOpen, 
  onDismiss, 
  selectedKey, 
  setSelectedKey,
  validationMessage
}) => {
  const options: IChoiceGroupOption[] = [
    { key: 'none', text: 'None' },
    { key: 'cinc-qms-documents-index', text: 'CINC QMS Documents' },
    { key: 'cinc-manu-proce-documents-index', text: 'CINC Manufacturing Procedures' },
    { key: 'cinc-fda-audit-documents-index', text: 'CINC FDA Audit 2024 Documents' },
    { key: 'cmms-agile-documents-index', text: 'CMMS Agile Documents' },
  ];

  const onChangeDataSource = (
    _event?: React.FormEvent<HTMLElement | HTMLInputElement>,
    option?: IChoiceGroupOption
  ) => {
    if (option) {
      setSelectedKey(option.key);
    }
  };

  return (
    <Dialog
      onDismiss={onDismiss}
      hidden={!isOpen}
      dialogContentProps={{
        title: 'Datasource Settings',
      }}
    >
      <ChoiceGroup
        options={options}
        selectedKey={selectedKey}
        onChange={onChangeDataSource}
      />
      <br></br>
      {validationMessage && <div className={styles.validationMessage}>{validationMessage}</div>}
      <div className={styles.buttonCenter}>
        <button
          onClick={onDismiss}
          className={styles.buttonSelect}
        >
          Select
        </button>
      </div>
    </Dialog>
  );
};

export default DatasourceSelect;
