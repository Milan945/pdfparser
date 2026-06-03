import React, { useRef } from 'react'

interface Props {
  initialMarkup: string
  filename: string
}

export function EditorPanel({ initialMarkup, filename }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function handleDownload() {
    const text = textareaRef.current?.value ?? initialMarkup
    const blob = new Blob([text], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `edited_${filename}`
    a.click()
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Editor</span>
        <button className="download-btn" onClick={handleDownload}>
          Download
        </button>
      </div>
      <div className="panel-body editor-body">
        <textarea
          ref={textareaRef}
          className="editor-textarea"
          defaultValue={initialMarkup}
          spellCheck={false}
        />
      </div>
    </div>
  )
}
