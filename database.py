#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: database.py
Description: Functions to interact with the database, initialise it, add documents and search for similar documents.
Author: @alexdjulin
Date: 2024-11-01
"""

import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
from datetime import datetime
from pathlib import Path
import uuid
# load config
from config_loader import get_config
config = get_config()
# logger
from logger import get_logger
LOG = get_logger(Path(__file__).stem)

# global client to initialise database only once
_chroma_client = None
_model = None


def get_chroma_client() -> chromadb.PersistentClient:
    """Get the database client, initialising it if it doesn't exist.

    Returns:
        chromadb.PersistentClient: the database client
    """

    global _chroma_client
    if _chroma_client is None:
        _chroma_client = initialise_database()
    return _chroma_client


def get_embedder() -> SentenceTransformer:
    """Get the SentenceTransformer model, initialising it if it doesn't exist.

    Returns:
        SentenceTransformer: the SentenceTransformer model
    """

    global _model
    if _model is None:
        _model = SentenceTransformer(config['embedding_model'])
    return _model


def initialise_database() -> chromadb.PersistentClient:
    """Initialise the database with two collections: `book_info` and `book_reviews`.

    Returns:
        chromadb.PersistentClient: the database client
    """

    # initialise the client
    chroma_client = chromadb.PersistentClient(path=config['db_path'])
    existing_collections = [collection.name for collection in chroma_client.list_collections()]

    # Create two collections: `book_info` and `book_reviews`
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(config['embedding_model'])

    for collection_name in ["book_info", "book_reviews"]:
        if collection_name not in existing_collections:
            chroma_client.create_collection(
                name=collection_name,
                embedding_function=embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )

    return chroma_client


def add_to_collection(text: str, collection_name: str, metadata: dict) -> None:
    """Add a document to a database collection.

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
        LOG.error(f"Collection name {collection_name} not found.")
        return

    # get embedder
    embedding_model = get_embedder()

    # encode text
    embedding = embedding_model.encode(text)
    metadata.update({
        "added_on": metadata.get("added_on", datetime.now().isoformat())
    })

    collection.add(
        ids=str(uuid.uuid4()),
        documents=[text],
        metadatas=[metadata],
        embeddings=[embedding]
    )


def search_collection(text: str, collection_name: str, n_results: int = 5) -> list:
    """Search a database collection for similar documents.

    Args:
        query_text (str): text to search for
        collection (str): collection name to searh in
        n_results (int, optional): number of results to return. Defaults to 5.

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
        LOG.error(f"Collection name {collection_name} not found.")
        return []

    # get embedder
    embedding_model = get_embedder()

    # encode text
    embedding = embedding_model.encode(text)

    results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results
    )

    return results
