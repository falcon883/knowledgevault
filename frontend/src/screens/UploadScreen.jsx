import { useRef, useState } from 'react';
import { uploadDocument } from '../api.js';

/**
 * KV-19 — Capture / upload screen.
 *
 * Wires the Sprint 1 capture wireframe to the real POST /upload endpoint.
 * The backend accepts application/pdf and text/plain only, so notes and
 * article text are uploaded as .txt files; the title field becomes the
 * filename since the API has no separate title field.
 */

const KINDS = ['PDF', 'Note', 'Article'];

function sanitizeFilename(title, extension) {
  const base = (title || '').trim().replace(/[\\/:*?"<>|]/g, '').slice(0, 80) || 'untitled';
  return `${base}.${extension}`;
}

export default function UploadScreen() {
  const [kind, setKind] = useState('PDF');
  const [title, setTitle] = useState('');
  const [file, setFile] = useState(null);
  const [text, setText] = useState('');
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState('idle'); // idle | uploading | ready | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  const isPdfKind = kind === 'PDF';
  const canSave =
    status !== 'uploading' &&
    (isPdfKind ? !!file : text.trim().length > 0);

  function pickFile(chosen) {
    if (!chosen) return;
    const looksPdf =
      chosen.type === 'application/pdf' || chosen.name.toLowerCase().endsWith('.pdf');
    if (!looksPdf) {
      setError('Please choose a PDF file.');
      setFile(null);
      return;
    }
    setError('');
    setFile(chosen);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files?.[0]);
  }

  async function handleSave() {
    setError('');
    setResult(null);
    let uploadFile;
    try {
      if (isPdfKind) {
        const filename = title.trim()
          ? sanitizeFilename(title, 'pdf')
          : file.name;
        uploadFile = new File([file], filename, { type: 'application/pdf' });
      } else {
        uploadFile = new File([text.trim()], sanitizeFilename(title, 'txt'), {
          type: 'text/plain',
        });
      }
    } catch {
      setStatus('error');
      setError('Could not prepare the file for upload.');
      return;
    }

    setStatus('uploading');
    try {
      const saved = await uploadDocument(uploadFile);
      setResult(saved);
      setStatus('ready');
    } catch (err) {
      setStatus('error');
      setError(err.message || 'Upload failed.');
    }
  }

  function reset() {
    setStatus('idle');
    setResult(null);
    setError('');
    setFile(null);
    setText('');
    setTitle('');
  }

  const tags = (result?.tags || '')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);

  return (
    <section className="kv-card" aria-labelledby="capture-heading">
      <h2 id="capture-heading">Add to your vault</h2>
      <p className="kv-lede">
        Save a PDF, a note, or article text. It will be extracted, indexed for
        semantic search, and automatically tagged with a summary.
      </p>

      <div className="kv-kind-toggle" role="group" aria-label="Document kind">
        {KINDS.map((k) => (
          <button
            key={k}
            type="button"
            className="kv-kind-btn"
            aria-pressed={kind === k}
            onClick={() => {
              setKind(k);
              setError('');
            }}
          >
            {k}
          </button>
        ))}
      </div>

      <label className="kv-label" htmlFor="kv-title">
        Title
      </label>
      <input
        id="kv-title"
        className="kv-input"
        type="text"
        placeholder="Document title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />

      {isPdfKind ? (
        <div
          className={`kv-drop${dragging ? ' dragging' : ''}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Choose a PDF file to upload"
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click();
          }}
        >
          <p>{file ? file.name : 'Drop a PDF here, or click to choose one'}</p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            aria-label="Choose PDF"
            onChange={(e) => pickFile(e.target.files?.[0])}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      ) : (
        <>
          <label className="kv-label" htmlFor="kv-text">
            {kind === 'Note' ? 'Note' : 'Article text'}
          </label>
          <textarea
            id="kv-text"
            className="kv-textarea"
            placeholder="Paste or write your text here"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </>
      )}

      <p className="kv-meta">Tags and a summary appear after processing.</p>

      <button
        type="button"
        className="kv-btn"
        disabled={!canSave}
        onClick={handleSave}
      >
        {status === 'uploading' ? (
          <>
            <span className="kv-spinner" aria-hidden="true" />
            Uploading…
          </>
        ) : (
          'Save to vault'
        )}
      </button>

      <div className="kv-status" aria-live="polite">
        {status === 'uploading' && (
          <div className="kv-status info">
            <span className="kv-spinner" aria-hidden="true" />
            Uploading → processing your document…
          </div>
        )}
        {status === 'ready' && result && (
          <div className="kv-status ok">
            <strong>Saved.</strong> “{result.filename}” is indexed
            {result.chunk_count != null && ` (${result.chunk_count} chunks)`}.
            {tags.length > 0 && (
              <div style={{ marginTop: '0.5rem' }}>
                {tags.map((t) => (
                  <span key={t} className="kv-chip">
                    {t}
                  </span>
                ))}
              </div>
            )}
            {result.summary && (
              <p style={{ margin: '0.5rem 0 0' }}>{result.summary}</p>
            )}
            <div style={{ marginTop: '0.75rem' }}>
              <button
                type="button"
                className="kv-btn kv-btn-secondary"
                style={{ marginTop: 0 }}
                onClick={reset}
              >
                Add another
              </button>
            </div>
          </div>
        )}
        {status === 'error' && (
          <div className="kv-status error">
            <strong>Upload failed.</strong> {error || 'Please try again.'}
            <div style={{ marginTop: '0.75rem' }}>
              <button
                type="button"
                className="kv-btn kv-btn-secondary"
                style={{ marginTop: 0 }}
                onClick={handleSave}
                disabled={!canSave}
              >
                Retry
              </button>
            </div>
          </div>
        )}
      </div>

      <p className="kv-meta">
        Processing states: Uploading → Processing → Ready · Failed with retry
      </p>
    </section>
  );
}
