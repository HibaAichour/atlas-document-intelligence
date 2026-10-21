import './App.css'

import { useCallback, useState } from 'react'

import { ChatPanel } from './components/ChatPanel'
import { DocumentsPanel } from './components/DocumentsPanel'
import { HealthStatus } from './components/HealthStatus'
import { SourcePanel } from './components/SourcePanel'
import { useChat } from './hooks/useChat'
import { useDocuments } from './hooks/useDocuments'
import type { OpenSource } from './lib/citations'
import { useMessages } from './lib/i18n'

function App() {
  const t = useMessages()
  const documents = useDocuments()
  const chat = useChat(documents.selectedIds)
  // The citation whose passage is shown in the side panel, if any.
  const [openSource, setOpenSource] = useState<OpenSource | null>(null)
  const closeSource = useCallback(() => setOpenSource(null), [])

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

      <div className={openSource ? 'workspace workspace-with-source' : 'workspace'}>
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
          openSource={openSource}
          onOpenSource={setOpenSource}
        />

        {openSource && <SourcePanel source={openSource} onClose={closeSource} />}
      </div>
    </div>
  )
}

export default App