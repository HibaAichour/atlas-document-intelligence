import './App.css'

import { useCallback, useState } from 'react'

import type { SessionDetail } from './api/types'
import { ChatPanel } from './components/ChatPanel'
import { DocumentsPanel } from './components/DocumentsPanel'
import { HealthStatus } from './components/HealthStatus'
import { SessionsPanel } from './components/SessionsPanel'
import { SourcePanel } from './components/SourcePanel'
import { useChat } from './hooks/useChat'
import { useDocuments } from './hooks/useDocuments'
import { useSessions } from './hooks/useSessions'
import { restoreMessages } from './lib/chat'
import type { OpenSource } from './lib/citations'
import { useMessages } from './lib/i18n'
import { restoredSelection } from './lib/selection'

function App() {
  const t = useMessages()
  // The citation whose passage is shown in the side panel, if any.
  const [openSource, setOpenSource] = useState<OpenSource | null>(null)
  const closeSource = useCallback(() => setOpenSource(null), [])
  const documents = useDocuments()
  const sessions = useSessions(showSession)
  const chat = useChat({
    selectedIds: documents.selectedIds,
    ensureSession: sessions.ensureSession,
    onSaved: sessions.saved,
  })

  /** Show an opened session (its messages and documents), or a new empty one. */
  function showSession(session: SessionDetail | null): void {
    // The open citation belonged to the previous conversation.
    setOpenSource(null)
    chat.load(session === null ? [] : restoreMessages(session.messages, session.id))
    documents.select(session === null ? 'all' : restoredSelection(session.document_ids))
  }

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
        <div className="sidebar">
          <SessionsPanel
            sessions={sessions.sessions}
            listState={sessions.listState}
            listError={sessions.listError}
            currentId={sessions.currentId}
            disabled={chat.isWaiting || sessions.isOpening}
            openError={sessions.openError}
            onOpen={(sessionId) => void sessions.open(sessionId)}
            onNew={sessions.startNew}
          />

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
        </div>

        <ChatPanel
          messages={chat.messages}
          isWaiting={chat.isWaiting}
          // No question while a saved session is still being restored: it
          // would start a new session instead of continuing that one.
          canAsk={documents.selectedIds.size > 0 && !sessions.isOpening}
          onAsk={(question) => void chat.ask(question)}
          documents={documents.documents}
          selectedIds={documents.selectedIds}
          canExtract={!sessions.isOpening}
          onExtract={(document) => void chat.extract(document)}
          openSource={openSource}
          onOpenSource={setOpenSource}
        />

        {openSource && <SourcePanel source={openSource} onClose={closeSource} />}
      </div>
    </div>
  )
}

export default App