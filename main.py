from flask import Flask, render_template, request, redirect
import praw
from textblob import TextBlob
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from prawcore.exceptions import NotFound

import config
from config import creds
from googleapiclient.discovery import build

app = Flask(__name__)

sheets_api = build('sheets', 'v4', credentials=creds)

reddit = praw.Reddit(
    client_id=config.REDDIT_CLIENT_ID,
    client_secret=config.REDDIT_SECRET_KEY,
    user_agent=config.REDDIT_USER_AGENT,
)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        search_term = request.form['search_term']
        search_sub = request.form['subreddit']

        subreddit = reddit.subreddit(search_sub)

        num_posts = 100
        posts = subreddit.search(search_term, limit=num_posts)

        data = []
        question_words = {'who', 'what', 'when', 'where', 'why', 'how'}

        for post in posts:
            analysis = TextBlob(post.title)
            pos_tags = analysis.tags
            first_word = pos_tags[0][0].lower()

            is_question = any(
                tag[1].startswith('W') for tag in pos_tags) or first_word in question_words or post.title.endswith('?')

            if not is_question:
                sentiment = 'positive' if analysis.sentiment.polarity > 0 else 'negative' if analysis.sentiment.polarity < 0 else 'neutral'
                data.append([post.title, sentiment])

        df = pd.DataFrame(data, columns=['Post', 'Sentiment'])

        spreadsheet = {
            'properties': {'title': f'Sentiment Analysis - {search_term} in r/UCLA'}
        }

        spreadsheet = sheets_api.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()

        sheet_id = spreadsheet.get('spreadsheetId')
        update_permissions(sheet_id)

        data_range = 'Sheet1!A1:B'
        body = {
            'range': data_range,
            'values': [['Comment', 'Sentiment']] + data
        }
        sheets_api.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=data_range,
            valueInputOption='RAW',
            body=body
        ).execute()

        return redirect(f'https://docs.google.com/spreadsheets/d/{sheet_id}')
    return render_template('index.html')


def update_permissions(file_id):
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        new_permission = {'type': 'anyone', 'role': 'reader'}
        result = drive_service.permissions().create(fileId=file_id, body=new_permission, fields='id').execute()
        print(f"Permission update result: {result}")
    except HttpError as error:
        print(f"An error occurred: {error}")
        file_id = None
    return file_id


if __name__ == '__main__':
    app.run(debug=True)
