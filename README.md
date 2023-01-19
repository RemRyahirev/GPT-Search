# Quest
 This is a web app that integrates GPT-3 with google searches.

# Dev run

1. obtain GPT 3 Api key
2. create app/.env file with "API_KEY=sk-...." content
3. run `docker compose up`

# Port

5000 and can't be changed for now

# Envs

* API_KEY - string. Key from GPT 3 Api, starts with 'sk-'.

Also looking for '.env' file into app/ dir for dev purpose. 

# API Doc

## GET /search

### params

* query - string. search query

### response

* query - string. requested query
* results - list of dicts. results of google search that passed to GPT
  * link - string
  * text - string

## GET /ask

### params

* query - string. a question to ask
* creativity - int from 0 to 4, a creativity level where 0 is 'Strictly Factual' and 4 is 'Very Creative'

### response

* query - string. requested query
* results - dict
  * answer - string. resulting answer from GPT
  * prompt - string. total question to GPT that provides the resulting answer
  * sources - list of dicts. results of google search that passed to GPT
    * link - string
    * text - string

# Known issues

* Sometimes error `'Connection to openaipublic.blob.core.windows.net timed out. (connect timeout=10)'` occurs due to tiktoken lib. On another launch everything seems ok.