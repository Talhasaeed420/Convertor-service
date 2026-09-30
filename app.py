import os
import sys
import uuid
import base64
import logging
import traceback
from flask import Flask, request, send_file, render_template, jsonify, url_for
from werkzeug.utils import secure_filename
from PIL import Image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# On Vercel / AWS Lambda, the root filesystem (/var/task) is strictly read-only.
# Only /tmp is writable.
IS_SERVERLESS = (
    os.environ.get("VERCEL") == "1"
    or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None
)

if IS_SERVERLESS:
    UPLOAD_FOLDER = "/tmp/uploads"
    OUTPUT_FOLDER = "/tmp/outputs"
else:
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")

# Safe directory creation with fallback to /tmp
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
except OSError:
    UPLOAD_FOLDER = "/tmp/uploads"
    OUTPUT_FOLDER = "/tmp/outputs"
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER

IMAGE_FORMAT_MAP = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "bmp": "BMP",
    "gif": "GIF",
    "tiff": "TIFF",
    "pdf": "PDF",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}


def convert_image(input_path, output_path, target_format):
    target_format = target_format.lower()
    pil_format = IMAGE_FORMAT_MAP.get(target_format, target_format.upper())

    with Image.open(input_path) as img:
        # Handle alpha channel when converting to formats that don't support transparency
        if pil_format in ("JPEG", "PDF"):
            if img.mode in ("RGBA", "LA", "P"):
                # Composite transparent images over a solid white background
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                mask = img.split()[-1] if "A" in img.getbands() else None
                bg.paste(img, mask=mask)
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")

        img.save(output_path, format=pil_format)


def convert_docx_to_pdf(input_path, output_path):
    try:
        import pymupdf
        doc = pymupdf.open(input_path)
        pdf_bytes = doc.convert_to_pdf()
        with pymupdf.open("pdf", pdf_bytes) as pdf_doc:
            pdf_doc.save(output_path)
        doc.close()
    except Exception as e:
        logger.warning(f"PyMuPDF docx conversion failed ({e}), trying docx2pdf...")
        try:
            from docx2pdf import convert as docx_to_pdf
            docx_to_pdf(input_path, output_path)
        except Exception as e2:
            raise RuntimeError(f"DOCX to PDF conversion failed: {e2}")

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("DOCX to PDF conversion produced an empty or missing file.")


def convert_pdf_to_docx(input_path, output_path):
    from pdf2docx import Converter
    cv = Converter(input_path)
    try:
        cv.convert(output_path)
    finally:
        cv.close()

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("PDF to DOCX conversion produced an empty or missing file.")


def convert_pdf_to_image(input_path, output_path, target_format):
    import pymupdf
    doc = pymupdf.open(input_path)
    if len(doc) == 0:
        raise RuntimeError("PDF contains no pages.")

    # Render first page at high quality
    page = doc[0]
    pix = page.get_pixmap(dpi=150)
    image_fmt = "jpeg" if target_format in ["jpg", "jpeg"] else target_format
    pix.save(output_path, output=image_fmt)
    doc.close()

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("PDF to Image conversion produced an empty or missing file.")


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    target_format = request.form.get("format", "").strip().lower()

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    original_filename = secure_filename(file.filename)
    if not original_filename:
        original_filename = "upload"

    name, ext = os.path.splitext(original_filename)
    ext = ext.lower()

    unique_id = uuid.uuid4().hex[:8]
    input_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{unique_id}_{original_filename}")
    file.save(input_path)

    output_filename = f"{name}_{unique_id}.{target_format}"
    output_path = os.path.join(app.config["OUTPUT_FOLDER"], output_filename)

    try:
        # ---- IMAGE CONVERSIONS ----
        if ext in IMAGE_EXTENSIONS and target_format in IMAGE_FORMAT_MAP:
            convert_image(input_path, output_path, target_format)

        # ---- DOCX TO PDF ----
        elif ext == ".docx" and target_format == "pdf":
            convert_docx_to_pdf(input_path, output_path)

        # ---- PDF TO DOCX ----
        elif ext == ".pdf" and target_format == "docx":
            convert_pdf_to_docx(input_path, output_path)

        # ---- PDF TO IMAGE ----
        elif ext == ".pdf" and target_format in ["jpg", "jpeg", "png", "webp"]:
            convert_pdf_to_image(input_path, output_path, target_format)

        else:
            return jsonify({"error": f"Unsupported conversion from {ext or 'unknown'} to {target_format}"}), 400

        # Read converted file for serverless-safe base64 delivery
        file_base64 = None
        if os.path.exists(output_path) and os.path.getsize(output_path) < 4 * 1024 * 1024:
            with open(output_path, "rb") as f:
                file_base64 = base64.b64encode(f.read()).decode("utf-8")

    except Exception as e:
        logger.error(f"Conversion error: {traceback.format_exc()}")
        return jsonify({"error": f"Conversion failed: {str(e)}"}), 500
    finally:
        # Clean up temporary uploaded file
        if os.path.exists(input_path):
            try:
                os.remove(input_path)
            except OSError:
                pass

    download_url = url_for("download_file", filename=output_filename, _external=True)
    return jsonify({
        "download_url": download_url,
        "filename": output_filename,
        "file_base64": file_base64,
    })


@app.route("/download/<filename>")
def download_file(filename):
    safe_filename = secure_filename(filename)
    file_path = os.path.join(app.config["OUTPUT_FOLDER"], safe_filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
