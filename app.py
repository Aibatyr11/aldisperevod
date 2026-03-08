from flask import Flask, render_template, request, jsonify
from google.cloud import translate_v2 as translate
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from docx import Document
import os
import traceback
import uuid

app = Flask(
    __name__,
    static_url_path="/aldisperevod/static",
    static_folder="static"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
GOOGLE_CREDENTIALS = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(BASE_DIR, "valid-ship-425513-q3-bd2c117e9b57.json")
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIALS

ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIALS
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

translate_client = translate.Client()


def get_file_extension(filename):
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower().strip()


def allowed_file(filename):
    ext = get_file_extension(filename)
    return ext in ALLOWED_EXTENSIONS


def build_safe_filename(original_filename):
    ext = get_file_extension(original_filename)

    safe_name = secure_filename(original_filename)
    if safe_name and "." in safe_name:
        return safe_name

    random_name = uuid.uuid4().hex
    if ext:
        return f"{random_name}.{ext}"
    return random_name


def extract_text_from_txt(filepath):
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def extract_text_from_pdf(filepath):
    reader = PdfReader(filepath)
    text_parts = []

    for i, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        except Exception as e:
            print(f"Ошибка чтения страницы PDF {i + 1}: {e}")

    return "\n".join(text_parts).strip()


def extract_text_from_docx(filepath):
    doc = Document(filepath)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs).strip()


def extract_text_by_extension(filepath, extension):
    extension = (extension or "").lower()

    if extension == "txt":
        return extract_text_from_txt(filepath)
    elif extension == "pdf":
        return extract_text_from_pdf(filepath)
    elif extension == "docx":
        return extract_text_from_docx(filepath)

    return ""


def split_text_into_chunks(text, max_chars=4000):
    text = text.strip()
    if not text:
        return []

    chunks = []
    current_chunk = ""

    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()

        if not paragraph:
            continue

        if len(paragraph) > max_chars:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""

            for i in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[i:i + max_chars])
            continue

        if len(current_chunk) + len(paragraph) + 1 <= max_chars:
            if current_chunk:
                current_chunk += "\n" + paragraph
            else:
                current_chunk = paragraph
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = paragraph

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def translate_large_text(text, target_language):
    chunks = split_text_into_chunks(text, max_chars=4000)
    translated_parts = []

    for chunk in chunks:
        result = translate_client.translate(chunk, target_language=target_language)

        if isinstance(result, list):
            for item in result:
                if "translatedText" in item:
                    translated_parts.append(item["translatedText"])
        elif isinstance(result, dict):
            if "translatedText" in result:
                translated_parts.append(result["translatedText"])

    return "\n".join(translated_parts).strip()


@app.route("/aldisperevod/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            text = request.form.get("text")
            target_language = request.form.get("target_language")

            if text:
                translated = translate_large_text(text, target_language)
                return jsonify({"translated_text": translated})

            if "file" in request.files:
                file = request.files["file"]

                if not file or not file.filename:
                    return jsonify({
                        "translated_text": "Файл не выбран."
                    }), 400

                original_filename = file.filename
                extension = get_file_extension(original_filename)

                if extension not in ALLOWED_EXTENSIONS:
                    return jsonify({
                        "translated_text": "Формат файла не поддерживается. Разрешены: txt, pdf, docx."
                    }), 400

                safe_filename = build_safe_filename(original_filename)
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_filename)
                file.save(filepath)

                try:
                    content = extract_text_by_extension(filepath, extension)

                    if not content.strip():
                        return jsonify({
                            "translated_text": "Не удалось извлечь текст из файла. Возможно, PDF является сканом или документ пустой."
                        })

                    translated = translate_large_text(content, target_language)
                    return jsonify({"translated_text": translated})

                finally:
                    if os.path.exists(filepath):
                        os.remove(filepath)

            return jsonify({
                "translated_text": "Файл не выбран или формат не поддерживается."
            }), 400

        except Exception as e:
            print("ОШИБКА ВО ВРЕМЯ ОБРАБОТКИ ЗАПРОСА:")
            print(str(e))
            traceback.print_exc()
            return jsonify({
                "translated_text": f"Ошибка сервера при обработке файла: {str(e)}"
            }), 500

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
