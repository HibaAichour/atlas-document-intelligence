import './App.css'

import { ChatPanel } from './components/ChatPanel'
import { DocumentsPanel } from './components/DocumentsPanel'
import { HealthStatus } from './components/HealthStatus'
import { useChat } from './hooks/useChat'
import { useDocuments } from './hooks/useDocuments'
import { useMessages } from './lib/i18n'

function App() {
  const t = useMessages()
  const documents = useDocuments()
  const chat = useChat(documents.selectedIds)

  return (
    <div className="app">
      <header className="app-header glass">
        <div className="brand">
          <span className="brand-text">
            <span className="brand-name">ATLAS</span>
            <span className="brand-tagline">{t.brandTagline}</span>
          </span>
        </div>
        <HealthStatus />
      </header>

      <div className="workspace">
        <DocumentsPanel
          documents={documents.documents}
          listState={documents.listState}
          listError={documents.listError}
          selectedIds={documents.selectedIds}
          isUploading={documents.isUploading}
          uploadError={documents.uploadError}
          onUpload={(file) => void documents.upload(file)}
          onToggle={documents.toggle}
        />

        <ChatPanel
          messages={chat.messages}
          isWaiting={chat.isWaiting}
          canAsk={documents.selectedIds.size > 0}
          onAsk={(question) => void chat.ask(question)}
        />
      </div>
    </div>
  )
}

export default App