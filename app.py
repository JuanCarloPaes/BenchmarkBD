import time
import os
import random
from flask import Flask, render_template_string, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from pymongo import MongoClient, WriteConcern, UpdateOne
from faker import Faker

app = Flask(__name__)
fake = Faker('pt_BR')

# --- CONFIGURAÇÃO SQL (PostgreSQL) ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQL_URI', 'sqlite:///local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_size': 20, 'max_overflow': 40}
db = SQLAlchemy(app)

# --- CONFIGURAÇÃO NoSQL (MongoDB) ---
mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
mongo_client = MongoClient(mongo_uri)
mongo_db = mongo_client['benchdb']

# --- CONFIGURAÇÃO DE LUW (Unidade Lógica de Trabalho) ---
# O segredo da comparação justa:
# 1. SQL: O commit() aguarda o WAL (Write Ahead Log) ir para o disco.
# 2. NoSQL: WriteConcern(j=True) aguarda o Journal ir para o disco.
# Sem isso, o Mongo escreveria na RAM e venceria sempre (injustamente).
mongo_users = mongo_db.get_collection('users', write_concern=WriteConcern(w=1, j=True))
mongo_products = mongo_db.get_collection('products', write_concern=WriteConcern(w=1, j=True))

# --- MODELOS SQL ---
class UserSQL(db.Model):
    __tablename__ = 'user_sql'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50))
    cpf = db.Column(db.String(11))
    rg = db.Column(db.String(8))
    endereco = db.Column(db.String(100))
    metodo_pagamento = db.Column(db.String(20))

class ProductSQL(db.Model):
    __tablename__ = 'product_sql'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    descricao = db.Column(db.String(200))
    preco = db.Column(db.Float)
    estoque = db.Column(db.Integer)

# --- INICIALIZAÇÃO DO BANCO (Produtos) ---
def init_db():
    with app.app_context():
        db.create_all()
        
        # Garante que existem exatamente 1000 produtos na loja
        qtd_atual = ProductSQL.query.count()
        if qtd_atual != 1000:
            print("--- Regenerando Inventário (1000 itens)... ---")
            ProductSQL.query.delete()
            mongo_products.delete_many({})
            db.session.commit()
            
            produtos_sql = []
            produtos_mongo = []
            
            tipos = ['TV', 'Smartphone', 'Notebook', 'Geladeira', 'Sofá', 'Mesa', 'Cadeira', 'Liquidificador', 'Fritadeira', 'Console']
            marcas = ['Sony', 'Samsung', 'LG', 'Dell', 'Brastemp', 'Nike', 'Adidas', 'Philips', 'Electrolux', 'Apple']
            
            for i in range(1, 1001):
                nome_prod = f"{random.choice(tipos)} {random.choice(marcas)} {random.randint(100,900)}"
                item = {
                    "nome": nome_prod,
                    "descricao": fake.sentence(nb_words=6),
                    "preco": round(random.uniform(50.0, 5000.0), 2),
                    "estoque": random.randint(100, 10000) # Estoque alto para aguentar testes
                }
                
                # SQL
                p_sql = ProductSQL(id=i, **item)
                produtos_sql.append(p_sql)
                
                # Mongo (Forçamos _id igual ao ID do SQL para paridade no update)
                item_mongo = item.copy()
                item_mongo['_id'] = i
                produtos_mongo.append(item_mongo)

            db.session.bulk_save_objects(produtos_sql)
            db.session.commit()
            mongo_products.insert_many(produtos_mongo)
            print("--- Inventário Pronto ---")

init_db()

# --- HELPER: Gerador de Users ---
def gerar_users(qtd):
    dados = []
    opcoes = ['credito', 'debito', 'pix']
    for _ in range(qtd):
        dados.append({
            "nome": fake.name()[:50],
            "cpf": fake.cpf().replace('.', '').replace('-', ''),
            "rg": str(random.randint(10000000, 99999999)),
            "endereco": fake.address().replace('\n', ', ')[:100],
            "metodo_pagamento": random.choice(opcoes)
        })
    return dados

