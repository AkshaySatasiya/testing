import os
import uuid
import pandas as pd
from PyPDF2 import PdfReader
from docx import Document

from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, SearchField,
    SearchFieldDataType, VectorSearch, VectorSearchProfile,
    HnswAlgorithmConfiguration
)

from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential

from config import (
    SEARCH_ENDPOINT, 
    SEARCH_KEY, 
    STORAGE_CONNECTION_STRING, 
    CONTAINER_NAME,
    DOC_INTEL_ENDPOINT,
    DOC_INTEL_KEY
)

# ================= CONFIG =================
LOCAL_FOLDER = r"D:\PROJECTS\PWC\PMO\data\Unstructured_extracted_data\Project_State_Catalyst"

SEARCH_ENDPOINT = SEARCH_ENDPOINT
SEARCH_KEY = SEARCH_KEY
INDEX_NAME = "project-state-catalyst"

OPENAI_ENDPOINT = ""
OPENAI_KEY = ""
EMBEDDING_MODEL = "text-embedding-3-small"
# ==========================================

# Clients
search_index_client = SearchIndexClient(
    endpoint=SEARCH_ENDPOINT,
    credential=AzureKeyCredential(SEARCH_KEY)
)

search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=AzureKeyCredential(SEARCH_KEY)
)

openai_client = AzureOpenAI(
    api_key=OPENAI_KEY,
    api_version="2024-02-01",
    azure_endpoint=OPENAI_ENDPOINT
)

# ==========================================
# 1. CREATE INDEX (VECTOR ENABLED)
# ==========================================
def create_index():
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="vector-profile"
        ),
        SimpleField(name="fileName", type=SearchFieldDataType.String)
    ]

    vector_search = VectorSearch(
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm_configuration_name="hnsw-config"
            )
        ],
        algorithms=[
            HnswAlgorithmConfiguration(name="hnsw-config")
        ]
    )

    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search
    )

    search_index_client.create_or_update_index(index)
    print("✅ Index ready")


# ==========================================
# 2. FILE TEXT EXTRACTION
# ==========================================
def extract_pdf(path):
    reader = PdfReader(path)
    return "\n".join([p.extract_text() or "" for p in reader.pages])


def extract_docx(path):
    doc = Document(path)
    return "\n".join([p.text for p in doc.paragraphs])


def extract_excel(path):
    df = pd.read_excel(path)
    return df.to_string()


def extract_csv(path):
    df = pd.read_csv(path)
    return df.to_string()


def extract_text(path):
    if path.endswith(".pdf"):
        return extract_pdf(path)
    elif path.endswith(".docx"):
        return extract_docx(path)
    elif path.endswith(".xlsx"):
        return extract_excel(path)
    elif path.endswith(".csv"):
        return extract_csv(path)
    else:
        return ""


# ==========================================
# 3. CHUNKING
# ==========================================
def chunk_text(text, size=1000, overlap=200):
    chunks = []
    start = 0

    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap

    return chunks


# ==========================================
# 4. EMBEDDING
# ==========================================
def get_embedding(text):
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )
    return response.data[0].embedding


# ==========================================
# 5. PROCESS LOCAL FILES
# ==========================================
def process_local_files():
    documents = []

    for root, _, files in os.walk(LOCAL_FOLDER):
        for file in files:
            path = os.path.join(root, file)

            print(f"📄 Processing: {file}")

            text = extract_text(path)
            if not text.strip():
                continue

            chunks = chunk_text(text)

            for chunk in chunks:
                embedding = get_embedding(chunk)

                documents.append({
                    "id": str(uuid.uuid4()),
                    "content": chunk,
                    "contentVector": embedding,
                    "fileName": file
                })

    return documents


# ==========================================
# 6. UPLOAD
# ==========================================
def upload_documents(docs):
    batch_size = 100

    for i in range(0, len(docs), batch_size):
        batch = docs[i:i + batch_size]
        search_client.upload_documents(batch)

    print("✅ Upload complete")


# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    create_index()
    docs = process_local_files()
    upload_documents(docs)