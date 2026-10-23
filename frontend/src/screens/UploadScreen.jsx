import { useRef, useState } from 'react';
import { uploadDocument } from '../api.js';

/**
 * KV-19 — Capture / upload screen.
 * KV-29 — Polish: client-side validation with visible messages, a file
 * size check that states the limit, per-case readable messages for the
 * backend errors from KV-24/KV-25, a Browse link on success, titles
 * derived from the first line for notes/articles, and .txt file picking.
 *
 * The backend accepts application/pdf and text/plain only, so notes and
 * article text are uploaded as .txt files; the title field becomes the
 * filename since the API has no separate title field.
 */

const KINDS = ['PDF', 'Note', 'Article'];

// From the KV-24 upload validation story: files over the maximum size
// are rejected with HTTP 413 and the limit stated in the message.
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const MAX_FILE_LABEL = '10 MB';
const TITLE_MAX = 80; // sanitizeFilename cap, in characters

function sanitizeFilename(title, extension) {
  const base = (title || '').trim().replace(/[\\/:*?"<>|]/g, '').slice(0, TITLE_MAX) || 'untitled';
  return `${base}.${extension}`;
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 bytes';
  if (bytes < 1024) return `${bytes} bytes`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function firstLineOf(text) {
  return (text || '')
    .split('\n')
    .map((line) => line.trim())
    .find(Boolean) || '';
}

function validatePdfFile(chosen) {
  const looksPdf =
    chosen.type === 'application/pdf' || chosen.name.toLowerCase().endsWith('.pdf');
  if (!looksPdf) {
    return 'That file is not a PDF. Choose a PDF file, or switch to Note or Article to save text instead.';
  }
  if (chosen.size === 0) {
    return 'That file is empty (0 bytes), so there is nothing to save.';
  }
  if (chosen.size > MAX_FILE_BYTES) {
    return `That file is ${formatBytes(chosen.size)}. Uploads are limited to ${MAX_FILE_LABEL}.`;
  }
  return '';
}

/**
 * Map an upload failure to a readable message for its specific case
 * (KV-29 acceptance: empty, unreadable, no text, too large, duplicate,
 * server unreachable). The backend (KV-24) returns a specific `detail`
 * per case and KV-25 returns 409 with the existing document's id and
 * filename, so prefer those signals and fall back to the detail text.
 */
function describeUploadError(err) {
  const detail = err?.detail;
  const detailText =
    typeof detail === 'string'
      ? detail
      : detail && typeof detail === 'object'
        ? detail.message || ''
        : '';
  const text = detailText.toLowerCase();

  // fetch itself rejected: the backend is down or unreachable.
  if (err && err.status == null) {
    return {
      tone: 'error',
      heading: 'Can’t reach the server.',
      message:
        'The KnowledgeVault backend is not responding. Make sure it is running, then try again.',
      retry: true,
    };
  }

  if (err.status === 409 || text.includes('duplicate') || text.includes('already')) {
    const quoted = detailText.match(/["“]([^"”]+)["”]/)?.[1];
    const existingName =
      (detail && typeof detail === 'object' && detail.filename) || quoted || '';
    return {
      tone: 'duplicate',
      heading: 'Already in your vault.',
      message: existingName
        ? `This content is already saved as “${existingName}”. Nothing was added.`
        : 'This content is already saved in your vault. Nothing was added.',
      retry: false,
      browse: true,
    };
  }

  if (err.status === 413 || text.includes('too large')) {
    return {
      tone: 'error',
      heading: 'That file is too large.',
      message: `Uploads are limited to ${MAX_FILE_LABEL}. Try a smaller file.`,
      retry: false,
    };
  }

  if (text.includes('no extractable text') || text.includes('no text')) {
    return {
      tone: 'error',
      heading: 'No readable text found.',
      message:
        'We could not find any text to index in that file. A scanned PDF without a text layer will do this — try an OCR copy, or paste the text as an Article instead.',
      retry: false,
    };
  }

  if (text.includes('empty')) {
    return {
      tone: 'error',
      heading: 'That file is empty.',
      message: 'There is no content to save. Choose a file with content and try again.',
      retry: false,
    };
  }

  if (
    text.includes('unreadable') ||
    text.includes('could not read') ||
    text.includes('couldn’t read') ||
    text.includes('cannot read') ||
    text.includes('invalid pdf') ||
    text.includes('password')
  ) {
    return {
      tone: 'error',
      heading: 'That file could not be read.',
      message:
        'The file may be damaged or password-protected. Try a different copy of it.',
      retry: false,
    };
  }

  if (
    text.includes('unsupported') ||
    text.includes('content type') ||
    text.includes('file type') ||
    text.includes('only pdf')
  ) {
    return {
      tone: 'error',
      heading: 'That file type is not supported.',
      message: 'Upload a PDF, or save the text as a Note or Article instead.',
      retry: false,
    };
  }

  return {
    tone: 'error',
    heading: 'Upload failed.',
    message: detailText || err?.message || 'Please try again.',
    retry: true,
  };
}

export default function UploadScreen({ onNavigate } = {}) {
  const [kind, setKind] = useState('PDF');
  const [title, setTitle] = useState('');
  const [file, setFile] = useState(null);
  const [text, setText] = useState('');
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState('idle'); // idle | uploading | ready | error
  const [result, setResult] = useState(null);
  const [failure, setFailure] = useState(null);
  const [fileError, setFileError] = useState('');
  const [textError, setTextError] = useState('');
  const fileInputRef = useRef(null);
  const textInputRef = useRef(null);

  const isPdfKind = kind === 'PDF';
  const canSave =
    status !== 'uploading' &&
    (isPdfKind ? !!file : text.trim().length > 0);
  const derivedName =
    !isPdfKind && !title.trim() && text.trim()
      ? sanitizeFilename(firstLineOf(text), 'txt')
      : null;

  function pickFile(chosen) {
    if (!chosen) return;
    const problem = validatePdfFile(chosen);
    if (problem) {
      setFileError(problem);
      setFile(null);
      return;
    }
    setFileError('');
    setFile(chosen);
  }

  async function pickTextFile(chosen) {
    if (!chosen) return;
    const looksText =
      chosen.type === 'text/plain' || chosen.name.toLowerCase().endsWith('.txt');
    if (!looksText) {
      setTextError('That file is not a plain text file. Choose a .txt file.');
      return;
    }
    if (chosen.size === 0) {
      setTextError('That file is empty (0 bytes), so there is nothing to load.');
      return;
    }
    if (chosen.size > MAX_FILE_BYTES) {
      setTextError(
        `That file is ${formatBytes(chosen.size)}. Uploads are limited to ${MAX_FILE_LABEL}.`,
      );
      return;
    }
    try {
      const content = await chosen.text();
      setText(content);
      setTextError('');
      if (!title.trim()) {
        setTitle(chosen.name.replace(/\.txt$/i, ''));
      }
    } catch {
      setTextError('That file could not be read.');
    }
  }

  function clearFile() {
    setFile(null);
    setFileError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files?.[0]);
  }

  async function handleSave() {
    setFailure(null);
    setResult(null);

    // Re-check before upload so nothing invalid reaches the backend.
    if (isPdfKind) {
      const problem = file ? validatePdfFile(file) : 'Choose a PDF file first.';
      if (problem) {
        setFileError(problem);
        return;
      }
    } else if (!text.trim()) {
      setTextError('Write or paste some text first, or choose a .txt file.');
      return;
    }

    let uploadFile;
    try {
      if (isPdfKind) {
        const filename = title.trim()
          ? sanitizeFilename(title, 'pdf')
          : file.name;
        uploadFile = new File([file], filename, { type: 'application/pdf' });
      } else {
        const nameSource = title.trim() || firstLineOf(text);
        uploadFile = new File([text.trim()], sanitizeFilename(nameSource, 'txt'), {
          type: 'text/plain',
        });
      }
    } catch {
      setStatus('error');
      setFailure({
        tone: 'error',
        heading: 'Upload failed.',
        message: 'Could not prepare the file for upload.',
        retry: false,
      });
      return;
    }

    setStatus('uploading');
    try {
      const saved = await uploadDocument(uploadFile);
      setResult(saved);
      setStatus('ready');
    } catch (err) {
      setFailure(describeUploadError(err));
      setStatus('error');
    }
  }

  function reset() {
    setStatus('idle');
    setResult(null);
    setFailure(null);
    setFileError('');
    setTextError('');
    setFile(null);
    setText('');
    setTitle('');
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (textInputRef.current) textInputRef.current.value = '';
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
              setFileError('');
              setTextError('');
              setFailure(null);
              if (status === 'error') setStatus('idle');
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
        aria-describedby="kv-title-hint"
      />
      <p className="kv-meta" id="kv-title-hint">
        {isPdfKind
          ? 'Optional — used as the saved filename. Leave blank to keep the file’s own name.'
          : 'Optional — if blank, the first line of your text becomes the title.'}
        {title.length > 0 && ` ${title.length}/${TITLE_MAX}`}
      </p>

      {isPdfKind ? (
        <>
          <div
            className={`kv-drop${dragging ? ' dragging' : ''}${fileError ? ' invalid' : ''}`}
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
            aria-invalid={!!fileError}
            aria-describedby={fileError ? 'kv-file-error' : undefined}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click();
            }}
          >
            <p>{file ? file.name : 'Drop a PDF here, or click to choose one'}</p>
            <p className="kv-meta">PDF files only, up to {MAX_FILE_LABEL}.</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              aria-label="Choose PDF"
              onChange={(e) => {
                pickFile(e.target.files?.[0]);
                e.target.value = '';
              }}
              onClick={(e) => e.stopPropagation()}
            />
          </div>
          {fileError && (
            <p className="kv-field-error" id="kv-file-error" role="alert">
              {fileError}
            </p>
          )}
          {file && !fileError && (
            <div className="kv-filebar">
              <span className="kv-filebar-name">{file.name}</span>
              <span className="kv-meta">{formatBytes(file.size)}</span>
              <button
                type="button"
                className="kv-btn kv-btn-secondary kv-btn-small"
                onClick={clearFile}
              >
                Remove
              </button>
            </div>
          )}
        </>
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
            onChange={(e) => {
              setText(e.target.value);
              if (e.target.value.trim()) setTextError('');
            }}
            aria-invalid={!!textError}
            aria-describedby={textError ? 'kv-text-error' : undefined}
          />
          <div className="kv-text-tools">
            <button
              type="button"
              className="kv-btn kv-btn-secondary kv-btn-small"
              onClick={() => textInputRef.current?.click()}
            >
              Choose a .txt file
            </button>
            <input
              ref={textInputRef}
              type="file"
              hidden
              accept=".txt,text/plain"
              aria-label="Choose a plain text file"
              onChange={(e) => {
                pickTextFile(e.target.files?.[0]);
                e.target.value = '';
              }}
            />
            <span className="kv-meta">
              {text.length} character{text.length === 1 ? '' : 's'}
              {derivedName && ` · will be saved as “${derivedName}”`}
            </span>
          </div>
          {textError && (
            <p className="kv-field-error" id="kv-text-error" role="alert">
              {textError}
            </p>
          )}
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
            <div className="kv-row" style={{ marginTop: '0.75rem' }}>
              {onNavigate && (
                <button
                  type="button"
                  className="kv-btn"
                  style={{ marginTop: 0 }}
                  onClick={() => onNavigate('browse')}
                >
                  View in Browse
                </button>
              )}
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
        {status === 'error' && failure && (
          <div className={`kv-status ${failure.tone === 'duplicate' ? 'duplicate' : 'error'}`}>
            <strong>{failure.heading}</strong> {failure.message}
            <div className="kv-row" style={{ marginTop: '0.75rem' }}>
              {failure.retry && (
                <button
                  type="button"
                  className="kv-btn kv-btn-secondary"
                  style={{ marginTop: 0 }}
                  onClick={handleSave}
                  disabled={!canSave}
                >
                  Retry
                </button>
              )}
              {failure.browse && onNavigate && (
                <button
                  type="button"
                  className="kv-btn kv-btn-secondary"
                  style={{ marginTop: 0 }}
                  onClick={() => onNavigate('browse')}
                >
                  View in Browse
                </button>
              )}
              {failure.tone === 'duplicate' && (
                <button
                  type="button"
                  className="kv-btn kv-btn-secondary"
                  style={{ marginTop: 0 }}
                  onClick={reset}
                >
                  Add something else
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
