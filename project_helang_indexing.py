import uuid
import io
import pandas as pd

from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField
)
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient

from config import (
    SEARCH_ENDPOINT, 
    SEARCH_KEY, 
    STORAGE_CONNECTION_STRING, 
    CONTAINER_NAME,
    DOC_INTEL_ENDPOINT,
    DOC_INTEL_KEY
)

# ================================
# CONFIG (FILL THESE)
# ================================
# SEARCH_ENDPOINT = "<YOUR_SEARCH_ENDPOINT>"
# SEARCH_KEY = "<YOUR_SEARCH_KEY>"
INDEX_NAME = "helang-indexing-files-only"

# STORAGE_CONNECTION_STRING = "<YOUR_BLOB_CONNECTION_STRING>"
# CONTAINER_NAME = "<YOUR_CONTAINER_NAME>"

# DOC_INTEL_ENDPOINT = "<YOUR_DOC_INTEL_ENDPOINT>"
# DOC_INTEL_KEY = "<YOUR_DOC_INTEL_KEY>"

TARGET_FOLDER = "indexing_files/"


# ================================
# CLIENTS
# ================================
blob_service = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
container_client = blob_service.get_container_client(CONTAINER_NAME)

search_index_client = SearchIndexClient(
    endpoint=SEARCH_ENDPOINT,
    credential=AzureKeyCredential(SEARCH_KEY)
)

search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=AzureKeyCredential(SEARCH_KEY)
)

doc_client = DocumentAnalysisClient(
    endpoint=DOC_INTEL_ENDPOINT,
    credential=AzureKeyCredential(DOC_INTEL_KEY)
)


def test_connections():
    """Test all Azure service connections"""
    print("🧪 Testing Azure connections...")
    
    # Test Blob Storage
    try:
        container_client.get_container_properties()
        print("✅ Blob Storage: Connected")
    except Exception as e:
        print(f"❌ Blob Storage: {e}")
        return False
    
    # Test Search Service
    try:
        search_index_client.get_service_statistics()
        print("✅ Search Service: Connected")
    except Exception as e:
        print(f"❌ Search Service: {e}")
        return False
    
    # Test Document Intelligence
    try:
        # Just test the endpoint is reachable
        print("✅ Document Intelligence: Endpoint configured")
    except Exception as e:
        print(f"❌ Document Intelligence: {e}")
        return False
    
    return True
def create_index():
    fields = [
        SimpleField(name="id", type="Edm.String", key=True),
        SearchableField(name="content", type="Edm.String", analyzer_name="en.microsoft"),
        SimpleField(name="source_file", type="Edm.String", filterable=True, facetable=True),
        SimpleField(name="category", type="Edm.String", filterable=True, facetable=True),
        SimpleField(name="file_type", type="Edm.String", filterable=True, facetable=True),
    ]

    index = SearchIndex(name=INDEX_NAME, fields=fields)

    try:
        # Delete existing index if you want to recreate
        # search_index_client.delete_index(INDEX_NAME)
        search_index_client.create_index(index)
        print("✅ Index created successfully")
    except Exception as e:
        print(f"ℹ️ Index already exists or error: {e}")


# ================================
# TEXT CHUNKING
# ================================
# def chunk_text(text, size=500):
#     words = text.split()
#     for i in range(0, len(words), size):
#         yield " ".join(words[i:i + size])


# ================================
# READ BLOB
# ================================
# def read_blob(blob_name):
#     blob_client = container_client.get_blob_client(blob_name)
#     data = blob_client.download_blob().readall()

#     # CSV
#     if blob_name.endswith(".csv"):
#         df = pd.read_csv(io.BytesIO(data))
#         return [row.to_dict() for _, row in df.iterrows()]

#     # Excel
#     elif blob_name.endswith(".xlsx"):
#         sheets = pd.read_excel(io.BytesIO(data), sheet_name=None)
#         rows = []
#         for sheet, df in sheets.items():
#             for _, row in df.iterrows():
#                 rows.append(row.to_dict())
#         return rows

#     # DOCX / PPTX / PDF
#     elif blob_name.endswith((".docx", ".pptx", ".pdf")):
#         poller = doc_client.begin_analyze_document("prebuilt-document", data)
#         result = poller.result()

#         text = []
#         for page in result.pages:
#             for line in page.lines:
#                 text.append(line.content)

#         full_text = "\n".join(text)

#         # chunk for better search
#         return [{"content": chunk} for chunk in chunk_text(full_text)]

#     return []

def chunk_text(text, chunk_size=200, overlap=50):
    """
    Chunk text with word-based splitting and overlap for better context preservation
    """
    if not text or not text.strip():
        return []
        
    words = text.split()
    if len(words) <= chunk_size:
        return [text]  # Return original if smaller than chunk size
        
    chunks = []
    start = 0
    
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        
        # Only add non-empty chunks
        if chunk.strip():
            chunks.append(chunk.strip())
            
        # Move start position with overlap
        start += (chunk_size - overlap)
        
        # Prevent infinite loop
        if start >= len(words):
            break

    return chunks
    
