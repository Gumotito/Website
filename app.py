from flask import Flask, render_template, jsonify
import random

app = Flask(__name__)

responses = [
    'Yes',
    'Of course he is',
    'Affirmative',
    'Without a doubt',
    'Absolutely',
    'Indeed',
    'Definitely'
]

clicked_responses = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/show-text')
def show_text():
    global clicked_responses
    text = responses[len(clicked_responses) % len(responses)]
    clicked_responses.append(text)
    return jsonify({'text': text, 'all_responses': clicked_responses})

if __name__ == '__main__':
    app.run(debug=True)