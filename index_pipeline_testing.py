from azure.search.documents import SearchClient
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import VectorizedQuery

from config import (
    SEARCH_ENDPOINT, 
    SEARCH_KEY, 
    STORAGE_CONNECTION_STRING, 
    CONTAINER_NAME,
    DOC_INTEL_ENDPOINT,
    DOC_INTEL_KEY
)


search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name="project-state-catalyst",
    credential=AzureKeyCredential(SEARCH_KEY)
)

openai_client = AzureOpenAI(
    api_key="",
    api_version="2024-02-01",
    azure_endpoint=""
)

def get_embedding(text):
    return openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    ).data[0].embedding


def search(query):
    embedding = get_embedding(query)

    vector_query = VectorizedQuery(
        vector=embedding,
        k_nearest_neighbors=5,
        fields="contentVector"
    )

    results = search_client.search(
        search_text=query,
        vector_queries=[vector_query],
        top=5
    )
    print(results)

    print("333333333333333333")
    for r in results:
        print("\n---")
        print(f"File: {r.get('fileName')}")
        print(r.get("content"))

search("Road & Highway Enhancement Programme – Project Update Tracker")