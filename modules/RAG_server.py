from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import base64
from werkzeug.utils import secure_filename
import shutil

# === Constants ===
BASE_DIR = os.path.join('C:', 'Data', 'RAG')
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), 'Data', 'Public')

# === App Setup ===
app = Flask(__name__, static_folder=FRONTEND_DIR)
CORS(app)

# === Ensure base directory exists ===
os.makedirs(BASE_DIR, exist_ok=True)

# === Routes ===

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)

@app.route('/api/files', methods=['POST'])
def list_files():
    try:
        rel_path = request.json.get('path', '')
        dir_path = os.path.join(BASE_DIR, rel_path)
        files = []
        for name in os.listdir(dir_path):
            full_path = os.path.join(dir_path, name)
            stats = os.stat(full_path)
            files.append({
                'name': name,
                'size': stats.st_size,
                'modified': int(stats.st_mtime * 1000),
                'isDirectory': os.path.isdir(full_path)
            })
        return jsonify(files)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/api/file', methods=['POST'])
def get_file():
    try:
        rel_path = request.json['path']
        file_path = os.path.join(BASE_DIR, rel_path)

        if os.path.isdir(file_path):
            return jsonify(success=False, message='Path is a directory'), 400

        ext = os.path.splitext(file_path)[1][1:].lower()
        is_binary = ext not in ['txt', 'html', 'css', 'js', 'json', 'md']

        if is_binary and ext in ['jpg', 'jpeg', 'png', 'gif']:
            with open(file_path, 'rb') as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
            return jsonify(content=encoded, isBinary=True)
        elif is_binary:
            return jsonify(content='', isBinary=True)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify(content=content, isBinary=False)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/api/create', methods=['POST'])
def create_file():
    try:
        file_path = os.path.join(BASE_DIR, request.json['path'])
        content = request.json.get('content', '')
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/api/create-folder', methods=['POST'])
def create_folder():
    try:
        dir_path = os.path.join(BASE_DIR, request.json['path'])
        os.makedirs(dir_path, exist_ok=True)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/api/save', methods=['POST'])
def save_file():
    try:
        file_path = os.path.join(BASE_DIR, request.json['path'])
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(request.json['content'])
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/api/delete', methods=['POST'])
def delete_item():
    try:
        file_path = os.path.join(BASE_DIR, request.json['path'])
        if os.path.exists(file_path):
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                os.remove(file_path)
            return jsonify(success=True)
        else:
            return jsonify(success=False, message='File not found'), 404
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/api/upload', methods=['POST'])
def upload_files():
    try:
        path = request.form.get('path', '')
        upload_path = os.path.join(BASE_DIR, path)
        os.makedirs(upload_path, exist_ok=True)
        for file in request.files.getlist('files'):
            filename = secure_filename(file.filename)
            file.save(os.path.join(upload_path, filename))
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/api/download', methods=['POST'])
def prepare_download():
    try:
        rel_path = request.json['path']
        full_path = os.path.join(BASE_DIR, rel_path)
        if os.path.exists(full_path):
            return jsonify(success=True, url=f'/download-file?path={rel_path}')
        else:
            return jsonify(success=False, message='File not found'), 404
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/download-file')
def download_file():
    try:
        rel_path = request.args.get('path')
        dir_path = os.path.dirname(rel_path)
        file_name = os.path.basename(rel_path)
        return send_from_directory(os.path.join(BASE_DIR, dir_path), file_name, as_attachment=True)
    except Exception as e:
        return str(e), 500

# === Start Server ===
def start_server():
    print(f"✅ Server running at: http://localhost:3000")
    print(f"📂 Serving frontend from: {FRONTEND_DIR}")
    print(f"🗃️  File operations base: {BASE_DIR}")
    app.run(port=3000, debug=True)