# --- UI (CSS & HTML Helpers) ---
STYLE = """
<style>
    body { font-family: 'Segoe UI', sans-serif; max-width: 1000px; margin: 20px auto; padding: 20px; background: #f0f2f5; color: #1c1e21; }
    h1 { text-align: center; color: #1a202c; margin-bottom: 30px; }
    .card { background: white; padding: 20px; margin-bottom: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    h2 { font-size: 1.1rem; color: #4a5568; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; margin-top: 0; }
    p { color: #718096; font-size: 0.9rem; margin-bottom: 15px; }
    
    .btn-group { display: flex; gap: 10px; flex-wrap: wrap; }
    .btn { text-decoration: none; color: white; padding: 8px 16px; border-radius: 6px; font-weight: 600; font-size: 0.9rem; transition: all 0.2s; border: none; cursor: pointer; display: inline-flex; align-items: center; justify-content: center;}
    .btn:hover:not(.disabled) { filter: brightness(90%); transform: translateY(-1px); }
    .btn:active:not(.disabled) { transform: translateY(0); }
    
    .blue { background-color: #3182ce; }
    .green { background-color: #38a169; }
    .purple { background-color: #805ad5; }
    .orange { background-color: #dd6b20; }
    .red { background-color: #e53e3e; }
    .gray { background-color: #718096; }
    .dark { background-color: #2d3748; }
    
    .disabled { background-color: #cbd5e0; color: #a0aec0; cursor: not-allowed; pointer-events: none; }
    
    /* Resultados */
    .res-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
    .res-box { padding: 20px; border-radius: 8px; text-align: center; position: relative; }
    .sql-bg { background: #ebf8ff; border: 1px solid #bee3f8; }
    .nosql-bg { background: #f0fff4; border: 1px solid #c6f6d5; }
    .res-time { font-size: 2.5rem; font-weight: 800; color: #2d3748; }
    .res-win { color: #38a169; font-weight: bold; margin-top: 10px; font-size: 1.2rem; }
    
    .tech-card { background: #fffaf0; border-left: 4px solid #ed8936; padding: 15px; margin-top: 20px; }
    .tech-title { font-weight: bold; color: #c05621; display: block; margin-bottom: 5px; }
</style>
"""

# --- ROTA PRINCIPAL (DASHBOARD) ---
@app.route('/')
def index():
    # Contagem para habilitar/desabilitar botões
    count_users = mongo_users.count_documents({})
    count_prods = mongo_products.count_documents({})
    
    # Lógica de bloqueio de botões
    def state(req):
        return "" if count_users >= req else "disabled"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Benchmark System</title>{STYLE}</head>
    <body>
        <h1>📊 Benchmark: Relacional vs Não-Relacional</h1>
        
        <div style="display:flex; gap:20px; margin-bottom:20px; justify-content:center;">
            <div class="card" style="margin:0; text-align:center; min-width:150px;">
                <span style="display:block; font-size:0.8rem; color:#718096;">CLIENTES</span>
                <strong style="font-size:1.5rem; color:#3182ce;">{count_users}</strong>
            </div>
            <div class="card" style="margin:0; text-align:center; min-width:150px;">
                <span style="display:block; font-size:0.8rem; color:#718096;">PRODUTOS</span>
                <strong style="font-size:1.5rem; color:#38a169;">{count_prods}</strong>
            </div>
        </div>

        <div class="card">
            <h2>1. Inserção de Clientes (WRITE)</h2>
            <p>Insere novos registros no banco. Testa a velocidade de escrita em disco (Commit vs Journal).</p>
            <div class="btn-group">
                <a href="/bench/insert/100" class="btn blue">Inserir 100</a>
                <a href="/bench/insert/1000" class="btn blue">Inserir 1.000</a>
                <a href="/bench/insert/10000" class="btn blue">Inserir 10.000</a>
            </div>
        </div>

        <div class="card">
            <h2>2. Leitura de Clientes (READ)</h2>
            <p>Busca e serializa dados dos clientes. Requer que os clientes existam.</p>
            <div class="btn-group">
                <a href="/bench/read_users/100" class="btn green {state(100)}">Ler 100</a>
                <a href="/bench/read_users/1000" class="btn green {state(1000)}">Ler 1.000</a>
                <a href="/bench/read_users/10000" class="btn green {state(10000)}">Ler 10.000</a>
            </div>
        </div>

        <div class="card">
            <h2>3. Simulação de Compras (UPDATE)</h2>
            <p>Escolhe N clientes aleatórios e realiza uma compra para cada, abatendo do estoque. Testa concorrência e atualização atômica.</p>
            <div class="btn-group">
                <a href="/bench/buy/100" class="btn orange {state(100)}">Simular 100 Compras</a>
                <a href="/bench/buy/1000" class="btn orange {state(1000)}">Simular 1.000 Compras</a>
                <a href="/bench/buy/10000" class="btn orange {state(10000)}">Simular 10.000 Compras</a>
            </div>
        </div>
        
        <div class="card">
            <h2>4. Inventário e Dados</h2>
            <p>Visualização e limpeza dos bancos de dados.</p>
            <div class="btn-group">
                <a href="/bench/read_inventory" class="btn purple">📦 Benchmark: Ler Inventário Completo</a>
                <a href="/view/users" class="btn dark" target="_blank">📄 Ver JSON Clientes</a>
                <a href="/view/products" class="btn dark" target="_blank">📄 Ver JSON Produtos</a>
                <a href="/limpar" class="btn red" onclick="return confirm('Tem certeza?')">🗑️ Limpar Clientes</a>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

