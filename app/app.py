import pandas as pd
from flask import Flask, request
from dotenv import load_dotenv
import openai
import requests
import bs4
import os
import json
import tiktoken
from openai.embeddings_utils import get_embedding, cosine_similarity

tokenizer = tiktoken.get_encoding("gpt2")

load_dotenv()

app = Flask(__name__)
creativity_levels = ['Strictly Factual', 'Factual', 'Neutral', 'Creative', 'Very Creative']


def google_search(search: str, search_depth: int):
    try:
        res = requests.get('https://google.com/search?q=' + search, timeout=5)
        res.raise_for_status() # Raise if a HTTPError occurred
    except:
        # TODO: log
        raise

    soup = bs4.BeautifulSoup(res.text, 'html.parser')

    link_elements = soup.select('a')
    links = [link.get('href').split('&sa=U&ved=')[0].replace('/url?q=', '')
            for link in link_elements
            if '/url?q=' in link.get('href') and
            'accounts.google.com' not in link.get('href') and
            'support.google.com' not in link.get('href')]
    links = list(set(links)) # Remove duplicates while maintaining the same order

    links_attempted = -1
    links_explored = 0
    google_results = pd.DataFrame(columns=['text', 'link', 'query'])
    while links_explored < search_depth or links_attempted == len(links):
        links_attempted += 1
        if not links:
            return
        # If this link does not work, go to the next one
        try:
            res = requests.get(links[links_attempted], timeout=10)
            res.raise_for_status()
        except:
            continue

        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        _link_text = list(set(soup.get_text(separator='\n').splitlines())) # Separate all text by lines and remove duplicates
        _useful_text = [s for s in _link_text if len(s) > 30] # Get only strings above 30 characters
        _links = [links[links_attempted] for i in range(len(_useful_text))]
        _query = [search for i in range(len(_useful_text))]
        _link_results = pd.DataFrame({'text': _useful_text, 'link': _links, 'query': _query})
        google_results = pd.concat([google_results, _link_results])
        links_explored += 1

    google_results['text_length'] = google_results['text'].str.len()
    largest_results = google_results.nlargest(50, 'text_length')
    largest_results = largest_results.drop_duplicates()
    largest_results['ada_search'] = largest_results['text'].apply(lambda x: get_embedding(x, engine='text-embedding-ada-002'))

    return largest_results


def find_top_similar_results(df: pd.DataFrame, query: str, n: int):
    if len(df.index) < n:
        n = len(df.index)
    embedding = get_embedding(query, engine="text-embedding-ada-002")
    df1 = df.copy()
    df1["similarities"] = df1["ada_search"].apply(lambda x: cosine_similarity(x, embedding))
    best_results = df1.sort_values("similarities", ascending=False).head(n)
    return best_results.drop(['similarities', 'ada_search'], axis=1).drop_duplicates(subset=['text'])


def gpt3_call(prompt: str, tokens: int, temperature: int=1, stop=None):
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=tokens,
        n=1,
        stop=stop,
        temperature=temperature,
        request_timeout=120
    )

    return response["choices"][0]["text"].replace('\n', '  \n')


def num_of_tokens(prompt: str):
    return len(tokenizer.encode(prompt))


# Load Assistant settings
script_path = os.path.abspath(__file__).replace('app.py', '')
folder_path = os.path.join(script_path, 'conversation_settings')
file_names = os.listdir(folder_path)
all_settings = []
for file_name in file_names:
    if file_name.endswith('.json'):
        with open(os.path.join(folder_path, file_name)) as f:
            data = json.load(f)
            all_settings.append(data)

settings = {setting['setting_name']: (setting['warn_assistant'], pd.DataFrame(setting['starting_conversation'])) for setting in all_settings}

# app.logger.error('Api key: %s', os.getenv('API_KEY'))
openai.api_key = os.getenv('API_KEY')


@app.route('/search')
def run_search():
    query = request.args.get('query', '')

    search_results = google_search(query, 3)

    similar_results = find_top_similar_results(search_results, query, 5)

    google_findings = similar_results['text'].to_list()
    links = similar_results['link'].to_list()

    resp = {'query': query, 'results': []}

    if len(query) > 0:
        for i,finding in enumerate(google_findings):
            resp['results'].append({'text': finding, 'link': links[i]})

    return resp


@app.route('/ask')
def conversation():
    query = request.args.get('query', '')
    creativity = int(request.args.get('creativity', '0'))

    search_results = google_search(query, 3)

    history = search_results.drop_duplicates(subset=['text'])
    warn_assistant, starting_conversation = settings[creativity_levels[creativity]]

    similar_google_results = find_top_similar_results(history, query, 5)
    similar_conversation = find_top_similar_results(starting_conversation, query, 3)

    prompt = "You are a friendly and helpful AI assistant. You don't have access to the internet beyond the google searches that the user provides.\n"
    if similar_google_results.empty:
        prompt += "The user did not make a google search to provide more information.\n"
    else:
        prompt += "The user provided you with google searches.\nYour findings are:" + \
                '\n'.join(similar_google_results['text'].to_list()) + "\n"

    prompt += 'These are the relevant entries from the conversation so far (in order of importance):\n' + \
        '\n'.join(similar_conversation['text'].to_list()) + '\nThis is the last message by the user:\nUser: ' + query + warn_assistant + '\nAssistant:'

    tokens = num_of_tokens(prompt)
    answer = gpt3_call(prompt, tokens=4000 - tokens, stop='User:')

    resp = {'query': query, 'result': {'answer': answer, 'sources': [], 'prompt': prompt}}
    for row in similar_google_results.iterrows():
        resp['result']['sources'].append({'text': row[1]['text'], 'link': row[1]['link']})

    return resp
