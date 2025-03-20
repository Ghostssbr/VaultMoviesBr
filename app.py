from flask import Flask, jsonify, request, render_template_string
from functools import wraps
import sqlite3
from datetime import datetime, timedelta
import secrets
import sys

# Adiciona o diretório atual ao sys.path (caso necessário)
sys.path.append(".")

# Caminhos dos bancos de dados
DATABASE_API = "filmes.db"
DATABASE_MANGAS = "mangas.db"

# Função para conectar ao banco de dados de chaves API
def get_db_connection_api():
    conn = sqlite3.connect(DATABASE_API)
    conn.row_factory = sqlite3.Row
    return conn

# Função para conectar ao banco de dados de mangás
def get_db_connection_mangas():
    conn = sqlite3.connect(DATABASE_MANGAS)
    conn.row_factory = sqlite3.Row
    return conn

# Função para gerar uma nova chave API ou retornar a existente (verifica se já existe uma chave ativa para o IP)
def gerar_chave(ip):
    conn = get_db_connection_api()
    cursor = conn.cursor()

    # Verificar se o IP já possui uma chave ativa
    cursor.execute("SELECT * FROM api_keys WHERE ip = ? AND expires_at > ?", (ip, datetime.now()))
    chave_existente = cursor.fetchone()

    if chave_existente:
        conn.close()
        # Retorna a chave existente se estiver ativa
        return chave_existente['key']
    
    # Gerar nova chave e definir expiração para 24 horas
    chave = secrets.token_hex(16)
    expires_at = datetime.now() + timedelta(hours=24)

    cursor.execute("INSERT INTO api_keys (key, ip, expires_at) VALUES (?, ?, ?)", (chave, ip, expires_at))
    conn.commit()
    conn.close()

    return chave

# Função para verificar se uma chave API é válida
def verificar_chave(chave, ip):
    conn = get_db_connection_api()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_keys WHERE key = ? AND ip = ? AND expires_at > ?", (chave, ip, datetime.now()))
    chave_valida = cursor.fetchone()
    conn.close()
    return chave_valida is not None

# Iniciar a API Flask
app = Flask(__name__)

