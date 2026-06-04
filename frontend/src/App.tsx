import { useState } from 'react'
import './App.css'
import { UploadZone } from './components/UploadZone'
import { PdfPanel } from './components/PdfPanel'
import { RawMarkupPanel } from './components/RawMarkupPanel'
import { MarkupPanel } from './components/MarkupPanel'

type AppState = 'idle' | 'uploading' | 'ready' | 'needs-state' | 'error'

interface ConversionResult {
  sessionId: string
  state: string
  markup: string
  filename: string
}

const SUPPORTED_STATES = ['CA', 'KS']

export default function App() {
  const [appState, setAppState] = useState<AppState>('idle')
  const [result, setResult] = useState<ConversionResult | null>(null)
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [selectedState, setSelectedState] = useState('CA')
  const [errorMsg, setErrorMsg] = useState('')
  const [scrollRatio, setScrollRatio] = useState(0)

  async function runUpload(file: File, state?: string) {
    setAppState('uploading')
    const form = new FormData()
    form.append('file', file)
    if (state) form.append('state', state)

    try {
      const res = await fetch('/upload', { method: 'POST', body: form })
      const body = await res.json()

      if (!res.ok) {
        setErrorMsg(body.detail ?? 'Upload failed.')
        setAppState('error')
        return
      }

      if (body.state === null) {
        setPendingFile(file)
        setAppState('needs-state')
        return
      }

      setResult({
        sessionId: body.session_id,
        state: body.state,
        markup: body.markup,
        filename: body.filename,
      })
      setAppState('ready')
    } catch {
      setErrorMsg('Network error — is the API server running?')
      setAppState('error')
    }
  }

  function handleFile(file: File) {
    runUpload(file)
  }

  function handleConvertWithState() {
    if (pendingFile) runUpload(pendingFile, selectedState)
  }

  function handleReset() {
    if (result) {
      fetch(`/session/${result.sessionId}`, { method: 'DELETE' })
    }
    setResult(null)
    setPendingFile(null)
    setAppState('idle')
    setErrorMsg('')
    setScrollRatio(0)
  }

  if (appState === 'idle') {
    return (
      <div className="center-page">
        <h1>NetScan Bill Converter</h1>
        <UploadZone onFile={handleFile} />
      </div>
    )
  }

  if (appState === 'uploading') {
    return (
      <div className="center-page">
        <p className="spinner-text">Analyzing bill…</p>
      </div>
    )
  }

  if (appState === 'needs-state') {
    return (
      <div className="center-page">
        <p>Could not auto-detect state. Please select one:</p>
        <select value={selectedState} onChange={e => setSelectedState(e.target.value)}>
          {SUPPORTED_STATES.map(s => <option key={s}>{s}</option>)}
        </select>
        <button className="primary-btn" onClick={handleConvertWithState}>
          Convert
        </button>
      </div>
    )
  }

  if (appState === 'error') {
    return (
      <div className="center-page">
        <p className="error-msg">{errorMsg}</p>
        <UploadZone onFile={handleFile} />
      </div>
    )
  }

  const rawName = result!.filename.replace(/\.[^.]+$/, '') + '.markup.txt'
  return (
    <div className="app-ready">
      <div className="top-bar">
        <span className="brand">NetScan Bill Converter</span>
        <span className="state-badge">{result!.state} — auto-detected</span>
        <button className="reset-btn" onClick={handleReset}>Upload new bill</button>
      </div>
      <div className="panels">
        <PdfPanel sessionId={result!.sessionId} ratio={scrollRatio} onRatio={setScrollRatio} />
        <RawMarkupPanel
          markup={result!.markup}
          filename={rawName}
          ratio={scrollRatio}
          onRatio={setScrollRatio}
        />
        <MarkupPanel
          markup={result!.markup}
          filename={result!.filename}
          ratio={scrollRatio}
          onRatio={setScrollRatio}
        />
      </div>
    </div>
  )
}
