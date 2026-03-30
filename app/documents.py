import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.documents import Document

from app.rag import BASE_DIR, DOCS_DIR, SUPPORTED_EXTENSIONS, build_vector_store, get_vector_store, split_documents

REGISTRY_PATH = BASE_DIR / "data" / "document_registry.json"


def compute_md5(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


def normalize_filename(filename: str | None) -> str:
    original_name = filename or "document.txt"
    path = Path(original_name)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only .txt and .md files are supported.")

    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", path.stem).strip()
    if not sanitized:
        sanitized = "document"

    return f"{sanitized}{suffix}"


def read_registry() -> list[dict]:
    if not REGISTRY_PATH.exists():
        return []

    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("Document registry is invalid JSON.") from error

    if not isinstance(data, list):
        raise ValueError("Document registry must be a JSON list.")

    return [item for item in data if isinstance(item, dict)]


def write_registry(records: list[dict]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def sort_records(records: list[dict]) -> list[dict]:
    uploaded = [record for record in records if record.get("uploaded_at")]
    uploaded.sort(key=lambda item: item["uploaded_at"], reverse=True)

    seed_docs = [record for record in records if not record.get("uploaded_at")]
    seed_docs.sort(key=lambda item: item["source"])
    return uploaded + seed_docs


def compute_chunk_count(text: str, source: str) -> int:
    document = Document(page_content=text, metadata={"source": source})
    return len(split_documents([document]))


def refresh_document_registry() -> list[dict]:
    existing_records = {record.get("source"): record for record in read_registry() if record.get("source")}
    records: list[dict] = []

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(DOCS_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        source = path.relative_to(BASE_DIR).as_posix()
        content = path.read_bytes()
        text = content.decode("utf-8")
        previous = existing_records.get(source, {})
        chunk_count = previous.get("chunk_count")
        if chunk_count is None:
            chunk_count = compute_chunk_count(text, source)

        records.append(
            {
                "file_name": path.name,
                "source": source,
                "md5": compute_md5(content),
                "uploaded_at": previous.get("uploaded_at"),
                "chunk_count": chunk_count,
            }
        )

    records = sort_records(records)
    write_registry(records)
    return records


def build_document_record(path: Path, content: bytes, uploaded_at: str | None, chunk_count: int | None) -> dict:
    return {
        "file_name": path.name,
        "source": path.relative_to(BASE_DIR).as_posix(),
        "md5": compute_md5(content),
        "uploaded_at": uploaded_at,
        "chunk_count": chunk_count,
    }


def make_unique_path(filename: str) -> Path:
    candidate = DOCS_DIR / filename
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2

    while candidate.exists():
        candidate = DOCS_DIR / f"{stem}-{index}{suffix}"
        index += 1

    return candidate


def get_document_path(source: str) -> Path:
    path = (BASE_DIR / source).resolve()
    docs_root = DOCS_DIR.resolve()
    try:
        path.relative_to(docs_root)
    except ValueError as error:
        raise ValueError("Document source is invalid.") from error
    return path


def list_documents() -> list[dict]:
    return refresh_document_registry()


def store_uploaded_document(filename: str | None, content: bytes) -> tuple[str, dict]:
    if not content:
        raise ValueError("Uploaded file is empty.")

    safe_name = normalize_filename(filename)
    text = content.decode("utf-8")
    if not text.strip():
        raise ValueError("Uploaded file is empty.")

    records = refresh_document_registry()
    md5 = compute_md5(content)
    duplicate = next((record for record in records if record.get("md5") == md5), None)
    if duplicate is not None:
        return "duplicate", duplicate

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = make_unique_path(safe_name)
    target_path.write_text(text, encoding="utf-8")

    try:
        source = target_path.relative_to(BASE_DIR).as_posix()
        document = Document(page_content=text, metadata={"source": source})
        chunks = split_documents([document])
        build_vector_store(chunks)
    except Exception:
        if target_path.exists():
            target_path.unlink()
        raise

    uploaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    new_record = build_document_record(target_path, content, uploaded_at=uploaded_at, chunk_count=len(chunks))

    merged_records = [record for record in records if record.get("source") != new_record["source"]]
    merged_records.append(new_record)
    merged_records = sort_records(merged_records)
    write_registry(merged_records)
    return "indexed", new_record


def delete_document(source: str) -> dict:
    source = source.strip()
    if not source:
        raise ValueError("Document source is required.")

    records = refresh_document_registry()
    target = next((record for record in records if record.get("source") == source), None)
    if target is None:
        raise ValueError("Document not found.")

    target_path = get_document_path(source)
    vector_store = get_vector_store()
    matches = vector_store.get(where={"source": source})
    ids = matches.get("ids") or []
    if ids:
        vector_store.delete(ids=ids)

    if target_path.exists():
        target_path.unlink()

    remaining_records = [record for record in records if record.get("source") != source]
    write_registry(sort_records(remaining_records))
    return target
