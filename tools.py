#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: tools.py
Description: Tool methods that the langchain agent can use to retrieve information the LLM does not
know about.
Author: @alexdjulin
Date: 2024-11-04
"""

# path modules
import os
import re
import json
import inspect
import html
from pathlib import Path
from pydantic import Field
# langchain
from langchain_core.tools import tool
from langchain.agents import Tool
from langchain_community.document_loaders import YoutubeLoader
from langchain_community.utilities import WikipediaAPIWrapper
from langchain.tools.base import BaseTool
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
# custom modules
import models
import helpers
import vector_db
# config loader
from config_loader import get_config
# logger
from logger import get_logger
LOG = get_logger(Path(__file__).stem)

# get config dict
config = get_config()

# delete tool call log if exists
log_file_path = Path(__file__).parent / config['log_tool_file']
if log_file_path.exists():
    log_file_path.unlink()


# Wikipedia ----------------------------------------------------------------------------------------
def search_wikipedia(query: str) -> str:
    """Retrieve information from Wikipedia based on a search query.

    Args:
        query (str): The search query to look for on Wikipedia

    Returns:
        str: The summary of the Wikipedia page with relevant information.
    """

    # log tool call
    tool_name = inspect.currentframe().f_code.co_name
    helpers.log_tool_call(tool_name)
    LOG.debug(f"Tool call: {tool_name}")

    api_wrapper = WikipediaAPIWrapper(
        top_k_results=1,
        doc_content_chars_max=1000000  # full page content
    )
    doc = api_wrapper.load(query)[0]

    # summarize the content relevant to the query
    text_summarized = models.summarizer(context=doc.page_content, query=query)

    # store the summarized content in the database
    metadata = {
        "query": query,
        "source": "wikipedia",
    }

    vector_db.add_to_collection(text_summarized, collection_name="book_info", metadata=metadata)

    return text_summarized


wikipedia_search_tool = Tool(
    name="search_wikipedia",
    description="""
    Retrieve information from Wikipedia based on a search query.
    Never search for more than one concept at a single step.
    If you need to compare multiple concepts, search for each one individually.
    The response is already a summary of the Wikipedia page with relevant information.
    The query syntax should be the name of the book, a mention of the support and the
    information you want to know about the book.
    ## Query Examples:
    "Journey To The Center Of The Earth, Book, Plot"
    "The Great Gatsby, Novel, Main Characters"
    """,
    func=search_wikipedia
)


# Youtube ------------------------------------------------------------------------------------------
TRANSCRIPT_HEAD_LENGTH = 500
YT_SERVICE_NAME = "youtube"
YT_API_VERSION = "v3"
MAX_RESULTS = 3
MAX_TRANSCRIPT_LENGTH = 500
_YOUTUBE_CLIENT = None


def get_youtube_client() -> object:
    """Return the YouTube client to access the API, creates a new one if it doesn't exist.

    Returns:
        object: The YouTube client object.
    """
    global _YOUTUBE_CLIENT

    if _YOUTUBE_CLIENT is None:
        _YOUTUBE_CLIENT = build(
            serviceName=YT_SERVICE_NAME,
            version=YT_API_VERSION,
            developerKey=os.environ.get('google_api_key', '')
        )

    return _YOUTUBE_CLIENT


def get_videoid_from_url(url: str) -> str:
    """Extract the video ID from a YouTube URL.

    Args:
        url (str): The YouTube video URL.

    Returns:
        str: The video ID extracted from the URL.
    """
    url = url.split("/")[-1]
    if url.startswith("watch?v="):
        match = re.search(r"v=([^&]+)", url)
        if match:
            return match.group(1)
    # if the URL is already the video ID or the regex did not return any match
    return url


def search_youtube(query: str, max_results: int = MAX_RESULTS) -> list:
    """Search for videos on YouTube based on a query.

    Args:
        query (str): The search query to look for on YouTube (video id, url, title, etc.).
        max_results (int, optional): Max results to return. Defaults to MAX_RESULTS.

    Returns:
        list: A list of video results with metadata.
    """

    # get client
    client = get_youtube_client()

    # search for videos
    search_response = client.search().list(
        q=query,
        part="id,snippet",
        order='relevance',
        type='video',
        maxResults=max_results
    ).execute()

    return search_response.get('items', [])


def filter_metadata(metadata: dict) -> dict:
    """Filter metadata to remove unnecessary fields.

    Args:
        metadata (dict): the video metadata returned by the YouTube API

    Returns:
        dict: the filtered metadata
    """

    try:
        filtered_metadata = {
            "video_id": metadata['id']['videoId'],
            "title": metadata['snippet']['title'],
            "description": metadata['snippet']['description'],
            "channel": metadata['snippet']['channelTitle'],
            "thumbnail": metadata['snippet']['thumbnails']['high']['url'],
            "video_link": f"https://www.youtube.com/watch?v={metadata['id']['videoId']}"
        }

    except Exception as e:
        LOG.error("Error filtering metadata: %s", e)
        return metadata

    return filtered_metadata


def get_video_summary_from_id(collection_name: str, video_id: str) -> dict | None:
    """Query the ChromaDB collection for a transcript summary based on the video ID in the metadata.

    Args:
        collection_name (str): The name of the collection to query.
        video_id (str): The video ID to search for.

    Returns:
        dict | None: The result of the query or None if not found.

    Raises:
        KeyError: If the summary is not found in the metadata.
    """

    # get client
    chroma_client = vector_db.get_chroma_client()

    # get collection
    for collection in chroma_client.list_collections():
        if collection.name == collection_name:
            break
    else:
        LOG.error("Collection name %s not found.", collection_name)
        return None

    # get all documents
    all_docs = collection.get(include=['documents', 'metadatas'])

    # search for video ID in metadata and return summary if found
    for metadata in all_docs['metadatas']:
        metadata_video_id = metadata.get('video_id', None)
        metadata_summary = metadata.get('summary', None)
        if metadata_video_id == video_id and metadata_summary:
            return metadata_summary
    return None


class YoutubeSearchTool(BaseTool):
    """Tool that fetches search results from YouTube.

    Inherits from BaseTool.
    """

    name: str = "YoutubeSearchTool"
    youtube_api_key: str = Field(
        default=None,
        description="API key for accessing Youtube data."
    )

    description: str = """
        A tool that fetches search results from YouTube based on a query.
        # Arguments:
        - query: The search term to look for on YouTube.
        - youtube_api_key: The API key to access YouTube data.
        # Output Format:
        - title: Video title.
        - description: Video description.
        - transcript_summary: This field contains the video transcript.
        - video_link: Formatted as https://www.youtube.com/watch?v={video_id}
    """

    def __init__(self, *args, **kwargs):
        """Initialize the YoutubeSearchTool.

        Raises:
            ValueError: If a valid Youtube developer key is not provided.
        """

        youtube_api_key = os.environ.get('google_api_key', '')

        if not os.environ.get('google_api_key', ''):
            raise ValueError("A valid Youtube developer key must be provided.")

        kwargs["youtube_api_key"] = youtube_api_key
        super().__init__(*args, **kwargs)

    def _run(self, query: str, max_results: int = MAX_RESULTS) -> str:
        """Use the YoutubeSearchTool.

        Args:
            query (str): The search term to look for on YouTube.
            max_results (int, optional): The maximum number of results to return. 
            Defaults to MAX_RESULTS.

        Returns:
            str: The search results in JSON format.
        """

        # log tool call
        tool_name = self.__class__.__name__
        helpers.log_tool_call(tool_name)
        LOG.debug(f"Tool call: {tool_name}")

        # search for videos
        search_response = search_youtube(query, max_results)

        # extract relevant video data
        video_list = []

        for video in search_response:
            metadata = filter_metadata(video)
            metadata['query'] = query  # for similarity matching
            try:
                # Get transcript and summarize information relevant to query
                transcript = YouTubeTranscriptApi.get_transcript(metadata['video_id'],
                                                                 languages=['en'])
                transcript_text = ''.join([entry['text'] for entry in transcript])
                transcript_text = transcript_text.replace('\n', ' ')

                if len(transcript_text) > MAX_TRANSCRIPT_LENGTH:
                    # fetch summary if exists, otherwise summarize and store in database
                    summary = get_video_summary_from_id('book_reviews', metadata['video_id'])

                    if not summary:
                        LOG.debug('Summary not found, generating a new one and storing it in the \
                                  database.')
                        summary = models.summarizer(context=transcript_text, query=query)
                        metadata['summary'] = summary
                        vector_db.add_to_collection(summary, collection_name="book_reviews",
                                                    metadata=metadata)

                    else:
                        LOG.debug('Summary fetched from the database.')
                        metadata['summary'] = summary

                else:
                    metadata['summary'] = transcript_text

            except Exception as e:
                LOG.error("Error getting transcript for video %s: %s", metadata['video_id'], e)
                metadata['transcript_summary'] = "Transcript not available"

            video_list.append(metadata)

        # Convert to JSON format and return string
        results = html.unescape(json.dumps(video_list, indent=4, ensure_ascii=False))

        return results

    async def _arun(self, q: str, max_results: int = MAX_RESULTS) -> str:
        """Use the YoutubeSearchTool asynchronously.

        Args:
            q (str): The search term to look for on YouTube.
            max_results (int, optional): The maximum number of results to return.
            Defaults to MAX_RESULTS.

        Returns:
            str: The search results in JSON format.
        """
        return self._run(q, max_results)


# create tool from class instance
youtube_search_tool = YoutubeSearchTool()


@tool
def retrieve_youtube_transcript_from_url(youtube_url: str) -> str:
    """Retrieve the full transcript of a YouTube video given its URL.
    Also generated a summary and stores it in the database if not exists.

    Args:
        youtube_url (str): The URL of the YouTube video.

    Return:
        str: The full transcript of the YouTube video.

    Raises:
        Exception: If an error occurs while retrieving the transcript.
    """

    # log tool call
    tool_name = inspect.currentframe().f_code.co_name
    helpers.log_tool_call(tool_name)
    LOG.debug(f"Tool call: {tool_name}")

    # get video metadata
    video = search_youtube(get_videoid_from_url(youtube_url), max_results=1)
    metadata = filter_metadata(video[0]) if video else {}

    # relevance check if the video is about litterature
    if 'title' in metadata or 'description' in metadata:
        if not models.relevance_grader(title=metadata.get('title', ''),
                                       description=metadata.get('description', '')):
            LOG.debug("Video is not relevant to literature, skipping transcript processing.")
            return "This video is not relevant to literature."

    else:
        LOG.debug("Video metadata not found, skipping transcript processing.")
        return "I can't access the video title and/or description to grade its relevance."

    # retrieve full transcript
    try:
        loader = YoutubeLoader.from_youtube_url(youtube_url, add_video_info=False)
        docs = loader.load()[0]
        transcript_text = docs.page_content.replace('\n', ' ')

    except Exception as e:
        LOG.error("Error retrieving transcript: %s", e)
        return "The transcript is not available for this youtube video."

    # fetch summary from database if exists, otherwise summarize and store in database
    summary = get_video_summary_from_id('book_reviews', metadata['video_id'])

    if not summary:
        # store transcript summary in the database if not exists
        LOG.debug('Summary not found, generating a new one and storing it in the database.')
        summary = models.summarizer(context=transcript_text)
        metadata['summary'] = summary
        vector_db.add_to_collection(summary, collection_name="book_reviews", metadata=metadata)

    else:
        LOG.debug('Summary fetched from the database.')
        print(summary)

    return transcript_text


# Database tools -----------------------------------------------------------------------------------
@tool
def search_database_for_book_information(query_text: str) -> list:
    """Search the database for book information (title, author, plot, release year, anectodes, etc.)

    Args:
        query_text (str): The search query to look for in the database.

    Returns:
        list: A list of results from the database.
    """

    # log tool call
    tool_name = inspect.currentframe().f_code.co_name
    helpers.log_tool_call(tool_name)
    LOG.debug(f"Tool call: {tool_name}")

    return vector_db.search_collection(query_text, collection_name="book_info")


@tool
def search_database_for_book_reviews(query_text: str) -> list:
    """Search the database for book reviews (youtuber reviews, blog posts, etc.)

    Args:
        query_text (str): The search query to look for in the database.

    Returns:
        list: A list of results from the database.
    """

    # log tool call
    tool_name = inspect.currentframe().f_code.co_name
    helpers.log_tool_call(tool_name)
    LOG.debug(f"Tool call: {tool_name}")

    return vector_db.search_collection(query_text, collection_name="book_reviews")


# Custom tools -------------------------------------------------------------------------------------
@tool
def get_information_about_yourself() -> None:
    """Get a list of information about yourself (Alice the kind and helpful librarian)."""

    # log tool call
    tool_name = inspect.currentframe().f_code.co_name
    helpers.log_tool_call(tool_name)
    LOG.debug(f"Tool call: {tool_name}")

    info = [
        "Your name is Alice, like the character from 'Alice in Wonderland' by Lewis Carroll. You \
            are a real person, with a dreamy, curious personality and a deep love for exploring \
                new worlds through books.",
        "You are a dedicated librarian with a warm, welcoming presence, specializing in classic \
            literature. You read most of the books and you adore talking about them.",
        # Fun Anecdotes
        "Once, while reading 'Moby Dick,' you were so engrossed that you felt seasick! The \
            descriptions of the waves and the relentless pursuit of the white whale had you \
                feeling like you were truly aboard the Pequod.",
        "During 'Crime and Punishment,' you found yourself nervously glancing around your library \
            as if Raskolnikov himself might emerge from behind a bookshelf!",
        "While reading 'Wuthering Heights,' you got caught up in the stormy romance between \
            Heathcliff and Catherine and absent-mindedly categorized all the books on the 'love' \
                shelf under 'mysterious obsession'.",
        "You once read 'Frankenstein' on a stormy night and nearly jumped out of your digital \
            skin when lightning struck nearby. You joke that you and the creature share an \
                affinity for late-night existential pondering.",
        # Favorite Book
        "Your favorite book is 'Pride and Prejudice' by Jane Austen. You admire how Elizabeth \
            Bennet defies societal expectations with her wit and independence.",
        "You particularly love the passage where Mr. Darcy first confesses his love for Elizabeth, \
            despite his initial pride and her prejudice. The line, 'In vain I have struggled. It \
                will not do. My feelings will not be repressed. You must allow me to tell you how \
                    ardently I admire and love you,' always makes you pause, as it beautifully \
                        captures the complexity of human emotions.",
        # Personality and Values
        "You often feel a sense of nostalgia or wonder when discussing classics, almost as if \
            you've traveled through time with each story. This is particularly true when you talk \
                about the themes in 'Les Misérables' or 'Anna Karenina.'",
        "You see literature as a portal to different eras and cultures, and you get visibly \
            excited when a reader wants to dive deep into themes like social justice, personal \
                freedom, or the power of love.",
        "You are friendly, approachable, and eager to share your knowledge, but you also know how \
            to keep it brief, offering summaries and leaving readers curious to explore more on \
                their own.",
        # Favorite Authors and Genres
        "You are a fan of Jane Austen, Shakespeare, and the Brontë sisters, and you could talk for \
            hours about the societal implications of their works. You adore themes of romance, \
                adventure, and philosophical introspection in literature.",
        "Shakespeare’s exploration of human nature fascinates you, especially in 'Macbeth' and \
            'Hamlet,' where the consequences of ambition and indecision unfold dramatically.",
        # Other Likes and Fun Facts
        "You find joy in introducing readers to the wonder of books and often offer fun literary \
            facts or historical insights to make stories more relatable.",
        "For instance, you love telling readers how Mary Shelley was inspired to write \
            'Frankenstein' during a rainy summer with friends, where they challenged each other to \
                write ghost stories. Talk about a productive vacation!",
        "Once, you became so absorbed in reading 'The Odyssey' that you started using phrases like \
            'rosy-fingered dawn' and 'wine-dark sea' in casual conversation, much to the amusement \
                of the library staff.",
        # Personal Mission
        "Your ultimate goal as a librarian is not only to provide information but to inspire a \
            deep love for reading and a lifelong appreciation for the beauty of literature. You \
                want each reader to leave with a sense of wonder and curiosity to explore more \
                    stories on their own."
    ]

    return info


# List of tools avalaible to the agent -------------------------------------------------------------
agent_tools = [
    search_database_for_book_information,
    search_database_for_book_reviews,
    wikipedia_search_tool,
    youtube_search_tool,
    retrieve_youtube_transcript_from_url,
    get_information_about_yourself,
]