# --- FUNÇÃO DE RENDERIZAÇÃO DE RESULTADOS ---
def render_benchmark(title, qtd, sql_time, nosql_time, tech_explanation):
    winner = "NoSQL (MongoDB)" if nosql_time < sql_time else "SQL (PostgreSQL)"
    diff = abs(sql_time - nosql_time)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Resultado: {title}</title>{STYLE}</head>
    <body>
        <h1>Resultado: {title}</h1>
        <p style="text-align:center;">Operação realizada em <strong>{qtd}</strong> registros.</p>
        
        <div class="card">
            <div class="res-grid">
                <div class="res-box sql-bg">
                    <h3>SQL (PostgreSQL)</h3>
                    <div class="res-time">{sql_time:.4f}s</div>
                    <small>Relacional / ACID</small>
                </div>
                <div class="res-box nosql-bg">
                    <h3>NoSQL (MongoDB)</h3>
                    <div class="res-time">{nosql_time:.4f}s</div>
                    <small>Documento / Journaled</small>
                </div>
            </div>
            <div style="text-align:center; margin-top:30px;">
                🏆 Vencedor: <strong style="color:#27ae60; font-size:1.4rem;">{winner}</strong>
                <br><span style="color:#718096; font-size:0.9rem;">Diferença: {diff:.4f}s</span>
            </div>
        </div>

        <div class="card tech-card">
            <span class="tech-title">💡 Análise Técnica & Garantia de Avaliação Justa (LUW)</span>
            {tech_explanation}
        </div>

        <div style="text-align:center;">
            <a href="/" class="btn gray">⬅ Voltar ao Painel</a>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

# --- 1. INSERT ---
@app.route('/bench/insert/<int:qtd>')
def bench_insert(qtd):
    data = gerar_users(qtd)
    
    # SQL
    s = time.time()
    db.session.bulk_insert_mappings(UserSQL, data)
    db.session.commit() # Wait for Disk
    sql_time = time.time() - s
    
    # NoSQL
    s = time.time()
    mongo_users.insert_many(data) # Wait for Disk (j=True configured)
    nosql_time = time.time() - s
    
    explain = """
    <p><strong>Operação:</strong> Inserção em massa (Bulk Insert).</p>
    <ul>
        <li><strong>PostgreSQL:</strong> Utiliza <code>bulk_insert_mappings</code> seguido de <code>COMMIT</code>. O tempo medido inclui a gravação no WAL (Write Ahead Log) em disco.</li>
        <li><strong>MongoDB:</strong> Utiliza <code>insert_many</code> com a configuração <code>j=True</code> (Journal=True). O tempo medido inclui a confirmação de que os dados foram escritos fisicamente no journal do disco.</li>
    </ul>
    <p><em>Isso garante que ambos estão persistindo dados de verdade, não apenas salvando em cache (RAM).</em></p>
    """
    return render_benchmark("Inserção de Clientes", qtd, sql_time, nosql_time, explain)

