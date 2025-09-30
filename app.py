# app.py (No changes needed, but ensuring routes are there)
import os
from flask import Flask, request, send_file, render_template, jsonify, url_for
from werkzeug.utils import secure_filename
from PIL import Image
from docx2pdf import convert as docx_to_pdf
from pdf2docx import Converter as pdf_to_docx

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


@app.route("/")
def home():
    return render_template("index.html")



@app.route("/convert", methods=["POST"])
def convert_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    target_format = request.form.get("format")

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    input_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(input_path)

    name, ext = os.path.splitext(filename)
    ext = ext.lower()

    output_filename = f"{name}.{target_format}"
    output_path = os.path.join(app.config["OUTPUT_FOLDER"], output_filename)

    try:
        # ---- IMAGE CONVERSION ----
        if ext in [".jpg", ".jpeg", ".png", ".webp"] and target_format in ["jpg", "jpeg", "png", "webp"]:
            img = Image.open(input_path)
            img = img.convert("RGB") if target_format in ["jpg", "jpeg"] else img
            img.save(output_path, target_format.upper())

        # ---- DOCX TO PDF ----
        elif ext == ".docx" and target_format == "pdf":
            docx_to_pdf(input_path, output_path)

        # ---- PDF TO DOCX ----
        elif ext == ".pdf" and target_format == "docx":
            cv = pdf_to_docx(input_path)
            cv.convert(output_path)
            cv.close()

        else:
            return jsonify({"error": "Unsupported conversion"}), 400

    except Exception as e:
        return jsonify({"error": f"Conversion failed: {str(e)}"}), 500

    download_url = url_for("download_file", filename=output_filename, _external=True)
    return jsonify({"download_url": download_url})


@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(app.config["OUTPUT_FOLDER"], filename)
    return send_file(file_path, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)