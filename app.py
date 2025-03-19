import os
from flask import Flask, jsonify, request, render_template_string

# Definindo o diretório base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route("/", methods=["GET"])
def documentacao():
    try:
        file_path = os.path.join(BASE_DIR, "index.html")
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return jsonify({"error": "Arquivo index.html não encontrado"}), 404

@app.route("/chaves", methods=["GET"])
def gerenciar_chaves():
    try:
        file_path = os.path.join(BASE_DIR, "gerenciar_chaves.html")
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return jsonify({"error": "Arquivo gerenciar_chaves.html não encontrado"}), 404