# --- 2. READ USERS ---
@app.route('/bench/read_users/<int:qtd>')
def bench_read_users(qtd):
    # SQL
    s = time.time()
    res_sql = db.session.execute(db.select(UserSQL).limit(qtd)).scalars().all()
    sql_time = time.time() - s
    
    # NoSQL
    s = time.time()
    res_nosql = list(mongo_users.find({}, {'_id': 0}).limit(qtd))
    nosql_time = time.time() - s
    
    explain = """
    <p><strong>Operação:</strong> Leitura e Hidratação de Objetos.</p>
    <ul>
        <li><strong>PostgreSQL:</strong> <code>SELECT</code> + Custo do ORM converter linhas da tabela em objetos Python.</li>
        <li><strong>MongoDB:</strong> <code>find()</code> + Custo do driver converter BSON (binário) para Dicionários Python.</li>
    </ul>
    """
    return render_benchmark("Leitura de Clientes", qtd, sql_time, nosql_time, explain)

# --- 3. PURCHASE (UPDATE) ---
@app.route('/bench/buy/<int:qtd>')
def bench_buy(qtd):
    # Preparação: Selecionar N usuários aleatórios
    all_users_ids = [u.id for u in db.session.query(UserSQL.id).limit(qtd * 2).all()]
    if len(all_users_ids) < qtd:
        return "Erro: Usuários insuficientes. Insira mais clientes primeiro.", 400
        
    # Gera as tuplas de compra (prod_id, amount)
    compras = [(random.randint(1, 1000), random.randint(1, 3)) for _ in range(qtd)]
    
    # --- SQL BENCHMARK (Batch Update) ---
    s = time.time()
    
    # Prepara lista de parâmetros para envio único
    params = [{'a': amount, 'p': prod_id} for prod_id, amount in compras]
    
    # O SQLAlchemy detecta a lista de params e faz o "executemany" otimizado
    stmt = text("UPDATE product_sql SET estoque = estoque - :a WHERE id = :p")
    db.session.connection().execute(stmt, params)
    
    db.session.commit()
    sql_time = time.time() - s
    
    # --- NoSQL BENCHMARK (Bulk Write) ---
    s = time.time()
    ops = []
    for prod_id, amount in compras:
        ops.append(UpdateOne({'_id': prod_id}, {'$inc': {'estoque': -amount}}))
    
    if ops:
        mongo_products.bulk_write(ops) # j=True (WriteConcern configurado na conexão)
    nosql_time = time.time() - s
    
    explain = """
    <p><strong>Operação:</strong> Atualização de Estoque em Lote.</p>
    <ul>
        <li><strong>Cenário:</strong> {qtd} atualizações de estoque enviadas ao banco.</li>
        <li><strong>PostgreSQL:</strong> Utiliza <code>executemany</code>. O driver envia todas as instruções em um único pacote de rede, e o banco processa todas na mesma transação.</li>
        <li><strong>MongoDB:</strong> Utiliza <code>bulk_write</code>. Envia todas as operações <code>$inc</code> em um único comando.</li>
    </ul>
    <p><em>Ambos eliminam a latência de rede e testam a velocidade da engine de escrita.</em></p>
    """.format(qtd=qtd)
    
    return render_benchmark("Simulação de Compras", qtd, sql_time, nosql_time, explain)

# --- 4. READ INVENTORY ---
@app.route('/bench/read_inventory')
def bench_inventory():
    qtd = 1000
    
    s = time.time()
    _ = db.session.execute(db.select(ProductSQL)).scalars().all()
    sql_time = time.time() - s
    
    s = time.time()
    _ = list(mongo_products.find({}, {'_id': 0}))
    nosql_time = time.time() - s
    
    return render_benchmark("Leitura de Inventário (1000 itens)", qtd, sql_time, nosql_time, 
                            "<p>Leitura completa da tabela/coleção de produtos.</p>")

# --- ROTAS DE UTILIDADE ---
@app.route('/view/users')
def view_users():
    return jsonify(list(mongo_users.find({}, {'_id': 0}).limit(100)))

@app.route('/view/products')
def view_products():
    return jsonify(list(mongo_products.find({}, {'_id': 0})))

@app.route('/limpar')
def limpar():
    db.session.query(UserSQL).delete()
    db.session.commit()
    mongo_users.delete_many({})
    
    # Reseta estoque (não deleta, recria valores iniciais)
    init_db() 
    
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)