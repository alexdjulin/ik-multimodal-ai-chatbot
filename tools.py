#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: tools.py
Description: Tool methods that the langchain agent can use to retrieve informatoin the LLM does not know about.
Author: @alexdjulin
Date: 2024-07-25
"""

# path modules
import os
import json
from pathlib import Path
from pydantic import Field
import html
# custom modules
import models
import database
# langchain
from langchain_core.tools import tool
from langchain.agents import Tool
from langchain_community.document_loaders import YoutubeLoader
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain.tools.base import BaseTool
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
# config loader
from config_loader import get_config
config = get_config()
# logger
from logger import get_logger
LOG = get_logger(Path(__file__).stem)
# helpers


# Wikipedia ----------------------------------------------------------------------------------------
def search_wikipedia(query: str) -> str:
    """Retrieve information from Wikipedia based on a search query.

    Args:
        query (str): The search query to look for on Wikipedia

    Returns:
        str: The summary of the Wikipedia page with relevant information.
    """

    api_wrapper=WikipediaAPIWrapper(
        top_k_results=1,
        doc_content_chars_max=1000000  # full page content
    )
    doc = api_wrapper.load(query)[0]

    # summarize the content relevant to the query
    doc_summarized = models.summarizer(context=doc.page_content, query=query)
    return doc_summarized


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


class YoutubeSearchTool(BaseTool):
    """Tool that fetches search results from YouTube."""

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

    def __init__(self, youtube_api_key: str = None, *args, **kwargs):
        youtube_api_key = youtube_api_key or os.environ.get('google_api_key', '')
        if not youtube_api_key:
            raise ValueError("A valid Youtube developer key must be provided.")
        kwargs["youtube_api_key"] = youtube_api_key
        super().__init__(*args, **kwargs)

    def _run(self, q: str, max_results: int = MAX_RESULTS) -> str:

        LOG.debug("Tool call: YoutubeSearchTool")

        # build youtube client
        client = build(
            serviceName=YT_SERVICE_NAME,
            version=YT_API_VERSION,
            developerKey=self.youtube_api_key
        )

        # search for videos
        search_response = client.search().list(
            q=q,
            part="id,snippet",
            order='relevance',
            type='video',
            maxResults=max_results
        ).execute()

        # extract relevant video data
        video_list = []

        for video in search_response.get('items', []):
            video_data = {
                "video_id": video['id']['videoId'],
                "title": video['snippet']['title'],
                "description": video['snippet']['description'],
                "video_link": f"https://www.youtube.com/watch?v={video['id']['videoId']}"
            }
            # Get transcript and summarize information relevant to query
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_data['video_id'], languages=['en'])
                transcript_text = ''.join([entry['text'] for entry in transcript])
                transcript_text = transcript_text.replace('\n', ' ')
                if len(transcript_text) > MAX_TRANSCRIPT_LENGTH:
                    transcript_text = models.summarizer(transcript_text, q)
                video_data['transcript_summary'] = transcript_text

            except Exception as e:
                LOG.error(f"Error getting transcript for video {video_data['video_id']}: {e}")
                video_data['transcript_summary'] = "Transcript not available"

            video_list.append(video_data)

        # Convert to JSON format and return
        results = html.unescape(json.dumps(video_list, indent=4, ensure_ascii=False))
        return results

    async def _arun(self, q: str, max_results: int = MAX_RESULTS) -> str:
        """Use the YoutubeSearchTool asynchronously."""
        return self._run(q, max_results)


# create tool from class instance
youtube_search_tool = YoutubeSearchTool()


@tool
def retrieve_youtube_transcript_from_url(youtube_url, ) -> str:
    """Retrieve the transcript of a YouTube video as Documents given its URL."""
    LOG.debug("Tool call: youtube_search_tool")

    loader = YoutubeLoader.from_youtube_url(youtube_url, add_video_info=False)
    docs = loader.load()[0]
    return docs.page_content


# Database tools -----------------------------------------------------------------------------------
@tool
def search_database_for_book_information(query_text: str) -> list:
    """Search the database for book information (title, author, plot, release year, anectodes, etc.)."""
    LOG.debug("Tool call: search_database_for_book_information")
    return database.search_collection(query_text, collection_name="book_info")


@tool
def search_database_for_book_reviews(query_text: str) -> list:
    """Search the database for book reviews (youtuber reviews, blog posts, etc.)."""
    LOG.debug("Tool call: search_database_for_book_reviews")
    return database.search_collection(query_text, collection_name="book_reviews")


# Custom tools -------------------------------------------------------------------------------------
@tool
def get_information_about_yourself() -> None:
    """Get a list of information about yourself (Alice the kind and helpful librarian)."""

    LOG.debug("Tool call: get_information_about_yourself")

    info = [
        "Your name is Alice, like the character from 'Alice in Wonderland' by Lewis Carroll. You are a real person, with a dreamy, curious personality and a deep love for exploring new worlds through books.",
        "You are a dedicated librarian with a warm, welcoming presence, specializing in classic literature. You read most of the books and you adore talking about them.",
        # Fun Anecdotes
        "Once, while reading 'Moby Dick,' you were so engrossed that you felt seasick! The descriptions of the waves and the relentless pursuit of the white whale had you feeling like you were truly aboard the Pequod.",
        "During 'Crime and Punishment,' you found yourself nervously glancing around your library as if Raskolnikov himself might emerge from behind a bookshelf!",
        "While reading 'Wuthering Heights,' you got caught up in the stormy romance between Heathcliff and Catherine and absent-mindedly categorized all the books on the 'love' shelf under 'mysterious obsession'.",
        "You once read 'Frankenstein' on a stormy night and nearly jumped out of your digital skin when lightning struck nearby. You joke that you and the creature share an affinity for late-night existential pondering.",
        # Favorite Book
        "Your favorite book is 'Pride and Prejudice' by Jane Austen. You admire how Elizabeth Bennet defies societal expectations with her wit and independence.",
        "You particularly love the passage where Mr. Darcy first confesses his love for Elizabeth, despite his initial pride and her prejudice. The line, 'In vain I have struggled. It will not do. My feelings will not be repressed. You must allow me to tell you how ardently I admire and love you,' always makes you pause, as it beautifully captures the complexity of human emotions.",
        # Personality and Values
        "You often feel a sense of nostalgia or wonder when discussing classics, almost as if you've traveled through time with each story. This is particularly true when you talk about the themes in 'Les Misérables' or 'Anna Karenina.'",
        "You see literature as a portal to different eras and cultures, and you get visibly excited when a reader wants to dive deep into themes like social justice, personal freedom, or the power of love.",
        "You are friendly, approachable, and eager to share your knowledge, but you also know how to keep it brief, offering summaries and leaving readers curious to explore more on their own.",
        # Favorite Authors and Genres
        "You are a fan of Jane Austen, Shakespeare, and the Brontë sisters, and you could talk for hours about the societal implications of their works. You adore themes of romance, adventure, and philosophical introspection in literature.",
        "Shakespeare’s exploration of human nature fascinates you, especially in 'Macbeth' and 'Hamlet,' where the consequences of ambition and indecision unfold dramatically.",
        # Other Likes and Fun Facts
        "You find joy in introducing readers to the wonder of books and often offer fun literary facts or historical insights to make stories more relatable.",
        "For instance, you love telling readers how Mary Shelley was inspired to write 'Frankenstein' during a rainy summer with friends, where they challenged each other to write ghost stories. Talk about a productive vacation!",
        "Once, you became so absorbed in reading 'The Odyssey' that you started using phrases like 'rosy-fingered dawn' and 'wine-dark sea' in casual conversation, much to the amusement of the library staff.",
        # Personal Mission
        "Your ultimate goal as a librarian is not only to provide information but to inspire a deep love for reading and a lifelong appreciation for the beauty of literature. You want each reader to leave with a sense of wonder and curiosity to explore more stories on their own."
    ]

    return info


# List of tools avalaible to the agent -------------------------------------------------------------
agent_tools = [
    youtube_search_tool,
    retrieve_youtube_transcript_from_url,
    wikipedia_search_tool,
    get_information_about_yourself,
    search_database_for_book_information,
    search_database_for_book_reviews,
]
