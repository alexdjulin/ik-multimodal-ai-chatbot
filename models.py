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
import helpers
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
    messages = helpers.load_prompt_messages()

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


# def summarizer(context: str) -> str:
#     """Summarize a text into a few sentences.

#     Args:
#         context (str): text to summarize

#     Returns:
#         str: summary of the text
#     """

#     prompt_text = """
#     Write a concise summary of the following context in a few sentences.
#     Return a single string with the summary.
#     Don't include the context in the response.
#     Don't return lists or bullet points, just a single string.
#     ## Context:
#     {context}
#     """

#     prompt = ChatPromptTemplate.from_messages(
#         [("system", prompt_text),]
#     )

#     llm = ChatOpenAI(
#         temperature=0,
#         model_name=config["summarizer_model"],
#         api_key=os.getenv("OPENAI_API_KEY")
#     )

#     chain = create_stuff_documents_chain(llm, prompt)
#     document = Document(page_content=context)
#     return chain.invoke({"context": [document]})


def summarizer(context: str, query: str) -> str:
    """Extract and summarize information from a given context relevant to the query.

    Args:
        context (str): text to summarize
        query (str, optional): input query

    Returns:
        str: summary of the text
    """

    prompt_text = """
    Given the following context and query, extract and summarize all relevant information.
    Return a single string with the extracted information.
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
        model_name='gpt-3.5-turbo-0125',
        api_key=os.getenv("OPENAI_API_KEY")
    )

    chain = create_stuff_documents_chain(llm, prompt)
    document = Document(page_content=context)
    return chain.invoke({"context": [document], "query": query})