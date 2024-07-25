import React from 'react';
import { Dialog, ChoiceGroup, IChoiceGroupOption } from '@fluentui/react';

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
    { key: 'cinc_qms', text: 'CINC QMS' },
    { key: 'cmh_qms', text: 'CMH QMS' },
    { key: 'marketing', text: 'Marketing' },
    { key: 'hr', text: 'HR' },
    { key: 'rd', text: 'R&D' }
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
      {validationMessage && <div style={{ color: 'red' }}>{validationMessage}</div>}
    </Dialog>
  );
};

export default DatasourceSelect;
