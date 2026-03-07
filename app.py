from flask import Flask, render_template, request, jsonify
from google.cloud import translate_v2 as translate
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

# Configure this with your Google Cloud credentials
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', '/home/aldisai/mysite/uploads')
app.config['GOOGLE_APPLICATION_CREDENTIALS'] = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '/home/aldisai/mysite/valid-ship-425513-q3-bd2c117e9b57.json')


# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

translate_client = translate.Client()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    print("Route accessed")
    if request.method == 'POST':
        text = request.form.get('text')
        target_language = request.form.get('target_language')

        if text:
            result = translate_client.translate(text, target_language=target_language)
            return jsonify({'translated_text': result['translatedText']})

        if 'file' in request.files:
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                with open(filepath, 'r') as f:
                    content = f.read()

                result = translate_client.translate(content, target_language=target_language)
                os.remove(filepath)  # Remove the file after translation

                return jsonify({'translated_text': result['translatedText']})
    print("Rendering template")
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)

