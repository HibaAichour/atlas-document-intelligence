import './App.css'

import { DocumentsPanel } from './components/DocumentsPanel'
import { HealthStatus } from './components/HealthStatus'
import { useDocuments } from './hooks/useDocuments'
import { useMessages } from './lib/i18n'

function App() {
  const t = useMessages()
  const documents = useDocuments()

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

        <main className="conversation glass">
          <div className="conversation-intro">
            <h1>{t.introTitle}</h1>
            <p>{t.introText}</p>
          </div>
        </main>
      </div>
    </div>
  )
}

export default App