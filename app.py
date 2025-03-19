import sqlite3
from datetime import datetime, timedelta
import secrets
import sys
from flask import Flask, jsonify, request, render_template_string
from functools import wraps

# Adiciona o diretório atual ao sys.path (caso necessário)
sys.path.append(".")

# Caminhos dos bancos de dados
DATABASE_API = "filmes.db"
DATABASE_MANGAS = "mangas.db"

# Função para resetar a tabela de chaves API
def resetar_tabela_api_keys():
    conn = sqlite3.connect(DATABASE_API)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS api_keys")  # Remove a tabela se existir
    cursor.execute('''
        CREATE TABLE api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            ip TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL
        )
    ''')  # Cria a tabela novamente
    conn.commit()
    conn.close()

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

# Função para gerar uma nova chave API (verifica se já existe uma ativa para o IP)
def gerar_chave(ip):
    conn = get_db_connection_api()
    cursor = conn.cursor()

    # Verificar se o IP já possui uma chave ativa
    cursor.execute("SELECT * FROM api_keys WHERE ip = ? AND expires_at > ?", (ip, datetime.now()))
    chave_existente = cursor.fetchone()

    if chave_existente:
        conn.close()
        return None  # Retorna None se já existir uma chave válida

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

# Rota para gerar uma nova chave API
@app.route("/api/gerar_chave", methods=["GET"])
def criar_chave():
    ip = request.remote_addr
    nova_chave = gerar_chave(ip)
    if nova_chave:
        return jsonify({"chave": nova_chave, "expira_em": "24 horas"})
    else:
        return jsonify({"error": "Já existe uma chave ativa para este IP."}), 400

# Rota para listar todas as chaves de um IP
@app.route("/api/chaves", methods=["GET"])
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
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                    font-family: 'Poppins', sans-serif;
                }

                body {
                    background-color: #121212;
                    color: #fff;
                    line-height: 1.6;
                    padding: 20px;
                }

                header {
                    background-color: #1a1a1a;
                    padding: 20px;
                    border-radius: 10px;
                    margin-bottom: 20px;
                }

                header .logo h1 {
                    font-size: 2rem;
                    color: #ff2d55;
                    margin-bottom: 5px;
                }

                header .logo .tagline {
                    font-size: 1rem;
                    color: #aaa;
                }

                nav ul {
                    list-style: none;
                    display: flex;
                    gap: 20px;
                }

                nav ul li a {
                    color: #fff;
                    text-decoration: none;
                    font-size: 1.1rem;
                    transition: color 0.3s;
                }

                nav ul li a:hover {
                    color: #ff2d55;
                }

                .intro {
                    background-color: #1d1d1d;
                    padding: 40px;
                    border-radius: 10px;
                    text-align: center;
                    margin-bottom: 20px;
                }

                .intro h2 {
                    font-size: 2.5rem;
                    color: #ff2d55;
                    margin-bottom: 20px;
                }

                .intro p {
                    font-size: 1.1rem;
                    color: #ccc;
                    margin-bottom: 20px;
                }

                .intro .btn {
                    padding: 10px 20px;
                    background-color: #ff2d55;
                    color: #fff;
                    text-decoration: none;
                    font-weight: bold;
                    border-radius: 5px;
                    transition: background-color 0.3s;
                }

                .intro .btn:hover {
                    background-color: #e02447;
                }

                .documentacao {
                    background-color: #1d1d1d;
                    padding: 20px;
                    border-radius: 10px;
                }

                .documentacao h2 {
                    font-size: 2rem;
                    color: #ff2d55;
                    margin-bottom: 20px;
                }

                .endpoint {
                    background-color: #333;
                    padding: 20px;
                    border-radius: 10px;
                    margin-bottom: 20px;
                }

                .endpoint-title {
                    font-size: 1.5rem;
                    color: #ff2d55;
                    margin-bottom: 10px;
                }

                .endpoint-description p {
                    font-size: 1.1rem;
                    color: #ccc;
                    margin-bottom: 10px;
                }

                .endpoint-details p {
                    font-size: 1rem;
                    color: #fff;
                    margin-bottom: 5px;
                }

                .endpoint-details code {
                    background-color: #444;
                    color: #ff2d55;
                    padding: 2px 4px;
                    border-radius: 5px;
                }

                .note {
                    background-color: #222;
                    padding: 15px;
                    border-radius: 5px;
                    margin-top: 20px;
                }

                .note p {
                    font-size: 1rem;
                    color: #ccc;
                }

                footer {
                    background-color: #1a1a1a;
                    padding: 15px;
                    text-align: center;
                    border-radius: 10px;
                    margin-top: 20px;
                }

                footer p {
                    font-size: 0.9rem;
                    color: #aaa;
                }
            </style>
        </head>
        <body>
            <header>
                <div class="logo">
                    <h1>VaultMovies API</h1>
                    <p class="tagline">Sua fonte para filmes e gerenciamento de chaves API</p>
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

