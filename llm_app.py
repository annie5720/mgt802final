import os
import streamlit as st
import openai
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from PyPDF2 import PdfFileReader
from PyPDF2 import PdfReader
import io
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import textwrap

#Libraries for Document Splitting, embeddings and vector stores
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.embeddings import CohereEmbeddings

#Chain for Q&A after retrieving external documents
from langchain.chains import RetrievalQA

#Using ChatOpenAI
from langchain.chat_models import ChatOpenAI            #used for GPT3.5/4 model

os.environ["OPENAI_API_KEY"] = "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"
st.title("Whatsapp Bot Generator")
biz_info=""


# Function to extract all links from a URL
def extract_links(url, domain_name):
    links = set()
    try:
        response = requests.get(url)
        response.raise_for_status()  # Check if the request was successful

        soup = BeautifulSoup(response.content, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if urlparse(href).netloc == domain_name:
                links.add(urljoin(url, href))
    except Exception as e:
        st.error(f"Error fetching links from {url}: {e}")
    
    return links

# Function to fetch content from a URL
def fetch_page_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Check if the request was successful
        soup = BeautifulSoup(response.content, 'html.parser')
        text = soup.get_text(strip=True)
        return text
    except Exception as e:
        return f"Error fetching page: {e}"

# Function to extract all links from a URL and fetch their content
def extract_links_and_content(url):
    links_content = {}
    domain_name = urlparse(url).netloc

    # Include the main page in the processing
    links_content[url] = fetch_page_content(url)

    try:
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if urlparse(href).netloc == domain_name:
                full_url = urljoin(url, href)
                if full_url not in links_content:
                    content = fetch_page_content(full_url)
                    links_content[full_url] = content
    except Exception as e:
        st.error(f"Error fetching links from {url}: {e}")
    
    return links_content

# Function to recursively extract all link
def recursive_crawl(url, domain_name, links_content, max_depth=1, current_depth=0):
    if current_depth > max_depth or url in links_content:
        return

    try:
        content = fetch_page_content(url)
        links_content[url] = content

        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        for link in soup.find_all('a', href=True):
            href = link['href']
            if urlparse(href).netloc == domain_name:
                full_url = urljoin(url, href)
                recursive_crawl(full_url, domain_name, links_content, max_depth, current_depth + 1)

    except Exception as e:
        links_content[url] = f"Error fetching page: {e}"


#Give customers the option to upload their informtion     
with st.sidebar:
    functionality = st.radio("Please provide information about yourself", ("Manual Description", "PDF Uploader", 'Website Url'))

#If customers want to write a description of themselves
if functionality == "Manual Description":
  with st.form("my_form"):
    description = st.text_input("Please Provide Information About Your Business")
    # Every form must have a submit button.
    submitted = st.form_submit_button("Submit")

    if submitted:
        biz_info=biz_info+str(description)+ "\n\n"

#If customers want to upload a pdf about themselves
elif functionality == "PDF Uploader":
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()

        try:
            pdf_reader = PdfReader(io.BytesIO(bytes_data))
            st.write(f"Number of pages in the PDF: {len(pdf_reader.pages)}")
            for page in pdf_reader.pages:
                biz_info=biz_info+ str(page.extract_text())+ "\n\n"
            # Add more processing here if needed
            submitted=True
        except Exception as e:
            st.error(f"Error reading PDF: {e}")

#If customers want to upload an url to their site
elif functionality == "Website Url":
    with st.form("webpage_form"):
        url = st.text_input("Enter the webpage URL")
        max_depth = st.number_input("Enter max depth for crawling (be cautious)", min_value=1, max_value=20, value=1)
        fetch_button = st.form_submit_button("Fetch Webpage and Subpages")

        if fetch_button and url:
            all_content = {}
            domain_name = urlparse(url).netloc
            recursive_crawl(url, domain_name, all_content, max_depth)

            if all_content:
                submitted=True
                st.write(f"Found content from {len(all_content)} pages in the domain.")
                for link, content in all_content.items():
                    st.subheader(link)
                    # Use the link itself as a unique key for the text area
                    #st.text_area("Content", content, height=150, key=link)
                    biz_info=biz_info+str(content)+ "\n\n"


if biz_info:
    #st.write(biz_info)


    #Splitting Documents into Chunks for embeddings and the store them in vector stores
    # chunksize and chunkoverlap are key parameters to ensure that things work
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=500)
    chunks = text_splitter.create_documents([biz_info])
    #st.write(chunks[0])
    st.write('\n\n')
    #st.write(chunks[1])
    #Store the chunks as embeddings within a vector store
    embeddings = OpenAIEmbeddings()
    vector_store = Chroma.from_documents(chunks, embeddings)


    # initialize OpenAI instance and set up a chain for Q&A from an LLM and a vector score
    llm = ChatOpenAI(model='gpt-3.5-turbo', temperature=0)
    retriever=vector_store.as_retriever()
    chain = RetrievalQA.from_chain_type(llm, retriever=retriever)


    question = "What is location of willoughbys?"
    st.write(question)
    st.write('\n\n')
    response = chain.run(question)
    st.write(textwrap.fill(response,75))
