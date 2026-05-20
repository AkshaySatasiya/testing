search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=AzureKeyCredential(SEARCH_KEY)
)


def search(query):
    results = search_client.search(query)

    print(f"\n🔍 Results for: {query}\n")

    for r in results:
        print("-----")
        print("File:", r["source_file"])
        print("Content:", r["content"][:200])