# Rota para gerenciar chaves
@app.route("/chaves", methods=["GET"])
def gerenciar_chaves():
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Gerenciar Chaves da API</title>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                    font-family: 'Poppins', sans-serif;
                }

                body {
                    background-color: #121212;
                    color: #fff;
                    line-height: 1.6;
                    padding: 20px;
                }

                .container {
                    max-width: 900px;
                    margin: 0 auto;
                }

                header {
                    text-align: center;
                    margin-bottom: 40px;
                }

                header h1 {
                    font-size: 2.5rem;
                    color: #e60000;
                }

                header .tagline {
                    font-size: 1rem;
                    color: #aaa;
                }

                .documentacao {
                    background-color: #1c1c1c;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }

                .documentacao h2 {
                    font-size: 2rem;
                    color: #e60000;
                    margin-bottom: 20px;
                }

                .endpoint {
                    background-color: #222;
                    padding: 20px;
                    margin-bottom: 30px;
                    border-radius: 8px;
                }

                .endpoint h3 {
                    font-size: 1.5rem;
                    color: #fff;
                    margin-bottom: 10px;
                }

                .endpoint p {
                    font-size: 1rem;
                    color: #ccc;
                    margin-bottom: 10px;
                }

                button {
                    padding: 10px 20px;
                    background-color: #e60000;
                    color: #fff;
                    font-size: 1.1rem;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    transition: background-color 0.3s ease;
                }

                button:hover {
                    background-color: #b30000;
                }

                ul {
                    list-style-type: none;
                    margin-top: 10px;
                }

                ul li {
                    font-size: 1rem;
                    color: #ccc;
                    margin-bottom: 5px;
                }

                .voltar-docs {
                    display: block;
                    text-align: center;
                    margin-top: 30px;
                    color: #e60000;
                    text-decoration: none;
                    font-size: 1rem;
                }

                .voltar-docs:hover {
                    text-decoration: underline;
                }

                footer {
                    background-color: #1c1c1c;
                    padding: 20px;
                    text-align: center;
                    font-size: 1rem;
                    border-top: 2px solid #e60000;
                    margin-top: 40px;
                }

                @media (max-width: 768px) {
                    .container {
                        padding: 15px;
                    }

                    header h1 {
                        font-size: 2rem;
                    }

                    .documentacao h2 {
                        font-size: 1.5rem;
                    }

                    .endpoint h3 {
                        font-size: 1.2rem;
                    }

                    button {
                        font-size: 1rem;
                    }

                    ul li {
                        font-size: 0.9rem;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <header>
                    <h1>VaultMovies API - Gerenciar Chaves</h1>
                    <p class="tagline">Gerencie suas chaves API para acessar a nossa base de filmes</p>
                </header>
                <section class="documentacao">
                    <h2>Documentação de Chaves API</h2>
                    <p>Para acessar os recursos da VaultMovies API, você precisará de uma chave API. Use os seguintes recursos:</p>

                    <div class="endpoint">
                        <h3>Gerar Nova Chave</h3>
                        <p>Gere uma nova chave API associada ao seu IP. Se uma chave ativa já existir, você receberá uma mensagem informando isso.</p>
                        <button onclick="gerarChave()">Gerar Chave</button>
                        <p id="chaveGerada"></p>
                    </div>

                    <div class="endpoint">
                        <h3>Chaves Existentes</h3>
                        <p>Veja todas as chaves API associadas ao seu IP e suas datas de expiração.</p>
                        <ul id="listaChaves"></ul>
                    </div>
                </section>

                <a href="/" class="voltar-docs">Voltar para a documentação</a>

                <footer>
                    <p>© 2025 VaultMovies API. Todos os direitos reservados.</p>
                </footer>
            </div>

            <script>
                function gerarChave() {
                    fetch('/api/gerar_chave')
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('chaveGerada').textContent = data.chave 
                                ? `Chave gerada: ${data.chave}`
                                : 'Já existe uma chave ativa para este IP.';
                        });
                }

                fetch('/api/chaves')
                    .then(response => response.json())
                    .then(data => {
                        const lista = document.getElementById('listaChaves');
                        lista.innerHTML = data.map(chave => `<li>${chave.key} - Expira: ${chave.expires_at}</li>`).join('');
                    });
            </script>
        </body>
        </html>
    ''')

# Resetar a tabela de chaves no início (remova essa linha em produção)
resetar_tabela_api_keys()

# Iniciar o servidor
if __name__ == "__main__":
    app.run(debug=True)
