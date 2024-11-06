#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filename: models.py
Description: This file contains the different models used in the project.
Example: Agent chatbot, summarizer, extractor.
Author: @alexdjulin
Date: 2024-11-02
"""

import os
import json
from pathlib import Path
import tools
# langchain
from langchain_openai import ChatOpenAI
from langchain.docstore.document import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.memory import ConversationBufferWindowMemory
# config loader
from config_loader import get_config
config = get_config()


def load_prompt_messages(prompt_filepath: str = None) -> list[tuple[str, str]]:
    ''' Loads messages from a jsonl file and returns them as a list of tuples.

    Args:
        prompt_filepath (str): path to jsonl file. Default to None.

    Return:
        (list[tuple[str, str]]): list of tuples with role and content
    '''

    # load prompt file from config if not provided
    if prompt_filepath is None:
        # concatenate current path with prompt file path
        prompt_filepath = os.path.join(Path(__file__).parent, config['prompt_filepath'])

    # check if prompt file exists
    if not os.path.exists(prompt_filepath):
        return []

    messages = []

    # Open and read the file line by line
    with open(prompt_filepath, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                message = json.loads(line)  # Parse JSON only once
                # Ensure both 'role' and 'content' are present before appending
                if 'role' in message and 'content' in message:
                    messages.append((message['role'], message['content']))
            except json.JSONDecodeError:
                continue

    return messages


def llm_agent() -> AgentExecutor:
    ''' Defines an LLM langchain agent with access to a list of tools to perform a task.

    Return:
        (AgentExecutor): the agent instance
    '''

    # load llm
    llm = ChatOpenAI(
        model=config['generative_model'],
        api_key=os.environ['OPENAI_API_KEY'],
        temperature=config['openai_temperature'],
    )

    # create prompt
    messages = load_prompt_messages()

    # add default placeholders
    messages.append(("placeholder", "{chat_history}"))
    messages.append(("human", "{input}"))
    messages.append(("placeholder", "{agent_scratchpad}"))

    # create prompt
    prompt = ChatPromptTemplate.from_messages(messages)

    # create langchain agent
    agent = create_tool_calling_agent(
        tools=tools.agent_tools,
        llm=llm,
        prompt=prompt
    )

    memory = ConversationBufferWindowMemory(
        memory_key='chat_history',
        return_messages=True
    )

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools.agent_tools,
        verbose=config['agent_verbose'],
        handle_parsing_errors=True,
        memory=memory
    )

    return agent_executor


def summarizer(context: str, query: str = None) -> str:
    """Extract and summarize information from a given context relevant to the query.

    Args:
        context (str): text to summarize
        query (str, optional): input query

    Returns:
        str: summary of the text
    """

    prompt_text = """
    Given the following context and query, extract and summarize all relevant information.
    If no query is provided, summarize the entire context.
    Return a single string with the extracted information in a few sentences.
    Make sure you don't omit any important details of the video.
    Don't include the context or query in the response.
    Don't return lists or bullet points, just a single string.

    ## Context:
    {context}
    ## Query:
    {query}
    """

    prompt = ChatPromptTemplate.from_messages(
        [("system", prompt_text),]
    )

    llm = ChatOpenAI(
        temperature=0,
        model_name=config['summarizer_model'],
        api_key=os.getenv("OPENAI_API_KEY")
    )

    chain = create_stuff_documents_chain(llm, prompt)
    document = Document(page_content=context)
    return chain.invoke({"context": [document], "query": query})


def relevance_grader(title: str, description: str) -> bool:
    """Rate the relevance of a youtube video title and description to decide if it is a book
    review or summary.

    Args:
        title (str): youtube video title
        description (str): youtube video description

    Returns:
        bool: True if the video is relevant, False otherwise

    Raises:
        ValueError: if the relevance cannot be determined
    """

    prompt_text = """
    Given the following youtube video title and descripion, rate the relevance of the video to a
    book review, summary, discussion, analysis or anything related to literature.
    Rate the relevance on a scale from 1 to 5, where 1 is not relevant and 5 is very relevant.
    Only return a single number between 1 and 5, do not add any additional text.

    {context}
    """

    prompt = ChatPromptTemplate.from_messages(
        [("system", prompt_text),]
    )

    llm = ChatOpenAI(
        temperature=0,
        model_name=config['relevance_grader_model'],
        api_key=os.getenv("OPENAI_API_KEY")
    )

    chain = create_stuff_documents_chain(llm, prompt)
    document = Document(page_content=f"Title: {title}\nDescription: {description}")
    grade = chain.invoke({"context": [document]})

    try:
        return int(grade) > 3
    except ValueError:
        return False
