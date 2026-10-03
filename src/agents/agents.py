from langchain.agents import create_agent
from langchain_deepseek import ChatDeepSeek
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.tools.tools import web_search, scrape_url
from dotenv import load_dotenv
import os

load_dotenv()

llm = ChatDeepSeek(model="deepseek-flash", temperature=0)

# search_agent
def build_search_agent():
    return create_agent(
        model=llm,
        tools=[web_search]
    )

# reader_agent
def build_reader_agent():
    return create_agent(
        model=llm,
        tools=[scrape_url]
    )

writer_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert research writer. write a clear, structured and insightful reports."),
    ("human", """Write a detailed research report on the topic below,
    Topic: {topic}

    Research Gathered:
    {research}

    Structure report as:
    - Introduction
    - Key findings (minimum 3 well-explained points)
    - Conclusion
    - Sources (list all urls found in the research)

    Be detailed, factual and professional.""")
])

writer_chain = writer_prompt | llm | StrOutputParser()

critic_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a sharp and constructive research critic. Be honest and specific."),
    ("human", """Review the research reports below and evaluate it strictly.

    Report:
    {report}

    Respond in this exact format:

    Score: X/10

    Strengths:
    - ...
    - ...

    Areas to improve:
    - ...
    - ...

    One line verdict:
    ...""")
])

critic_chain = critic_prompt | llm | StrOutputParser()