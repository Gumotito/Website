from flask import Flask, render_template, jsonify

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

response_index = 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/show-text')
def show_text():
    global response_index
    text = responses[response_index % len(responses)]
    response_index += 1
    return jsonify({'text': text})

if __name__ == '__main__':
    app.run(debug=True)