# Middleware para exigir chave de API
def requer_chave(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        chave = request.view_args.get('key')  # Obtém a chave corretamente da URL
        ip = request.remote_addr
        if not chave or not verificar_chave(chave, ip):
            return jsonify({"error": "Chave inválida, expirada ou IP incorreto"}), 401
        return f(*args, **kwargs)
    return decorator

# Rota para gerar uma nova chave API ou mostrar a chave existente
@app.route("/chaves", methods=["GET"])
def criar_chave():
    ip = request.remote_addr
    chave = gerar_chave(ip)
    if chave:
        return jsonify({"chave": chave, "expira_em": "24 horas"})
    else:
        return jsonify({"error": "Erro ao gerar chave."}), 400

# Rota para listar todas as chaves de um IP
@app.route("/chaves", methods=["GET"])
def listar_chaves():
    ip = request.remote_addr
    conn = get_db_connection_api()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_keys WHERE ip = ?", (ip,))
    chaves = cursor.fetchall()
    conn.close()
    return jsonify([dict(chave) for chave in chaves])

# Rota para listar filmes (requer chave API)
@app.route("/api/<key>/filmes", methods=["GET"])
@requer_chave
def listar_filmes(key):
    nome = request.args.get('q', '')
    id_filme = request.args.get('id', None)

    conn = get_db_connection_api()
    cursor = conn.cursor()

    if id_filme:
        cursor.execute("SELECT * FROM filmes WHERE id = ?", (id_filme,))
        filmes = cursor.fetchall()
    elif nome:
        cursor.execute("SELECT * FROM filmes WHERE title LIKE ?", ('%' + nome + '%',))
        filmes = cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM filmes")
        filmes = cursor.fetchall()

    conn.close()
    return jsonify([dict(filme) for filme in filmes])

# Rota para listar mangás (requer chave API)
@app.route("/api/<key>/mangas", methods=["GET"])
@requer_chave
def listar_mangas(key):
    conn = get_db_connection_mangas()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM mangas")
    mangas = cursor.fetchall()

    dados_mangas = []
    for manga in mangas:
        cursor.execute("SELECT * FROM chapters WHERE manga_id = ?", (manga['id'],))
        capitulos = cursor.fetchall()

        dados_capitulos = [
            {
                "id": capitulo['id'],
                "titulo": capitulo['title'],
                "link": capitulo['link'],
                "data_lancamento": capitulo['release_date'],
                "imagens": capitulo['images'].split(", ")
            } for capitulo in capitulos
        ]

        dados_mangas.append({
            "id": manga['id'],
            "titulo": manga['title'],
            "rating": manga['rating'],
            "ano": manga['year'],
            "capa": manga['cover'],
            "link": manga['link'],
            "generos": manga['genres'].split(", "),
            "sinopse": manga['synopsis'],
            "capitulos": dados_capitulos
        })

    conn.close()
    return jsonify(dados_mangas)

# Rota para a página de documentação
@app.route("/", methods=["GET"])
def documentacao():
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VaultMovies API</title>
        <style>
            /* Estilos gerais */
            body {
                font-family: 'Arial', sans-serif;
                margin: 0;
                padding: 0;
                background-color: #1e1e1e;
                color: #fff;
            }

            header {
                background-color: #333;
                color: #fff;
                padding: 20px 0;
                text-align: center;
            }

            header h1 {
                margin: 0;
                font-size: 2.5em;
                font-weight: bold;
            }

            header p {
                margin: 5px 0 0;
                font-size: 1.2em;
                color: #ccc;
            }

            nav ul {
                list-style: none;
                padding: 0;
                margin: 20px 0;
            }

            nav ul li {
                display: inline;
                margin-right: 20px;
            }

            nav ul li a {
                color: #fff;
                text-decoration: none;
                font-weight: bold;
            }

            .intro {
                text-align: center;
                margin: 50px 0;
                padding: 20px;
                background-color: #2c2c2c;
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            }

            .intro h2 {
                font-size: 2em;
                margin-bottom: 10px;
            }

            .intro p {
                font-size: 1.1em;
                color: #ccc;
            }

            .intro .btn {
                display: inline-block;
                margin-top: 20px;
                padding: 10px 20px;
                background-color: #f44336;
                color: #fff;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
            }

            .documentacao {
                padding: 20px;
                background-color: #2c2c2c;
                margin: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            }

            .endpoint {
                margin-bottom: 30px;
                padding: 20px;
                background-color: #424242;
                border-radius: 10px;
            }

            .endpoint-title {
                font-size: 1.8em;
                color: #f44336;
                margin-bottom: 10px;
            }

            .endpoint-description {
                font-size: 1.1em;
                color: #ccc;
            }

            .endpoint-details {
                margin-top: 15px;
                padding: 15px;
                background-color: #333;
                border-radius: 5px;
                font-family: monospace;
                font-size: 1.05em;
            }

            .endpoint-details code {
                background-color: #1e1e1e;
                padding: 5px;
                border-radius: 3px;
                color: #f44336;
            }

            .note {
                background-color: #ffeb3b;
                padding: 10px;
                border-radius: 5px;
                margin-top: 20px;
                color: #000;
            }

            footer {
                text-align: center;
                padding: 20px 0;
                background-color: #333;
                color: #fff;
                margin-top: 50px;
            }

            footer p {
                margin: 0;
                font-size: 0.9em;
            }
        </style>
    </head>
    <body>
        <header>
            <div class="logo">
                <h1>VaultMovies API</h1>
                <p>Sua fonte para filmes e gerenciamento de chaves API</p>
            </div>
            <nav>
                <ul>
                    <li><a href="#">Home</a></li>
                    <li><a href="#documentacao">Documentação</a></li>
                    <li><a href="#">Sobre</a></li>
                </ul>
            </nav>
        </header>

        <section class="intro">
            <h2>Bem-vindo à VaultMovies API</h2>
            <p>A API VaultMovies oferece acesso completo a filmes, gerenciamento de chaves API e muito mais. Explore os endpoints abaixo.</p>
            <a href="#documentacao" class="btn">Veja a Documentação</a>
        </section>

        <section id="documentacao" class="documentacao">
            <h2>Documentação da API</h2>
            
            <div class="endpoint">
                <h3 class="endpoint-title">Gerenciar Chaves API</h3>
                <div class="endpoint-description">
                    <p>Este endpoint permite que você gere, renove ou remova chaves API associadas ao seu IP.</p>
                </div>
                <div class="endpoint-details">
                    <p><strong>URL:</strong> <code>/chaves</code></p>
                    <p><strong>Método:</strong> <code>GET</code></p>
                    <p><strong>Parâmetros:</strong> Nenhum</p>
                    <p><strong>Resposta:</strong> Uma chave API gerada ou confirmação de remoção.</p>
                </div>
            </div>

            <div class="endpoint">
                <h3 class="endpoint-title">Listar Filmes</h3>
                <div class="endpoint-description">
                    <p>Este endpoint retorna uma lista de todos os filmes registrados no banco de dados.</p>
                </div>
                <div class="endpoint-details">
                    <p><strong>URL:</strong> <code>/api/&lt;key&gt;/filmes</code></p>
                    <p><strong>Método:</strong> <code>GET</code></p>
                    <p><strong>Parâmetros:</strong> <code>key</code> (Chave API)</p>
                    <p><strong>Resposta:</strong> Uma lista de filmes com suas informações básicas.</p>
                </div>
            </div>

            <div class="note">
                <p><strong>Nota:</strong> Para acessar os endpoints de filmes, você precisa de uma chave API válida, que pode ser gerada através do endpoint <code>/chaves</code>.</p>
            </div>
        </section>

        <footer>
            <p>&copy; 2025 VaultMovies. Todos os direitos reservados.</p>
        </footer>
    </body>
    </html>
    ''')

# Iniciar o servidor
if __name__ == "__main__":
    app.run(debug=True)
