# KnowledgeVault Backend

## KV-6: Upload endpoint and text extraction

Builds on the KV-5 scaffold. Adds `POST /upload`, which accepts a PDF or
plain-text file and returns its extracted text. Nothing is persisted yet
(see KV-7 for the data model).

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Runs at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Test it

```bash
curl http://localhost:8000/health

curl -F "file=@/path/to/some.pdf;type=application/pdf" http://localhost:8000/upload
curl -F "file=@/path/to/some.txt;type=text/plain" http://localhost:8000/upload
```

Expected response shape:
```json
{
  "filename": "some.pdf",
  "content_type": "application/pdf",
  "size_bytes": 1426,
  "extracted_text": "...",
  "extracted_length": 69,
  "status": "extracted (not yet persisted - see KV-7)"
}
```

Supported file types: `application/pdf`, `text/plain`. Anything else
returns a 400 with a clear error message.

## Next steps

- KV-7: define the data model and start persisting uploaded documents
