import base64
import binascii
import io
from pathlib import PurePath

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_DOCUMENT_BYTES = 2_000_000
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


class DocumentParseError(ValueError):
    pass


def extract_document_text(name: str, content_base64: str) -> str:
    extension = PurePath(name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentParseError("Upload a .txt, .md, or text-based .pdf document.")
    try:
        content = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise DocumentParseError("Uploaded document data is not valid base64.") from exc
    if not content or len(content) > MAX_DOCUMENT_BYTES:
        raise DocumentParseError("Documents must be between 1 byte and 2 MB.")

    if extension in {".txt", ".md"}:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentParseError(
                "Text and Markdown documents must use UTF-8 encoding."
            ) from exc
    else:
        try:
            reader = PdfReader(io.BytesIO(content), strict=True)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except (PdfReadError, OSError, ValueError) as exc:
            raise DocumentParseError("The PDF could not be parsed as a text document.") from exc

    text = text.strip()
    if not text:
        raise DocumentParseError("No text could be extracted. Scanned PDFs need OCR before upload.")
    if len(text) > 250_000:
        raise DocumentParseError("Extracted document text must be 250,000 characters or less.")
    return text
