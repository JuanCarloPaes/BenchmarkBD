# 🚀 Benchmark Híbrido: SQL vs NoSQL (Python/Flask)

Este projeto é uma aplicação **Python (Flask)** containerizada desenhada para realizar comparativos de performance (Benchmark) entre bancos de dados **Relacionais (PostgreSQL)** e **Não-Relacionais (MongoDB)**.

O diferencial deste projeto é a implementação de uma lógica de **LUW (Logical Unit of Work)** justa, onde ambas as tecnologias são configuradas para garantir a persistência em disco, permitindo uma comparação honesta de tempo de resposta.

## 📋 Funcionalidades

- **Ambiente "Plug-and-Play":** Instalação automática via Docker Compose.
- **Gerador de Dados Brasileiros:** Criação automática de CPFs, RGs e Endereços via biblioteca `Faker`.
- **Benchmark de Escrita (Insert):**
  - Compara `SQL Bulk Insert` vs `MongoDB InsertMany`.
  - Configuração de `Journaling` (j=True) no Mongo para igualar a durabilidade do SQL.
- **Benchmark de Leitura (Select):**
  - Testes de recuperação de 100, 1.000 e 10.000 registros.
- **Painel Visual:** Interface web simples para controlar os testes sem necessidade de linha de comando.
- **Visualização de Dados:** Rota para inspecionar o JSON gerado e salvo no banco.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3.9
- **Framework Web:** Flask
- **Banco Relacional:** PostgreSQL 13 (via SQLAlchemy)
- **Banco NoSQL:** MongoDB 5.0 (via PyMongo)
- **Infraestrutura:** Docker & Docker Compose

---

## 🚀 Como Rodar o Projeto

### Pré-requisitos
Tudo o que você precisa ter instalado na sua máquina é o **Docker** e o **Docker Compose**.

### Como usar:
docker compose up --build

Nota: Se você usa uma versão antiga do Docker, use :
"docker-compose up --build" 
(com hífen).

Acesse o Painel: Abra seu navegador e vá para o endereço gerado no terminal
