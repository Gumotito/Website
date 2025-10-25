from flask import Flask, render_template, jsonify
import os

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

@app.route('/ask-agent/<question>')
def ask_agent(question):
    # Simple mock response without API
    agent_response = "Yes, Dorin is absolutely a chele!"
    return jsonify({'response': agent_response})

if __name__ == '__main__':
    app.run(debug=True)