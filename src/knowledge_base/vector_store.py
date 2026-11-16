import chromadb

# Persistent storage — data survives restarts
client = chromadb.PersistentClient(path="./chroma_data")

# A "collection" is like a table — one for our knowledge base
collection = client.get_or_create_collection(name="knowledge_base")

print(collection.count())  # Print the number of documents in the collection
print(collection.name)  # Print the name of the collection