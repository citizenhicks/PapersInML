import urllib.request as libreq
from dotenv import load_dotenv
from requests_oauthlib import OAuth1
import feedparser
import anthropic
import json
import requests
import time
import os

load_dotenv(override=True)
consumer_key = os.environ.get("API_KEY")
consumer_secret = os.environ.get("API_SECRET")
access_token = os.environ.get("ACCESS_TOKEN")
access_token_secret = os.environ.get("ACCESS_TOKEN_SECRET")

def connect_to_oauth(consumer_key, consumer_secret, access_token, access_token_secret):
    auth = OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)
    return auth

def get_prior_tweets(auth):
    url = f"https://api.twitter.com/2/users/{os.getenv('USER_ID')}/tweets"
    headers = {
    'Content-Type': 'application/json',
    }
    data = {
        'max_results': 5,
        'tweet.fields': 'in_reply_to_user_id, text'
    }
    response = requests.request("GET", url, headers=headers, data=data, auth=auth)
    return response

def filter_titles(priors, current_title):
    data = json.loads(priors)['data']
    result = any(
        current_title in ' '.join(t['text'][6:].split())
        for t in data 
        if t['text'].startswith("Title:")
    )
    return result

def get_arxiv_feed(priors):
    with libreq.urlopen('http://export.arxiv.org/api/query?search_query=cat:cs.ai&sortBy=submittedDate&sortOrder=descending&&max_results=5') as url:
        r = url.read()
    data = []
    feed = feedparser.parse(r)

    for entry in feed.entries:
        if entry.arxiv_primary_category['term'] in ['cs.LG', 'cs.AI', 'cs.CL'] and not filter_titles(priors, ' '.join(entry.title.split())):
            data.append(' '.join(entry.title.split()))
            data.append(entry.summary)
            data.append(entry.link)
            data.append(entry.published_parsed)
            return data

    return 42

def post_to_twitter(auth, message, data):
    url = "https://api.twitter.com/2/tweets"
    headers = {
    'Content-Type': 'application/json',
    }
    payload = json.dumps({"text": message.content[0].text})
    #payload = json.dumps({"text": "this is a test"})
    print("payload: ", payload)
    response = requests.request("POST", url, headers=headers, data=payload, auth=auth)
    print('first tweet: ', response.status_code, response.headers)
    if response.status_code == 201:
        time.sleep(5)
        reply_object = json.loads(response.text)
        reply = json.dumps({"text": 'Title: '+ data[0] + ' \n\nPublished: ' + time.strftime("%Y-%m-%d", data[3]) + '\n\nLink to paper: '+ data[2], "reply": {"in_reply_to_tweet_id": reply_object['data']['id']}})
        response = requests.request("POST", url, headers=headers, data=reply, auth=auth)
        print('reply tweet: ', response.status_code, response.headers)

def main():
    auth = connect_to_oauth(consumer_key, consumer_secret, access_token, access_token_secret)
    priors = get_prior_tweets(auth)
    if priors.status_code != 200:
        print('api error: ', priors.status_code)
        return
    data = get_arxiv_feed(priors.text)

    if data == 42:
        print('no new papers')
        return
    else:
        client = anthropic.Anthropic(api_key=os.getenv('CLAUDE_API'))
        prompt = f"""Summarize the given text in a short format maximum 280 characters. ONLY OUTPUT THE SUMMARY AND NOTHING ELSE:
        Text to summarize: {data}"""
        message = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=280,
            temperature=0.5,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        if message.content[0].text != None:
            post_to_twitter(auth, message, data)

if __name__ == '__main__':
    main()