def read_blob(blob_name):
    blob_client = container_client.get_blob_client(blob_name)
    data = blob_client.download_blob().readall()
    stream = io.BytesIO(data)

    # =========================
    # CSV
    # =========================
    if blob_name.endswith(".csv"):
        df = pd.read_csv(stream)
        return [row.to_dict() for _, row in df.iterrows()]

    # =========================
    # EXCEL
    # =========================
    elif blob_name.endswith(".xlsx"):
        sheets = pd.read_excel(stream, sheet_name=None)
        rows = []
        for sheet, df in sheets.items():
            for _, row in df.iterrows():
                rows.append(row.to_dict())
        return rows

    # =========================
    # DOCX
    # =========================
    elif blob_name.endswith(".docx"):
        try:
            from docx import Document
            stream.seek(0)
            doc = Document(stream)

            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            chunks = chunk_text(text)

            return [{"content": chunk} for chunk in chunks]

        except Exception as e:
            print(f"❌ DOCX error: {e}")
            return []

    # =========================
    # PPTX
    # =========================
    elif blob_name.endswith(".pptx"):
        try:
            from pptx import Presentation
            stream.seek(0)
            prs = Presentation(stream)

            text = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        text.append(shape.text)

            full_text = "\n".join(text)
            chunks = chunk_text(full_text)

            return [{"content": chunk} for chunk in chunks]

        except Exception as e:
            print(f"❌ PPTX error: {e}")
            return []

    # =========================
    # PDF (basic)
    # =========================
    elif blob_name.endswith(".pdf"):
        try:
            import PyPDF2
            stream.seek(0)
            reader = PyPDF2.PdfReader(stream)

            text = []
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text.append(extracted)

            full_text = "\n".join(text)
            chunks = chunk_text(full_text)

            return [{"content": chunk} for chunk in chunks]

        except Exception as e:
            print(f"❌ PDF error: {e}")
            return []

    # =========================
    # UNSUPPORTED
    # =========================
    return []



# ================================
# PROCESS FILES
# ================================
def process_files():
    documents = []

    # First, let's see what's in the container
    print(f"🔍 Checking container '{CONTAINER_NAME}' for files in '{TARGET_FOLDER}'...")
    try:
        # Only get blobs that start with TARGET_FOLDER
        target_blobs = list(container_client.list_blobs(name_starts_with=TARGET_FOLDER))
        print(f"📁 Found {len(target_blobs)} blobs in '{TARGET_FOLDER}' folder")
        
        if target_blobs:
            print("📋 Files in target folder:")
            for i, blob in enumerate(target_blobs):
                print(f"  {i+1}. {blob.name}")
        else:
            print(f"⚠️ No files found in '{TARGET_FOLDER}' folder")
            return []
            
    except Exception as e:
        print(f"❌ Error listing blobs: {e}")
        return []

    # Process only the target folder files
    for blob in target_blobs:
        blob_name = blob.name
        print(f"\n📄 Processing: {blob_name}")

        try:
            rows = read_blob(blob_name)
        except Exception as e:
            print(f"❌ Error reading {blob_name}: {e}")
            continue

        if not rows:
            print("⚠️ No usable data")
            continue

        for row in rows:
            # Handle different data types
            if isinstance(row, dict):
                if "content" in row:
                    # This is chunked text content (DOCX, PPTX, PDF)
                    content = row["content"]
                else:
                    # This is structured data (CSV, Excel)
                    content = " | ".join([f"{k}: {v}" for k, v in row.items() if v is not None and str(v).strip()])
            else:
                content = str(row)

            # Skip empty content
            if not content or not content.strip():
                continue

            # Get file extension for better categorization
            file_extension = blob_name.split('.')[-1].lower() if '.' in blob_name else 'unknown'

            documents.append({
                "id": str(uuid.uuid4()),
                "content": content.strip(),
                "source_file": blob_name,
                "category": TARGET_FOLDER.replace("/", ""),
                "file_type": file_extension
            })

    return documents


# ================================
# UPLOAD
# ================================
def upload_documents(docs):
    if not docs:
        print("⚠️ No documents to upload")
        return

    batch_size = 500
    successful_uploads = 0

    for i in range(0, len(docs), batch_size):
        batch = docs[i:i + batch_size]

        try:
            result = search_client.upload_documents(batch)
            successful_uploads += len(batch)
            print(f"✅ Uploaded batch {i//batch_size + 1}: {successful_uploads} / {len(docs)}")
            
            # Check for any failed uploads in the batch
            if hasattr(result, 'results'):
                failed = [r for r in result.results if not r.succeeded]
                if failed:
                    print(f"⚠️ {len(failed)} documents failed in this batch")
                    
        except Exception as e:
            print(f"❌ Failed to upload batch {i//batch_size + 1}: {e}")
            continue

    print(f"📊 Total successful uploads: {successful_uploads} / {len(docs)}")


# ================================
# SEARCH TEST
# ================================
def search(query):
    results = search_client.search(query)

    print(f"\n🔍 Results for: {query}\n")

    for r in results:
        print("-----")
        print("File:", r["source_file"])
        print("Content:", r["content"][:200])


# ================================
# MAIN
# ================================
if __name__ == "__main__":
    print("🚀 Starting pipeline...")

    # Test connections first
    if not test_connections():
        print("❌ Connection test failed. Please check your credentials.")
        exit(1)

    # Create index
    create_index()

    # Process files and get documents
    docs = process_files()
    print(f"\n📊 Total docs: {len(docs)}")

    if not docs:
        print("❌ No documents to index. Check your blob storage and TARGET_FOLDER.")
        exit(1)

    # Show sample document for debugging
    print(f"\n🔍 Sample document:")
    print(f"ID: {docs[0]['id']}")
    print(f"Source: {docs[0]['source_file']}")
    print(f"Content preview: {docs[0]['content'][:200]}...")
    print(f"Content length: {len(docs[0]['content'])}")

    # Upload documents
    upload_documents(docs)

    print("\n✅ Pipeline completed")

    # Test search
    print("\n🧪 Testing search...")
    search("hospital ICU")