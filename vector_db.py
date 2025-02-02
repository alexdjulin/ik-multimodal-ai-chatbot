#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: chroma_db.py
Description: Functions to interact with the chroma vectorstore, initialise it, add documents and 
search for similar documents.
Author: @alexdjulin
Date: 2024-11-04
"""

import uuid
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from langchain.text_splitter import CharacterTextSplitter
import chromadb
from chromadb.utils import embedding_functions
# load config
from config_loader import get_config
# logger
from logger import get_logger
LOG = get_logger(Path(__file__).stem)

# get config dict
config = get_config()

# global variables
_CHROMA_CLIENT = None
_EMBEDDER = None
_SPLITTER = None
SEPARATOR = "-" * 80
COLLECTIONS = ['book_info', 'book_reviews']


# CHROMADB FUNCTIONS -------------------------------------------------------------------------------
def get_chroma_client() -> chromadb.PersistentClient:
    """Get the database client, initialising it if it doesn't exist.

    Returns:
        chromadb.PersistentClient: the database client
    """

    global _CHROMA_CLIENT
    if _CHROMA_CLIENT is None:
        _CHROMA_CLIENT = initialise_database()
    return _CHROMA_CLIENT


def get_embedder() -> SentenceTransformer:
    """Get the SentenceTransformer model, initialising it if it doesn't exist.

    Returns:
        SentenceTransformer: the SentenceTransformer model
    """

    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = SentenceTransformer(config['embedding_model'])
    return _EMBEDDER


def get_splitter() -> CharacterTextSplitter:
    """Get the text splitter, initialising it if it doesn't exist.

    Returns:
        CharacterTextSplitter: the text splitter
    """

    global _SPLITTER
    if _SPLITTER is None:
        _SPLITTER = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    return _SPLITTER


def relevance_grader(document: str, query: str) -> float:
    """Return the cosine similarity between a retrieved document and the input query to help decide
    if it should be stored in the database or not.

    Args:
        text (str): the retrieved document text
        query (str): the input query text

    Returns:
        float: the cosine similarity between the document and query
    """

    # get embedder
    embedding_model = get_embedder()

    # Embed the query and document
    document_embedding = embedding_model.encode([document])
    query_embedding = embedding_model.encode([query])

    # Return the cosine similarity
    return cosine_similarity(document_embedding, query_embedding)[0][0]


def initialise_database() -> chromadb.PersistentClient:
    """Initialise the database with two collections: `book_info` and `book_reviews`.

    Returns:
        chromadb.PersistentClient: the database client
    """

    # initialise the client
    chroma_client = chromadb.PersistentClient(path=config['chromadb_path'])

    # Create two collections: `book_info` and `book_reviews`
    for collection_name in COLLECTIONS:
        create_collection(chroma_client, collection_name)

    return chroma_client


def create_collection(chroma_client: chromadb.PersistentClient, collection_name: str) -> None:
    """Create a new collection in the database.

    Args:
        chroma_client (chromadb.PersistentClient): the database client
        collection_name (str): name of the collection to create
    """

    # get client
    existing_collections = [collection.name for collection in chroma_client.list_collections()]

    # check if collection already exists
    if collection_name in existing_collections:
        LOG.warning("Collection name %s already exists.", collection_name)
        return

    # get embedder
    embedding_model = get_embedder()

    # create collection
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(embedding_model)
    chroma_client.create_collection(
        name=collection_name,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"}
    )

    LOG.debug("Collection '%s' has been created.", collection_name)


def add_to_collection(text: str, collection_name: str, metadata: dict) -> None:
    """Add a document to a database collection in chunks.

    Args:
        text (str): text to add
        collection (str): collection name to add to
        metadata (dict): metadata to add to the document
    """

    # get client
    chroma_client = get_chroma_client()

    # get collection
    for collection in chroma_client.list_collections():
        if collection.name == collection_name:
            break
    else:
        LOG.error("Collection name %s not found.", collection_name)
        return

    # Dont add the document if it does not meet the similarity threshold (irrelevant to query)
    if 'query' in metadata:
        similarity = relevance_grader(text, metadata['query'])
        if similarity < config['add_similarity_threshold']:
            LOG.debug("Document not added to %s. Cosine similarity: %s",
                      collection_name, similarity)
            return

    # get embedder
    embedding_model = get_embedder()

    # create a unique id for the document
    document_id = str(uuid.uuid4())

    # Split the text into chunks
    text_splitter = get_splitter()
    chunks = text_splitter.split_text(text)
    chunks_len = len(chunks)

    # Add each chunk to the collection
    for i, chunk in enumerate(chunks):
        chunk_id = f"{document_id}_{i}"
        embedding = embedding_model.encode(chunk)
        chunk_metadata = metadata.copy()
        chunk_metadata.update({
            "document_id": document_id,  # to link chunks to the main document
            "added_on": datetime.now().isoformat(),  # to track when the chunk was added
        })

        collection.add(
            ids=[chunk_id],
            documents=[chunk],
            metadatas=[chunk_metadata],
            embeddings=[embedding]
        )

    LOG.debug("Document:\n%s\nSplit: %s chunks\nAdded to collection: %s\nMetadata:\n%s",
              text, chunks_len, collection_name, metadata)


def search_collection(query: str, collection_name: str, n_results: int = 3) -> list:
    """Search a database collection for similar documents.

    Args:
        query_text (str): text to search for
        collection (str): collection name to searh in
        n_results (int, optional): number of results to return. Defaults to 3.

    Returns:
        list: list of search results
    """

    # get client
    chroma_client = get_chroma_client()

    # get collection
    for collection in chroma_client.list_collections():
        if collection.name == collection_name:
            break
    else:
        LOG.error("Collection name %s not found.", collection_name)
        return []

    # get embedder
    embedding_model = get_embedder()

    # encode text
    embedding = embedding_model.encode(query)

    search_results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results,
        include=['documents', 'metadatas', 'distances']
    )

    # filter results based on distance threshold
    filtered_results = {
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]]
    }

    for i, distance in enumerate(search_results["distances"][0]):
        if distance < config['search_similarity_threshold']:
            filtered_results["documents"][0].append(search_results["documents"][0][i])
            filtered_results["metadatas"][0].append(search_results["metadatas"][0][i])
            filtered_results["distances"][0].append(distance)

    return filtered_results


# DATABASE MAINTENANCE FUNCTIONS (NOT REQUIRED TO RUN THE APP) -------------------------------------
def print_collection_contents(collection_name: str) -> None:
    """Print the contents of a ChromaDB collection.

    Args:
        collection_name (str): name of the collection to print
    """

    # Get client
    chroma_client = get_chroma_client()

    # Get collection
    collection = None
    for coll in chroma_client.list_collections():
        if coll.name == collection_name:
            collection = coll
            break

    if collection is None:
        raise ValueError(f"Collection name {collection_name} not found.")

    # Retrieve all documents and metadata from the collection
    all_docs = collection.get(include=['documents', 'metadatas'])

    # Print the number of documents in the collection
    print(SEPARATOR)
    print(f"Retrieved {len(all_docs['documents'])} documents from collection {collection_name}")

    # Print the contents of the collection
    for i, (doc, metadata) in enumerate(zip(all_docs['documents'], all_docs['metadatas'])):
        print(SEPARATOR)
        print(f"Document {i + 1} - Metadata: {metadata}")
        print(doc)
    print(SEPARATOR)


def remove_duplicates_by_query_or_title(collection_name: str) -> None:
    """Remove duplicate documents from a ChromaDB collection based on either the query or title
    fields in metadata.

    Args:
        collection_name (str): name of the collection to remove duplicates from
    """

    # Get client
    chroma_client = get_chroma_client()

    # Get collection
    collection = None
    for coll in chroma_client.list_collections():
        if coll.name == collection_name:
            collection = coll
            break

    if collection is None:
        raise ValueError(f"Collection name {collection_name} not found.")

    # Retrieve all documents and metadata from the collection
    all_docs = collection.get(include=['documents', 'metadatas'])

    # Dictionaries to track unique content by query and title
    unique_queries = defaultdict(list)
    unique_titles = defaultdict(list)

    # Identify duplicates based on the query and title fields in metadata
    for i, metadata in enumerate(all_docs['metadatas']):
        query = metadata.get('query')
        title = metadata.get('title')
        doc_id = all_docs['ids'][i]  # Ensure to use a unique identifier from the returned data

        if query:
            if query not in unique_queries:
                unique_queries[query].append(doc_id)
            else:
                # Collect duplicate IDs for the query
                unique_queries[query].append(doc_id)

        if title:
            if title not in unique_titles:
                unique_titles[title].append(doc_id)
            else:
                # Collect duplicate IDs for the title
                unique_titles[title].append(doc_id)

    # Collect IDs of documents to delete (keep the first occurrence, remove the rest)
    duplicate_ids_query = [ids[1:] for ids in unique_queries.values() if len(ids) > 1]
    duplicate_ids_title = [ids[1:] for ids in unique_titles.values() if len(ids) > 1]

    # Combine all duplicate IDs and flatten the list
    duplicate_ids = {item for sublist in (duplicate_ids_query + duplicate_ids_title)
                     for item in sublist}

    if duplicate_ids:
        # Delete duplicates from the collection
        collection.delete(ids=list(duplicate_ids))
        LOG.debug("Removed %d duplicate documents.", len(duplicate_ids))
    else:
        LOG.debug("No duplicates found.")


def reset_collection(collection_name: str) -> None:
    """Delete and recreate a collection to clear all its contents.

    Args:
        collection_name (str): Name of the collection to reset.
    """

    # Get client
    chroma_client = get_chroma_client()

    # Check if the collection exists and delete it
    existing_collections = [coll.name for coll in chroma_client.list_collections()]
    if collection_name in existing_collections:
        confirmation = input(f"Are you sure you want to delete the collection '{collection_name}'?"
                             "THIS WILL REMOVE ALL DATA PERMANENTLY. Type 'YES' to confirm: ")

        if confirmation == 'YES':
            chroma_client.delete_collection(name=collection_name)
            LOG.debug("Collection '%s' has been deleted.", collection_name)
        else:
            LOG.debug("Operation cancelled. No changes were made.")
            return

    # Recreate the collection
    create_collection(chroma_client, collection_name)
