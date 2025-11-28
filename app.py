import time
import os
import random
from flask import Flask, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from pymongo import MongoClient, WriteConcern
from faker import Faker

app = Flask(__name__)
fake = Faker('pt_BR')

# --- Configuração SQL (PostgreSQL) ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQL_URI', 'sqlite:///local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_size': 10, 'max_overflow': 20}
db = SQLAlchemy(app)

# Modelo SQL
class UserSQL(db.Model):
    __tablename__ = 'user_sql'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    cpf = db.Column(db.String(11), nullable=False)
    rg = db.Column(db.String(8), nullable=False)
    endereco = db.Column(db.String(100), nullable=False)
    metodo_pagamento = db.Column(db.String(20), nullable=False)

# --- Configuração NoSQL (MongoDB) ---
mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
# LUW SEGURA: j=True obriga o Mongo a confirmar escrita no disco
mongo_client = MongoClient(mongo_uri)
mongo_db = mongo_client['benchdb']
mongo_collection = mongo_db.get_collection('users', write_concern=WriteConcern(w=1, j=True))

with app.app_context():
    db.create_all()

# Gerador de Dados
def gerar_dados_fake(qtd):
    dados = []
    opcoes_pagamento = ['credito', 'debito', 'pix']
    for _ in range(qtd):
        cpf_raw = fake.cpf().replace('.', '').replace('-', '')
        rg_raw = str(random.randint(10000000, 99999999))
        item = {
            "nome": fake.name()[:50],
            "cpf": cpf_raw,
            "rg": rg_raw,
            "endereco": fake.address().replace('\n', ', ')[:100],
            "metodo_pagamento": random.choice(opcoes_pagamento)
        }
        dados.append(item)
    return dados

# --- ROTA PRINCIPAL (Menu) ---
@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Benchmark SQL vs NoSQL</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; max-width: 850px; margin: 30px auto; padding: 20px; background: #f4f6f8; }
            h1 { text-align: center; color: #2c3e50; }
            .card { background: white; padding: 25px; margin-bottom: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
            h2 { font-size: 1.2rem; color: #444; margin-top: 0; border-bottom: 2px solid #eee; padding-bottom: 10px; }
            p { color: #666; font-size: 0.9rem; }
            
            /* Estilo dos Botões */
            .btn { text-decoration: none; color: white; padding: 10px 20px; border-radius: 6px; display: inline-block; margin: 5px; font-weight: 600; transition: transform 0.1s; }
            .btn:active { transform: scale(0.98); }
            
            .blue { background-color: #3498db; } .blue:hover { background-color: #2980b9; }
            .green { background-color: #27ae60; } .green:hover { background-color: #219150; }
            .dark { background-color: #34495e; } .dark:hover { background-color: #2c3e50; }
            .red { background-color: #e74c3c; } .red:hover { background-color: #c0392b; }
            
            .operations-area { border-top: 5px solid #34495e; background-color: #eef2f5; }
        </style>
    </head>
    <body>
        <h1>Benchmark de LUW (Transações)</h1>
        
        <div class="card">
            <h2>1. Testar ESCRITA (Insert)</h2>
            <p>Insere dados com confirmação de disco (LUW Segura) em ambos.</p>
            <a href="/benchmark/write/100" class="btn blue">Inserir 100</a>
            <a href="/benchmark/write/1000" class="btn blue">Inserir 1.000</a>
            <a href="/benchmark/write/10000" class="btn blue">Inserir 10.000</a>
        </div>

        <div class="card">
            <h2>2. Testar LEITURA (Select)</h2>
            <p>Mede a velocidade de recuperação dos dados.</p>
            <a href="/benchmark/read/100" class="btn green">Ler 100</a>
            <a href="/benchmark/read/1000" class="btn green">Ler 1.000</a>
            <a href="/benchmark/read/10000" class="btn green">Ler 10.000</a>
        </div>

        <div class="card operations-area">
            <h2>3. Gerenciamento e Visualização</h2>
            <p>Ações globais sobre o banco de dados.</p>
            
            <a href="/ver_tudo" class="btn dark" target="_blank">📄 Ver JSON Completo</a>
            <a href="/limpar" class="btn red">🗑️ LIMPAR TODOS OS DADOS</a>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

# --- Rota de Benchmark: ESCRITA ---
@app.route('/benchmark/write/<int:qtd>')
def benchmark_write(qtd):
    payload = gerar_dados_fake(qtd)
    
    # LUW SQL
    start_sql = time.time()
    db.session.bulk_insert_mappings(UserSQL, payload)
    db.session.commit() 
    end_sql = time.time()
    
    # LUW NoSQL (com j=True configurado na conexão)
    start_nosql = time.time()
    mongo_collection.insert_many(payload)
    end_nosql = time.time()

    return jsonify({
        "operacao": "INSERT (LUW Segura)",
        "quantidade": qtd,
        "tempo_sql": round(end_sql - start_sql, 4),
        "tempo_nosql": round(end_nosql - start_nosql, 4),
        "vencedor": "NoSQL" if (end_nosql - start_nosql) < (end_sql - start_sql) else "SQL",
        "link_voltar": "/"
    })

# --- Rota de Benchmark: LEITURA ---
@app.route('/benchmark/read/<int:qtd>')
def benchmark_read(qtd):
    # Leitura SQL
    start_sql = time.time()
    stmt = db.select(UserSQL).limit(qtd)
    _ = db.session.execute(stmt).scalars().all()
    end_sql = time.time()
    
    # Leitura NoSQL
    start_nosql = time.time()
    _ = list(mongo_collection.find({}, {'_id': 0}).limit(qtd))
    end_nosql = time.time()

    return jsonify({
        "operacao": "SELECT (Read)",
        "quantidade_lida": qtd,
        "tempo_sql": round(end_sql - start_sql, 4),
        "tempo_nosql": round(end_nosql - start_nosql, 4),
        "vencedor": "NoSQL" if (end_nosql - start_nosql) < (end_sql - start_sql) else "SQL",
        "link_voltar": "/"
    })

# --- Rotas de Gerenciamento ---
@app.route('/ver_tudo')
def ver_tudo():
    total = mongo_collection.count_documents({})
    # Limitamos visualização para não travar navegador
    dados = list(mongo_collection.find({}, {'_id': 0}).limit(200))
    return jsonify({
        "info": "Exibindo amostra dos primeiros 200 registros",
        "total_registros_banco": total,
        "dados": dados
    })

@app.route('/limpar')
def limpar():
    db.session.query(UserSQL).delete()
    db.session.commit()
    mongo_collection.delete_many({})
    return jsonify({"status": "Todos os bancos foram limpos com sucesso.", "link_voltar": "/"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)