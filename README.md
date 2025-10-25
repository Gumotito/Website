# My Python Web App

This is a simple web application built using Flask. The application features a landing page with a button that, when clicked, displays additional text.

## Project Structure

```
my-python-web-app
├── app.py
├── static
│   └── style.css
├── templates
│   └── index.html
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup Instructions

1. **Clone the repository**:
   ```
   git clone <repository-url>
   cd my-python-web-app
   ```

2. **Create a virtual environment** (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install the required dependencies**:
   ```
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```
   python app.py
   ```

5. **Access the application**:
   Open your web browser and go to `http://127.0.0.1:5000` to view the landing page.

## Features

- A simple landing page with a button.
- Additional text displayed upon button click using JavaScript.

## License

This project is licensed under the MIT License.