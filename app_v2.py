


from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from datetime import datetime, timedelta
import mysql.connector
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import os
import concurrent.futures
from functools import partial
from flask_cors import CORS
import tempfile
from dotenv import load_dotenv
import json
from datetime import datetime
import pandas as pd
from io import BytesIO
from functools import wraps
import requests
import logging
import numpy as np
from scipy import stats
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import request, render_template
from sqlalchemy import create_engine, text, bindparam
import traceback
import concurrent.futures
from collections import defaultdict
from mysql.connector import Error, pooling
from dateutil.relativedelta import relativedelta
from werkzeug.utils import secure_filename
import math
# Carrega variáveis do arquivo .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')


CORS(app)  

db_config = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

# Configura a chave da API do Groq
os.environ["GROQ_API_KEY"] = os.getenv('GROQ_API_KEY')

# Configurar o modelo Grok via API do Groq
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError(
        "GROQ_API_KEY não está configurada. Configure a variável de ambiente.")

# Usando o modelo Grok via Groq
llm = ChatGroq(model="llama3-70b-8192", api_key=groq_api_key)

# Definir o prompt para gerar perguntas no formato JSON
prompt = ChatPromptTemplate.from_template(
    "Você é um especialista em entrevistas de emprego. "
    "Gere exatamente 10 perguntas para um candidato à vaga de {titulo_vaga} com base nos requisitos: {requisitos}. "
    "O nível de senioridade da vaga é {senioridade}, então as perguntas devem ser adequadas para esse nível (Júnior: perguntas mais básicas; Pleno: perguntas intermediárias com foco prático; Sênior: perguntas avançadas com foco em arquitetura e liderança). "
    "Cada pergunta deve ser um objeto JSON com os seguintes campos: "
    "- 'pergunta': uma string com a pergunta (máximo 200 caracteres). "
    "- 'alternativas': uma lista com exatamente 3 opções no formato ['a) texto', 'b) texto', 'c) texto'], onde cada texto tem no máximo 100 caracteres. "
    "- 'correta': a letra da alternativa correta, que deve ser 'a', 'b' ou 'c'. "
    "As perguntas devem abordar diretamente os requisitos da vaga e refletir o nível de senioridade. "
    "Retorne as perguntas como uma lista de objetos JSON, no seguinte formato: "
    "["
    "{"
    "\"pergunta\": \"Qual é a sua experiência com Python?\", "
    "\"alternativas\": [\"a) Nenhuma\", \"b) 1-2 anos\", \"c) Mais de 2 anos\"], "
    "\"correta\": \"b\""
    "}, "
    "{"
    "\"pergunta\": \"Você tem conhecimento em Flask?\", "
    "\"alternativas\": [\"a) Sim\", \"b) Não\", \"c) Parcialmente\"], "
    "\"correta\": \"a\""
    "}"
    "]"
)
# Configurar o parser para garantir que a saída seja JSON
parser = JsonOutputParser()
# Criar a chain
perguntas_chain = LLMChain(llm=llm, prompt=prompt, output_parser=parser)

# Criar um prompt para gerar sugestões
prompt_template = PromptTemplate(
    input_variables=["titulo"],
    template=""" 
    Com base no título da vaga '{titulo}', gere sugestões para os seguintes campos de uma vaga de emprego:

    - Benefícios: Liste 3-5 benefícios comuns para essa vaga em formato de lista (ex.: "Vale-refeição, Plano de saúde, Trabalho remoto").
    - Descrição da Vaga: Escreva uma descrição clara e detalhada das responsabilidades e expectativas para a vaga, com 2-3 frases.
    - Requisitos: Liste 5-7 requisitos necessários para a vaga em formato de lista (ex.: "Python, 2 anos de experiência, Boa comunicação").

    Retorne as sugestões no formato:
    Benefícios: [lista de benefícios]
    Descrição: [descrição da vaga]
    Requisitos: [lista de requisitos]

    Certifique-se de que as sugestões sejam concisas e relevantes para o título da vaga fornecido.
    """
)

# Criar uma cadeia para processar o prompt com o Grok (via Groq)
suggestion_chain = LLMChain(llm=llm, prompt=prompt_template)

# Função para conectar ao banco

def get_db_connection():
    return mysql.connector.connect(**db_config)

# # Decorador para proteger rotas


# Decorador para verificar se o usuário está logado
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        print(f"Verificando sessão: {session}")
        if 'user' not in session:
            print("Usuário não autenticado. Redirecionando para login.")
            return jsonify({'success': False, 'message': 'Usuário não autenticado', 'redirect': url_for('login_page')}), 401
        print(f"Usuário autenticado: {session['user']}")
        return f(*args, **kwargs)
    return wrap



def permission_required(*perms):
    """
    Decorador que verifica se o usuário tem todas as permissões necessárias.

    Exemplo de uso:
    @permission_required(('modulo1', 'permissao1'), ('modulo2', 'permissao2'))
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                return jsonify({'success': False, 'message': 'Usuário não autenticado', 'redirect': url_for('login_page')}), 401

            matricula = session['user']['matricula']

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                for modulo, permissao in perms:
                    cursor.execute(
                        "SELECT 1 FROM permissoes WHERE matricula = %s AND modulo = %s AND permissao = %s",
                        (matricula, modulo, permissao)
                    )
                    has_permission = cursor.fetchone() is not None
                    if not has_permission:
                        print(
                            f"Usuário {matricula} NÃO tem permissão: {modulo}:{permissao}")
                        return jsonify({
                            'success': False,
                            'message': f'Sem permissão: {modulo}:{permissao}',
                            'redirect': url_for('pagina_principal')
                        }), 403

            finally:
                cursor.close()
                conn.close()

            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Rota de login (GET)
@app.route('/login', methods=['GET'])
def login_page():
    print(f"Verificando sessão na rota /login (GET): {session}")
    if 'user' in session:
        print("Usuário já autenticado. Redirecionando para index.")
        return jsonify({'success': True, 'redirect': url_for('pagina_principal')})
    print("Renderizando página de login.")
    return render_template('login.html')

# Rota de login (POST)


@app.route('/login', methods=['POST'])
def login():
    print("Recebendo requisição POST para /login")
    data = request.get_json()
    print(f"Dados recebidos: {data}")
    matricula = data.get('matricula')
    senha = data.get('senha')
    device_type = data.get('deviceType')

    if not matricula or not senha:
        print("Matrícula ou senha não fornecidos.")
        return jsonify({'success': False, 'message': 'Matrícula e senha são obrigatórios'}), 400

    if not device_type:
        print("deviceType não fornecido, assumindo 'desktop' como padrão.")
        device_type = 'desktop'

    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        print(f"Buscando usuário com matrícula: {matricula}")
        cur.execute('SELECT * FROM usuarios WHERE matricula = %s', (matricula,))
        user = cur.fetchone()
        print(f"Usuário encontrado: {user}")
        if not user:
            print(f"Usuário com matrícula {matricula} não encontrado.")
            return jsonify({'success': False, 'message': 'Matrícula ou senha inválidos'}), 401

        stored_password = user['senha']
        print(f"Senha armazenada: {stored_password}")
        print(f"Verificando senha para matrícula {matricula}")
        if senha == stored_password:
            # Verificar se a matrícula tem pelo menos uma permissão
            cur.execute(
                "SELECT 1 FROM permissoes WHERE matricula = %s LIMIT 1",
                (matricula,)
            )
            has_any_permission = cur.fetchone() is not None

            if not has_any_permission:
                print(f"Usuário {matricula} não tem permissões.")
                return jsonify({'success': False, 'message': 'Matrícula sem permissões registradas'}), 403

            print(f"Login bem-sucedido para matrícula {matricula}.")
            session['user'] = {
                'matricula': user['matricula'],
                'nome': user['nome'],
                'device_type': device_type
            }
            print(f"Sessão atualizada: {session}")
            redirect_url = url_for('pagina_principal') if device_type.lower(
            ) == 'desktop' else url_for('pda_principal')
            print(f"Redirecionando para: {redirect_url}")
            return jsonify({'success': True, 'redirect': redirect_url})
        else:
            print(f"Senha incorreta para matrícula {matricula}.")
            return jsonify({'success': False, 'message': 'Matrícula ou senha inválidos'}), 401
    except mysql.connector.Error as db_err:
        print(f"Erro no banco de dados: {db_err}")
        return jsonify({'success': False, 'message': f'Erro no banco de dados: {str(db_err)}'}), 500
    except Exception as e:
        print(f"Erro ao fazer login: {e}")
        return jsonify({'success': False, 'message': f'Erro ao fazer login: {str(e)}'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# Rota de permissões


@app.route('/permissoes', methods=['GET', 'POST'])
@login_required
def permissoes():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            matricula = request.form.get('matricula')
            permissoes_selecionadas = request.form.getlist('permissoes')
            print(
                f"Matricula recebida: {matricula}, Permissoes selecionadas: {permissoes_selecionadas}")

            # Limpar permissões existentes do usuário
            cursor.execute(
                "DELETE FROM permissoes WHERE matricula = %s", (matricula,))

            # Adicionar novas permissões
            for perm in permissoes_selecionadas:
                modulo, permissao = perm.split(':')
                cursor.execute(
                    "SELECT 1 FROM permissoes_disponiveis WHERE modulo = %s AND permissao = %s",
                    (modulo, permissao)
                )
                if cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO permissoes (matricula, modulo, permissao) VALUES (%s, %s, %s)",
                        (matricula, modulo, permissao)
                    )
            conn.commit()
            print(f"Permissoes salvas para matricula {matricula}")
            return jsonify({'success': True, 'message': 'Permissões salvas com sucesso', 'redirect': url_for('permissoes')})

        # Buscar usuários
        cursor.execute("SELECT matricula, nome, filial FROM usuarios")
        usuarios = cursor.fetchall()

        # Buscar todas as permissões disponíveis
        cursor.execute(
            "SELECT modulo, permissao FROM permissoes_disponiveis ORDER BY modulo, permissao")
        permissoes_disponiveis = [
            f"{row['modulo']}:{row['permissao']}" for row in cursor.fetchall()]

        # Buscar permissões atribuídas
        cursor.execute("SELECT matricula, modulo, permissao FROM permissoes")
        permissoes = cursor.fetchall()
        permissoes_dict = {}
        for p in permissoes:
            matricula = p['matricula']
            if matricula not in permissoes_dict:
                permissoes_dict[matricula] = []
            permissoes_dict[matricula].append(
                f"{p['modulo']}:{p['permissao']}")

        return render_template(
            'permissoes.html',
            usuarios=usuarios,
            permissoes_disponiveis=permissoes_disponiveis,
            permissoes_dict=permissoes_dict
        )
    except Exception as e:
        print(f"Erro em /permissoes: {e}")
        return jsonify({'success': False, 'message': f'Erro ao carregar permissões: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()


# --- CONFIGURAÇÃO CENTRALIZADA ---
API_BASE_URL = "http://192.168.4.1:8480/ws/api_sacolao"
API_TOKEN = "s4c0140_$b4tm4n_r0b1n_790883_000103"
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

try:
    DATABASE_URI = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    engine = create_engine(DATABASE_URI)
    print("Conexão com o banco de dados estabelecida com sucesso.")
except Exception as e:
    print(f"ERRO CRÍTICO ao conectar ao banco de dados: {e}")
    engine = None

# --- DECORATORS E FUNÇÕES AUXILIARES ---


def login_requerido(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'user' not in session:
            session['user'] = {'matricula': '9999', 'nome': 'Usuário Padrão'}
        return f(*args, **kwargs)
    return wrap


def obter_detalhes_de_muitos_produtos(codigos_produtos):
    """
    Busca detalhes de múltiplos produtos em uma única consulta.
    Esta é a versão corrigida que usa bindparam para a cláusula IN.
    """
    if not engine or not codigos_produtos:
        return {}

    detalhes_map = {}
    with engine.connect() as conn:
        # Prepara a query com o bindparam para a cláusula IN, que é a forma segura.
        query = text(
            "SELECT codigo, descricao, barras FROM produtos WHERE codigo IN :codigos")
        query = query.bindparams(bindparam('codigos', expanding=True))

        # Executa a query passando a lista de códigos
        result = conn.execute(query, {"codigos": list(codigos_produtos)})

        for row in result:
            detalhes_map[str(row.codigo)] = {
                "descricao": row.descricao, "barras": row.barras}

    return detalhes_map


@app.route("/pda_confe_pedido")
def pda_confe_pedido():
    return render_template("pda_confe_pedido.html")


@app.route("/pda_conferencia_pedido")
def pda_conferencia_pedido():
    return render_template("pda_conferencia_pedido.html")

# --- ROTAS DA API ---



lojas_map = {
    "1": "Ponta Negra", "2": "Alecrim", "7": "SAC - Centro VI", "100": "Lagoa Nova",
    "121": "Norte Shopping", "122": "Parnamirim", "131": "ZN2", "137": "Macaiba",
    "140": "Maria Lacerda", "141": "Igapo"
}

def get_db_connection():
    try:
        # Imprime as credenciais que está tentando usar (exceto a senha)
        print(f"DEBUG: Tentando conectar ao host '{os.getenv('DB_HOST')}' com o usuário '{os.getenv('DB_USER')}' no banco '{os.getenv('DB_NAME')}'")
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'), user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'), database=os.getenv('DB_NAME')
        )
        print("DEBUG: Conexão com o banco de dados bem-sucedida!")
        return conn
    except mysql.connector.Error as err:
        # Imprime o erro específico da conexão
        print(f"ERRO DE CONEXÃO COM O DB: {err}")
        return None


@app.route('/api/obter-url', methods=['GET'])
def obter_url():
    print("\n--- Rota /api/obter-url foi chamada ---")
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'erro': 'Falha na conexão com o banco'}), 500
        
        cursor = conn.cursor()
        
        # Seleciona a URL da tabela de parâmetros
        cursor.execute("SELECT url_api FROM parametros WHERE id = 1")
        result = cursor.fetchone() # Pega a primeira (e única) linha
        
        cursor.close()
        
        # Verifica se algo foi encontrado e retorna
        if result and result[0]:
            print(f"DEBUG: URL encontrada no banco: {result[0]}")
            return jsonify({'url_api': result[0]})
        else:
            print("DEBUG: Nenhuma URL encontrada no banco para o id=1.")
            return jsonify({'url_api': ''}) # Retorna vazio se não houver nada

    except mysql.connector.Error as err:
        print(f"ERRO DE SQL: {err}")
        return jsonify({'erro': f'Erro no banco de dados: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()
            print("--- Fim da chamada /api/obter-url ---")


# =================================
# ROTA PARA ANÁLISE DE VENDA CASADA 
# =================================
@app.route('/api/analise-cesta')
@login_required
def api_analise_cesta():
    produto_id_coluna = 'produto'
    quantidade_coluna = 'qtd'  
    produto_id = request.args.get('produto_id')
    data_str = request.args.get('data')
    logging.info("=======================================================")
    logging.info(f"Iniciando Análise de Cesta para Produto: {produto_id} na Data: {data_str}")

    if not all([produto_id, data_str]):
        return jsonify({"erro": "ID do Produto e a Data são obrigatórios."}), 400

    # ---  Encontrar todas as notas que contêm o produto principal ---
    logging.info("--- ETAPA 1: Buscando notas fiscais com o produto principal...")
    notas_com_produto = set()
    for loja_id in LOJAS_MAP.keys():
        db_name = LOJA_DB_MAP.get(loja_id)
        table_name = TABELAS_VENDAS_MAP.get(loja_id)
        if not db_name or not table_name: continue
        
        conn = None
        try:
            conn = get_db_connection(db_name)
            cursor = conn.cursor(dictionary=True)
            logging.info(f"  - Conectado a {db_name}. Buscando em {table_name}...")
            
            # Query ajustada para usar a coluna 'produto'
            query = f"""
                SELECT DISTINCT CONCAT(loja, '-', nfce, '-', serie) as numero_pedido
                FROM {table_name} 
                WHERE {produto_id_coluna} = %s AND DATE(data_hora) = %s
            """
            cursor.execute(query, (produto_id, data_str))
            resultados = cursor.fetchall()
            if resultados:
                for row in resultados:
                    notas_com_produto.add(row['numero_pedido'])
                logging.info(f"  -> SUCESSO: {len(resultados)} nota(s) encontrada(s) na loja {loja_id}.")
        except Exception as e:
            logging.error(f"  -> ERRO ao buscar notas na loja {loja_id}: {e}")
        finally:
            if conn and conn.is_connected(): conn.close()

    if not notas_com_produto:
        logging.warning("Nenhuma nota fiscal encontrada com o produto principal.")
        return jsonify({ "produto_principal": {"id": produto_id, "descricao": get_product_name(produto_id)}, "total_vendas_produto": 0, "vendas_sozinho": 0, "vendas_acompanhadas": 0, "produtos_associados": [] })

    logging.info(f"--- ETAPA 1 CONCLUÍDA: {len(notas_com_produto)} notas únicas encontradas.")
    
    # ---  Buscar todos os itens de cada nota encontrada ---
    logging.info("--- ETAPA 2: Buscando todos os itens das notas...")
    itens_por_nota = defaultdict(list)
    for loja_id in LOJAS_MAP.keys():
        db_name = LOJA_DB_MAP.get(loja_id)
        table_name = TABELAS_VENDAS_MAP.get(loja_id)
        if not db_name or not table_name: continue
        conn = None
        try:
            conn = get_db_connection(db_name)
            cursor = conn.cursor(dictionary=True)
            placeholders = ','.join(['%s'] * len(notas_com_produto))
            # Query ajustada para buscar as colunas corretas
            query = f"""
                SELECT CONCAT(loja, '-', nfce, '-', serie) as numero_pedido, {produto_id_coluna}, preco, {quantidade_coluna} 
                FROM {table_name} 
                WHERE CONCAT(loja, '-', nfce, '-', serie) IN ({placeholders})
            """
            cursor.execute(query, tuple(notas_com_produto))
            for row in cursor.fetchall():
                itens_por_nota[row['numero_pedido']].append(row)
        finally:
            if conn and conn.is_connected(): conn.close()
    
    logging.info(f"--- ETAPA 2 CONCLUÍDA: Itens de {len(itens_por_nota)} notas carregados.")

    # ---  Processar os dados ---
    logging.info("--- ETAPA 3: Processando dados e calculando KPIs...")
    vendas_sozinho = 0
    valor_agregado_total = 0.0
    produtos_associados = defaultdict(lambda: {'frequencia': 0, 'valor': 0.0})

    for numero_pedido, itens_na_nota in itens_por_nota.items():
        if len(itens_na_nota) == 1:
            vendas_sozinho += 1
        else:
            for item in itens_na_nota:
                # Usando os nomes de coluna corretos
                if str(item[produto_id_coluna]) != produto_id:
                    valor_item = float(item.get('preco') or 0.0) * int(item.get(quantidade_coluna) or 0)
                    valor_agregado_total += valor_item
                    pid = str(item[produto_id_coluna])
                    produtos_associados[pid]['frequencia'] += 1
                    produtos_associados[pid]['valor'] += valor_item
    
    # --- : Finalizar ---
    logging.info("--- ETAPA 4: Buscando nomes dos produtos associados...")
    ids_associados = list(produtos_associados.keys())
    detalhes_associados = get_product_name_batch(ids_associados) if ids_associados else {}
        
    ranking_associados = sorted(produtos_associados.items(), key=lambda item: item[1]['frequencia'], reverse=True)[:20]
    
    vendas_acompanhadas = len(itens_por_nota) - vendas_sozinho
    ticket_medio_adicional = (valor_agregado_total / vendas_acompanhadas) if vendas_acompanhadas > 0 else 0.0

    logging.info("Análise concluída! Montando resposta final.")
    
    resultado_final = {
        "produto_principal": {"id": produto_id, "descricao": get_product_name(produto_id)},
        "total_vendas_produto": len(itens_por_nota),
        "vendas_sozinho": vendas_sozinho,
        "vendas_acompanhadas": vendas_acompanhadas,
        "valor_agregado_total": valor_agregado_total,
        "ticket_medio_adicional": ticket_medio_adicional,
        "produtos_associados": [
            {"id": pid, "descricao": detalhes_associados.get(pid, f"Produto {pid}"), "frequencia": data['frequencia'], "valor": data['valor']}
            for pid, data in ranking_associados
        ]
    }
    
    return jsonify(resultado_final)



def get_product_details_batch(product_ids):
    """Função otimizada para buscar detalhes de muitos produtos de uma vez."""
    if not product_ids:
        return {}
    details_map = {}
    try:
        conn = get_db_connection('estoque_db')
        cursor = conn.cursor(dictionary=True)
        placeholders = ','.join(['%s'] * len(product_ids))
        query = f"SELECT codigo, descricao, custo, grupo FROM produtos WHERE codigo IN ({placeholders})"
        cursor.execute(query, tuple(product_ids))
        for row in cursor.fetchall():
            details_map[str(row['codigo'])] = {
                'descricao': row.get('descricao', 'N/A'),
                'custo': row.get('custo', 0.0),
                'grupo': row.get('grupo')
            }
    except Exception as e:
        logging.error(f"Erro ao buscar detalhes de produtos em lote: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()
    return details_map


@app.route('/api/obter-parametros', methods=['GET'])
def obter_parametros():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT url_api, dias_busca, intervalo_minutos, usar_intervalo_datas, data_inicio_fixa, data_fim_fixa, automacao_ativa FROM parametros WHERE id = 1")
        parametros = cursor.fetchone()
        if parametros:
            if parametros.get('data_inicio_fixa'):
                parametros['data_inicio_fixa'] = parametros['data_inicio_fixa'].strftime('%Y-%m-%d')
            if parametros.get('data_fim_fixa'):
                parametros['data_fim_fixa'] = parametros['data_fim_fixa'].strftime('%Y-%m-%d')
            return jsonify(parametros)
        return jsonify({"erro": "Parâmetros não encontrados"}), 404
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/salvar-parametros', methods=['POST'])
def salvar_parametros():
    print("\n--- ROTA /api/salvar-parametros CHAMADA ---")
    data = request.get_json()
    print(f"DEBUG: Dados recebidos do front-end: {data}")

    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            print("ERRO: Falha ao obter conexão com o banco.")
            return jsonify({'erro': 'Falha na conexão com o banco'}), 500
            
        cursor = conn.cursor()
        sql = """
            UPDATE parametros SET 
            url_api = %s, dias_busca = %s, intervalo_minutos = %s,
            usar_intervalo_datas = %s, data_inicio_fixa = %s, data_fim_fixa = %s
            WHERE id = 1
        """
        
        data_inicio = data.get('data_inicio_fixa') or None
        data_fim = data.get('data_fim_fixa') or None
        
        valores = (
            data.get('url_api'), data.get('dias_busca'), data.get('intervalo_minutos'),
            data.get('usar_intervalo_datas'), data_inicio, data_fim
        )
        
        print(f"DEBUG: Executando SQL de UPDATE com os valores: {valores}")
        cursor.execute(sql, valores)
        
        conn.commit()
        print("SUCESSO: Commit realizado. Parâmetros salvos no banco.")
        return jsonify({"mensagem": "Parâmetros salvos com sucesso!"})
        
    except Exception as e:
        if conn: conn.rollback()
        print(f"ERRO CRÍTICO ao salvar parâmetros: {str(e)}")
        return jsonify({"erro": str(e)}), 500
    finally:
        if conn: conn.close()
        print("--- FIM DA ROTA /api/salvar-parametros ---")

@app.route('/api/alterar-automacao', methods=['POST'])
def alterar_automacao():
    data = request.get_json()
    novo_estado = data.get('ativa', False)
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE parametros SET automacao_ativa = %s WHERE id = 1", (novo_estado,))
        conn.commit()
        return jsonify({"mensagem": "Estado da automação alterado com sucesso."})
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"erro": str(e)}), 500
    finally:
        if conn: conn.close()



@app.route('/api/iniciar-processo', methods=['POST'])
def iniciar_processo():
    conn = None
    cursor = None
    lookup_cursor = None
    try:
        conn = get_db_connection()
        if not conn: 
            return jsonify({'erro': 'Falha na conexão com o banco'}), 500
        
        cursor = conn.cursor()
        lookup_cursor = conn.cursor(dictionary=True)
        
        # 1. Busca os parâmetros do banco (sem alterações aqui)
        lookup_cursor.execute("SELECT * FROM parametros WHERE id = 1")
        parametros = lookup_cursor.fetchone()
        if not parametros or not parametros.get('url_api'):
            return jsonify({'erro': 'URL da API não está configurada.'}), 400
        
        # 2. Busca os pedidos que já existem para não duplicar (sem alterações aqui)
        print("-> Verificando pedidos já importados no banco de dados...")
        cursor.execute("SELECT DISTINCT pedido FROM pedidos_importados")
        pedidos_ja_existentes = {str(row[0]) for row in cursor.fetchall()}
        print(f"-> Encontrados {len(pedidos_ja_existentes)} pedidos já existentes. Eles serão ignorados.")

        # 3. Monta a URL da API (sem alterações aqui)
        url_salva = parametros['url_api']
        partes_url = url_salva.split('?')
        base_url_sem_params = partes_url[0]
        params_dict = {}
        if len(partes_url) > 1:
            for par in partes_url[1].split('&'):
                if '=' in par:
                    chave, valor = par.split('=', 1)
                    params_dict[chave] = valor

        if parametros.get('usar_intervalo_datas'):
            print("-> Usando modo de data: INTERVALO FIXO.")
            params_dict['inicio'] = parametros['data_inicio_fixa'].strftime('%Y-%m-%d')
            params_dict['final'] = parametros['data_fim_fixa'].strftime('%Y-%m-%d')
        else:
            print("-> Usando modo de data: ÚLTIMOS DIAS.")
            dias_busca = parametros.get('dias_busca', 1)
            data_final = datetime.now()
            data_inicial = data_final - timedelta(days=int(dias_busca))
            params_dict['inicio'] = data_inicial.strftime('%Y-%m-%d')
            params_dict['final'] = data_final.strftime('%Y-%m-%d')
            
        params_dict['loja'] = '999'
        nova_query_string = '&'.join([f"{chave}={valor}" for chave, valor in params_dict.items()])
        url_completa = f"{base_url_sem_params}?{nova_query_string}"
        
        print(f"--- INICIANDO CONSULTA NA API COM URL: {url_completa} ---")
        
        # 4. Chama a API e processa a resposta
        try:
            response = requests.get(url_completa, timeout=30)
            response.raise_for_status()
            api_data = response.json()
            
            if api_data.get('erro') == True:
                print(f"ERRO DA API: {api_data.get('msg')}")
                return jsonify({'mensagem': f"API retornou um erro: {api_data.get('msg')}"})

            if not api_data.get('dados'):
                return jsonify({'mensagem': 'Processo finalizado. Nenhum pedido retornado pela API.'})

            pedidos_novos_salvos = 0
            itens_novos_salvos = 0
            pedidos_duplicados_ignorados = 0
            
            for pedido_data in api_data['dados']:
                pedido_id_api = str(pedido_data.get('pedido'))

                if pedido_id_api in pedidos_ja_existentes:
                    pedidos_duplicados_ignorados += 1
                    continue

                if pedido_data.get('status') == 3:
                    id_destino = str(pedido_data.get('destino'))
                    nome_loja = lojas_map.get(id_destino, f"LOJA_ID_{id_destino}")
                    
                    print(f"-> NOVO PEDIDO ENCONTRADO: {pedido_id_api} (Status 3) para a loja: {nome_loja}")
                    
                    for item in pedido_data.get('itens', []):
                        codigo_produto = item.get('produto')
                        
                        # <<<  Adicionar a coluna 'multi_barras' na consulta >>>
                        sql_busca_produto = "SELECT descricao, barras, multi_barras FROM produtos WHERE codigo = %s"
                        lookup_cursor.execute(sql_busca_produto, (codigo_produto,))
                        produto_encontrado = lookup_cursor.fetchone()
                        
                        descricao_produto = "PRODUTO NÃO CADASTRADO"
                        codigo_barras_produto = ""
                        # <<<  Criar variável para armazenar os múltiplos barras >>>
                        multi_barras_produto = ""
                        
                        if produto_encontrado:
                            descricao_produto = produto_encontrado.get('descricao', descricao_produto)
                            codigo_barras_produto = produto_encontrado.get('barras', codigo_barras_produto)
                            # <<<  Obter o valor da coluna 'multi_barras' >>>
                            multi_barras_produto = produto_encontrado.get('multi_barras', '') 

                        # <<<  Adicionar 'multi_barras' na lista de colunas do INSERT >>>
                        sql_insert = """
                            INSERT INTO pedidos_importados (
                                pedido, data, codigo, descricao, codigo_barras, multi_barras, qtd, 
                                origem, destino, status, obs, status2
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        # <<<  Adicionar a variável 'multi_barras_produto' na tupla de valores >>>
                        valores = (
                            pedido_data.get('pedido'), pedido_data.get('data'),
                            codigo_produto, descricao_produto, codigo_barras_produto,
                            multi_barras_produto, # <-- Novo valor aqui
                            item.get('qtd'), pedido_data.get('origem'),
                            pedido_data.get('destino'), pedido_data.get('status'),
                            'Importado via automação', 'EM CONFERENCIA'
                        )
                        cursor.execute(sql_insert, valores)
                        itens_novos_salvos += 1
                    
                    
                    if pedido_data.get('itens'): # Apenas incrementa se o pedido tiver itens
                       pedidos_novos_salvos += 1
            
            conn.commit()
            mensagem_final = f'Processo finalizado. {pedidos_novos_salvos} novos pedidos ({itens_novos_salvos} itens) salvos. {pedidos_duplicados_ignorados} pedidos já existentes foram ignorados.'
            print(f"--- FIM DO PROCESSO ---")
            print(mensagem_final)
            return jsonify({'mensagem': mensagem_final})

        except requests.exceptions.RequestException as e:
            return jsonify({'erro': f'Não foi possível conectar à API: {e}'}), 500

    except Exception as e:
        print(f"ERRO CRÍTICO no processo: {str(e)}")
        if conn: conn.rollback()
        return jsonify({'erro': f'Erro crítico no processo: {str(e)}'}), 500
    finally:
        if conn and conn.is_connected():
            if cursor: cursor.close()
            if lookup_cursor: lookup_cursor.close()
            conn.close()
 


@app.route("/filtrar-pedidos", methods=["POST"])
#@login_required
def filtrar_pedidos_do_banco():
    data = request.json
    destino = data.get("destino")

    if not destino:
        return jsonify({"erro": "O campo 'destino' é obrigatório"}), 400

    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"erro": "Não foi possível conectar ao banco de dados"}), 500
        
        cursor = conn.cursor(dictionary=True)
        sql_query = """
            SELECT * FROM pedidos_importados 
            WHERE destino = %s AND status2 = 'EM CONFERENCIA'
            ORDER BY pedido;
        """
        cursor.execute(sql_query, (destino,))
        itens_de_pedidos = cursor.fetchall()
        
        if not itens_de_pedidos:
            return jsonify({"pedidos": []})

        pedidos_agrupados = {}
        for item in itens_de_pedidos:
            pedido_id = item['pedido']
            
            if pedido_id not in pedidos_agrupados:
                pedidos_agrupados[pedido_id] = {
                    "pedido": pedido_id,
                    "data": item['data'].strftime('%Y-%m-%d') if item.get('data') else None,
                    "origem": item['origem'], "destino": item['destino'],
                    "status": item['status'], "status2": item['status2'],
                    "itens": []
                }
        
            pedidos_agrupados[pedido_id]['itens'].append({
                "produto": item['codigo'],
                "descricao": item['descricao'],
                "qtd": item['qtd'],
                "barras": item.get('codigo_barras', ''),
                "multi_barras": item.get('multi_barras', '') 
            })
        
        pedidos_filtrados = list(pedidos_agrupados.values())

        return jsonify({"pedidos": pedidos_filtrados})

    except Exception as e:
        return jsonify({"erro": f"Ocorreu um erro no servidor: {str(e)}"}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()



@app.route("/salvar-conferencia", methods=["POST"])
@login_required
def salvar_conferencia():
    data = request.get_json()
    itens = data.get("itens")
    
    # Lógica para obter o número do pedido e da caixa
    numero_pedido = data.get("pedido")
    numero_caixa = data.get("caixa")
    if not numero_pedido and itens:
        numero_pedido = itens[0].get('numero_pedido')
    if not numero_caixa and itens:
        numero_caixa = itens[0].get('caixa')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Apaga registros antigos se estiver salvando uma caixa existente
        if numero_caixa and numero_pedido:
            # Esta lógica pode variar, mas a ideia é limpar antes de inserir
            cursor.execute("DELETE FROM conferencia WHERE numero_pedido = %s AND caixa = %s", (numero_pedido, numero_caixa))

        if itens:
            # <<<  Adicionar a coluna 'multi_barras' no INSERT >>>
            sql_insert = """
                INSERT INTO conferencia (
                    matricula, conferente, numero_pedido, codigo, descricao, codigo_barras, multi_barras,
                    unidade, quantidade_pedida, quantidade_conferida, divergencia, 
                    lojas_tag, status, caixa
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            nome_conferente = session["user"]["nome"]
            matricula_conferente = session["user"]["matricula"]
            print("\n--- INICIANDO SALVAMENTO DE CONFERÊNCIA ---")
            
            for item in itens:
                # <<<  Obter o valor de 'multi_barras' do JSON recebido >>>
                multi_barras = item.get('multi_barras', '') 

                params = (
                    matricula_conferente,
                    nome_conferente,
                    item.get('numero_pedido'),
                    item.get('codigo'),
                    item.get('descricao'),
                    item.get('codigo_barras'),
                    multi_barras,  
                    item.get('unidade', 'UN'),
                    item.get('quantidade_pedida'),
                    item.get('quantidade_conferida'),
                    item.get('divergencia'),
                    item.get('lojas_tag'),
                    item.get('status', 'EM CONFERENCIA'),
                    item.get('caixa')
                )
                cursor.execute(sql_insert, params)
            
            print("--- FIM DO SALVAMENTO DE CONFERÊNCIA ---\n")

        # Atualiza o status do pedido em 'pedidos_importados'
        if numero_pedido:
            cursor.execute("UPDATE pedidos_importados SET status2 = 'EM CONFERENCIA' WHERE pedido = %s", (numero_pedido,))

        conn.commit()
        return jsonify({"status": "ok", "mensagem": "Dados salvos com sucesso e prontos para conferência."})

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Erro ao salvar conferência: {e}")
        return jsonify({"status": "erro", "mensagem": f"Erro no servidor: {e}"}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()



@app.route("/finalizar-conferencia", methods=["POST"])
@login_required
def finalizar_conferencia():
    dados = request.get_json()
    numero_pedido = dados.get("numero_pedido")
    if not numero_pedido:
        return jsonify({"erro": "Número do pedido é obrigatório."}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        # 1. Buscar todos os itens do pedido que estão 'EM CONFERENCIA'
        cur.execute("SELECT id, quantidade_pedida, quantidade_conferida FROM conferencia WHERE numero_pedido = %s AND status = 'EM CONFERENCIA'", (numero_pedido,))
        itens_a_finalizar = cur.fetchall()

        if not itens_a_finalizar:
            return jsonify({"status": "ok", "message": "Nenhum item em conferência para finalizar."}), 200

        # 2. Para cada item, calcular crédito/débito e preparar para o update
        for item in itens_a_finalizar:
            # Garante que os valores são numéricos
            qtd_pedida = int(item.get('quantidade_pedida', 0))
            qtd_conferida = int(item.get('quantidade_conferida', 0))

            divergencia = qtd_conferida - qtd_pedida

            # --- LÓGICA DE CÁLCULO DE CRÉDITO/DÉBITO ---
            
            credito_calculado = abs(divergencia) * 1.00
            debito_calculado = 0.00

            # 3. Executar o UPDATE para cada linha, salvando os novos valores
            sql_update = """
                UPDATE conferencia 
                SET 
                    status = 'CONFERIDO', 
                    data_hora = NOW(),
                    credito = %s,
                    debito = %s
                WHERE id = %s
            """
            cur.execute(sql_update, (credito_calculado,
                        debito_calculado, item['id']))

        # Confirma todas as alterações no banco de dados de uma vez
        conn.commit()

        return jsonify({"status": "ok", "message": "Pedido finalizado e valores de crédito/débito calculados com sucesso."})

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Erro ao finalizar conferência: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        if conn and conn.is_connected():
            cur.close()
            conn.close()


@app.route("/buscar-itens")
@login_requerido
def buscar_itens():
    numero_pedido = request.args.get("pedido")
    if not numero_pedido:
        return jsonify({"erro": "Número do pedido é obrigatório"}), 400
    if not engine:
        return jsonify({"erro": "Conexão com o banco de dados não está disponível."}), 500
    try:
        with engine.connect() as conn:
            query = text(
                "SELECT * FROM conferencia WHERE numero_pedido = :pedido AND status = 'EM CONFERENCIA'")
            result = conn.execute(query, {"pedido": numero_pedido})
            rows = [dict(row._mapping) for row in result]
            return jsonify({"itens": rows})
    except Exception as e:
        print(f"Erro ao buscar itens: {e}")
        return jsonify({"erro": f"Erro interno do servidor: {str(e)}"}), 500


# Rota protegida: /pda_romaneio
@app.route('/pda_romaneio')
@login_required
def pda_romaneio():
    return render_template('pda_romaneio.html')


@app.route('/pda_conferencia/<romaneio_id>')
def pda_conferencia(romaneio_id):
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM romaneios WHERE id = %s", (romaneio_id,))
        romaneio = cursor.fetchone()
        if not romaneio:
            print(f"Romaneio {romaneio_id} não encontrado")
            return "Romaneio não encontrado", 404

        # Formatar as datas para exibir no formato DD/MM/YYYY HH:MM
        data_inicio = romaneio['data_inicio'].strftime(
            "%d/%m/%Y %H:%M") if romaneio['data_inicio'] else "N/A"
        data_fim = romaneio['data_fim'].strftime(
            "%d/%m/%Y %H:%M") if romaneio['data_fim'] else "N/A"

        return render_template('pda_conferencia.html',
                               romaneio_id=romaneio['id'],
                               conferente=romaneio['conferente'],
                               motorista=romaneio['nome_motorista'],
                               filial=romaneio['nome_filial'],
                               placa=romaneio['placa_caminhao'],
                               data_inicio=data_inicio,
                               data_fim=data_fim)
    except Exception as e:
        print(f"Erro ao buscar romaneio: {str(e)}")
        return f"Erro ao carregar romaneio: {str(e)}", 500
    finally:
        cursor.close()
        db.close()


# Variáveis de ambiente
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')


def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


@app.route('/processar_romaneio', methods=['POST'])
def processar_romaneio():
    print(f"Sessão atual: {session}")
    if 'user' not in session:
        print("Usuário não encontrado na sessão, redirecionando para login")
        return redirect(url_for('login'))

    user = session['user']
    matricula_conferente = user.get('matricula')
    if not matricula_conferente:
        print("Matrícula do conferente não encontrada nos dados da sessão, redirecionando para login")
        return redirect(url_for('login'))

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Busca nome do conferente
        cursor.execute(
            "SELECT nome FROM usuarios WHERE matricula = %s", (matricula_conferente,))
        usuario = cursor.fetchone()
        if not usuario:
            print(f"Matrícula {matricula_conferente} não encontrada no banco")
            return redirect(url_for('login'))
        conferente_nome = usuario['nome']
        print(f"Conferente identificado: {conferente_nome}")
    except Exception as e:
        print(f"Erro ao consultar conferente: {str(e)}")
        return redirect(url_for('login'))
    finally:
        cursor.close()

    motorista_id = request.form.get('motorista_id')
    filial_id1 = request.form.get('filial_id1')
    placa_caminhao = request.form.get('placa_caminhao')

    print(
        f"Recebido: motorista_id={motorista_id}, filial_id1={filial_id1}, placa_caminhao={placa_caminhao}, matricula_conferente={matricula_conferente}")

    if not motorista_id or not filial_id1 or not placa_caminhao:
        return "Dados incompletos", 400

    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT nome FROM usuarios WHERE matricula = %s", (motorista_id,))
        motorista = cursor.fetchone()
        if not motorista:
            print(f"Matrícula do motorista {motorista_id} não encontrada")
            return "Matrícula do motorista inválida", 400
        nome_motorista = motorista['nome']
    except Exception as e:
        print(f"Erro ao consultar motorista: {str(e)}")
        return f"Erro ao consultar motorista: {str(e)}", 500

    try:
        cursor.execute(
            "SELECT filial_nome1 FROM filiais WHERE filial_id1 = %s", (filial_id1,))
        filial = cursor.fetchone()
        if not filial:
            print(f"Filial com ID {filial_id1} não encontrada")
            return "Filial inválida", 400
        nome_filial = filial['filial_nome1']
    except Exception as e:
        print(f"Erro ao consultar filial: {str(e)}")
        return f"Erro ao consultar filial: {str(e)}", 500

    # Gera a data atual
    data_hoje = datetime.now().strftime("%Y%m%d")

    # Busca o maior sequencial globalmente
    sql_busca_sequencial = "SELECT MAX(id) as max_id FROM romaneios"
    cursor.execute(sql_busca_sequencial)
    resultado = cursor.fetchone()

    ultimo_sequencial = 0
    if resultado and resultado['max_id']:
        try:
            ultimo_sequencial = int(resultado['max_id'].split("-")[1])
        except (IndexError, ValueError):
            ultimo_sequencial = 0

    novo_sequencial = ultimo_sequencial + 1
    romaneio_id = f"RMN{data_hoje}-{str(novo_sequencial).zfill(3)}"

    data_inicio = datetime.now()

    try:
        sql_insert = """
            INSERT INTO romaneios 
                (id, motorista_id, filial_id1, placa_caminhao, conferente, nome_motorista, nome_filial, status, data_inicio, data_fim) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'em_andamento', %s, NULL)
        """
        valores = (
            romaneio_id,
            motorista_id,
            filial_id1,
            placa_caminhao,
            conferente_nome,
            nome_motorista,
            nome_filial,
            data_inicio
        )

        cursor.execute(sql_insert, valores)
        db.commit()
        print(f"Romaneio {romaneio_id} inserido com sucesso")
    except Exception as e:
        print(f"Erro ao salvar romaneio: {str(e)}")
        db.rollback()
        return f"Erro ao iniciar romaneio: {str(e)}", 500
    finally:
        cursor.close()
        db.close()

    return redirect(url_for('pda_conferencia', romaneio_id=romaneio_id))


@app.route('/registrar_volume', methods=['POST'])
def registrar_volume():
    romaneio_id = request.form.get('romaneio_id')
    codigo_barra_completo = request.form.get('codigo_volume')

    if not romaneio_id or not codigo_barra_completo:
        return jsonify({"status": "error", "msg": "Dados incompletos"}), 400

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Verifica se o romaneio existe
        cursor.execute(
            "SELECT id FROM romaneios WHERE id = %s", (romaneio_id,))
        romaneio_atual = cursor.fetchone()
        if not romaneio_atual:
            return jsonify({"status": "error", "msg": f"Romaneio {romaneio_id} não encontrado."}), 400

        # Extrair informações do código de barras
        partes = codigo_barra_completo.split('-')
        numero_pedido = partes[0]
        volume_info = partes[1].split('/')
        volume_numero = int(volume_info[0])
        total_volumes = int(volume_info[1])

        # Buscar filial_id do romaneio
        cursor.execute(
            "SELECT filial_id1 FROM romaneios WHERE id = %s", (romaneio_id,))
        filial_data = cursor.fetchone()
        filial_id_romaneio = filial_data['filial_id1'] if filial_data else None

        if not filial_id_romaneio:
            return jsonify({"status": "error", "msg": "Filial do romaneio não encontrada."}), 400

        # Verificar se esse pedido já foi usado em outro romaneio
        cursor.execute("""
            SELECT p.numero_pedido, r.id AS romaneio_id, r.nome_filial
            FROM pedidos p
            JOIN romaneios r ON p.romaneio_id = r.id
            WHERE p.numero_pedido = %s AND p.romaneio_id != %s
        """, (numero_pedido, romaneio_id))
        pedido_em_outro_romaneio = cursor.fetchone()

        if pedido_em_outro_romaneio:
            return jsonify({
                "status": "warning",
                "msg": f"Pedido {pedido_em_outro_romaneio['numero_pedido']} já está no romaneio {pedido_em_outro_romaneio['romaneio_id']} da filial {pedido_em_outro_romaneio['nome_filial']}."
            })

        # Verificar se o pedido já existe neste romaneio
        cursor.execute(
            "SELECT id FROM pedidos WHERE numero_pedido = %s AND romaneio_id = %s", (numero_pedido, romaneio_id))
        pedido_existente = cursor.fetchone()

        if not pedido_existente:
            # Criar pedido com filial_id do romaneio
            sql_criar_pedido = """
                INSERT INTO pedidos 
                    (numero_pedido, romaneio_id, filial_id, total_volumes, status)
                VALUES (%s, %s, %s, %s, 'pendente')
            """
            cursor.execute(sql_criar_pedido, (numero_pedido,
                           romaneio_id, filial_id_romaneio, total_volumes))
            pedido_id = cursor.lastrowid

            # Criar todos os volumes como 'pendente'
            for i in range(1, total_volumes + 1):
                codigo_barra = f"{numero_pedido}-{i}/{total_volumes}"
                sql_criar_volume = """
                    INSERT INTO volumes 
                        (romaneio_id, pedido_id, codigo_barra, status)
                    VALUES (%s, %s, %s, 'pendente')
                """
                cursor.execute(sql_criar_volume,
                               (romaneio_id, pedido_id, codigo_barra))
        else:
            pedido_id = pedido_existente['id']

        # Verificar se o volume já foi escaneado
        cursor.execute("""
            SELECT id, status FROM volumes 
            WHERE pedido_id = %s AND codigo_barra = %s
        """, (pedido_id, codigo_barra_completo))
        volume_atual = cursor.fetchone()

        if volume_atual and volume_atual['status'] == 'escaneado':
            return jsonify({
                "status": "warning",
                "msg": f"Volume {codigo_barra_completo} já foi escaneado."
            })
        elif volume_atual and volume_atual['status'] == 'pendente':
            cursor.execute("""
                UPDATE volumes SET 
                    data_conferencia = NOW(),
                    status = 'escaneado'
                WHERE id = %s
            """, (volume_atual['id'],))
        else:
            cursor.execute("""
                INSERT INTO volumes 
                    (romaneio_id, pedido_id, codigo_barra, data_conferencia, status)
                VALUES (%s, %s, %s, NOW(), 'escaneado')
            """, (romaneio_id, pedido_id, codigo_barra_completo))

        # Atualizar status do pedido
        cursor.execute("""
            SELECT COUNT(*) AS total, SUM(CASE WHEN status = 'escaneado' THEN 1 ELSE 0 END) AS escaneados
            FROM volumes
            WHERE pedido_id = %s
        """, (pedido_id,))
        stats = cursor.fetchone()

        if stats['total'] == stats['escaneados']:
            cursor.execute(
                "UPDATE pedidos SET status = 'ok' WHERE id = %s", (pedido_id,))
        else:
            cursor.execute(
                "UPDATE pedidos SET status = 'pendente' WHERE id = %s", (pedido_id,))

        db.commit()
        return jsonify({
            "status": "ok",
            "volume": codigo_barra_completo,
            "msg": "Volume registrado com sucesso!"
        })

    except Exception as e:
        db.rollback()
        print(f"Erro ao salvar volume: {str(e)}")
        return jsonify({"status": "error", "msg": str(e)}), 500

    finally:
        cursor.close()
        db.close()


@app.route('/get_pedidos/<romaneio_id>', methods=['GET'])
def get_pedidos(romaneio_id):
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Consulta para obter pedidos e status atualizados
        sql_pedidos = """
            SELECT 
                p.id AS pedido_id,
                p.numero_pedido,
                p.total_volumes,
                COUNT(v.id) AS volumes_escaneados,
                CASE 
                    WHEN COUNT(v.id) = p.total_volumes THEN 'ok'
                    ELSE 'pendente'
                END AS status
            FROM pedidos p
            LEFT JOIN volumes v ON p.id = v.pedido_id AND v.romaneio_id = %s AND v.status = 'escaneado'
            WHERE p.romaneio_id = %s
            GROUP BY p.id, p.numero_pedido, p.total_volumes
        """
        cursor.execute(sql_pedidos, (romaneio_id, romaneio_id))
        pedidos = cursor.fetchall()

        return jsonify({"status": "ok", "pedidos": pedidos})

    except Exception as e:
        print(f"Erro ao buscar pedidos: {str(e)}")
        return jsonify({"status": "error", "msg": str(e)}), 500

    finally:
        cursor.close()
        db.close()


@app.route('/criar_pedido', methods=['POST'])
def criar_pedido():
    romaneio_id = request.form.get('romaneio_id')
    numero_pedido = request.form.get('numero_pedido')
    filial_id = request.form.get('filial_id')
    total_volumes = request.form.get('total_volumes')

    if not romaneio_id or not numero_pedido or not filial_id or not total_volumes:
        return jsonify({"status": "error", "msg": "Todos os campos são obrigatórios."}), 400

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Verifica se o romaneio existe
        cursor.execute(
            "SELECT id FROM romaneios WHERE id = %s", (romaneio_id,))
        romaneio = cursor.fetchone()
        if not romaneio:
            return jsonify({"status": "error", "msg": f"Romaneio {romaneio_id} não encontrado."}), 400

        # Insere o pedido com filial_id
        sql = """
            INSERT INTO pedidos 
                (numero_pedido, romaneio_id, filial_id, total_volumes, status)
            VALUES (%s, %s, %s, %s, 'pendente')
        """
        cursor.execute(sql, (numero_pedido, romaneio_id,
                       filial_id, total_volumes))
        db.commit()

        return jsonify({"status": "ok", "msg": "Pedido criado com sucesso."})

    except Exception as e:
        db.rollback()
        print(f"Erro ao criar pedido: {str(e)}")
        return jsonify({"status": "error", "msg": str(e)}), 500

    finally:
        cursor.close()
        db.close()


@app.route('/finalizar_romaneio/<romaneio_id>', methods=['POST'])
def finalizar_romaneio(romaneio_id):
    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Atualiza o status do romaneio e define data_fim como NOW()
        cursor.execute("""
            UPDATE romaneios 
            SET status = 'concluido', data_fim = NOW() 
            WHERE id = %s
        """, (romaneio_id,))
        db.commit()

        # Após finalizar, redirecione para a tela de resumo do romaneio
        return redirect(url_for('pda_resumo_romaneio', romaneio_id=romaneio_id))

    except Exception as e:
        db.rollback()
        print(f"Erro ao finalizar romaneio: {str(e)}")
        return f"<script>alert('Erro ao finalizar romaneio: {str(e)}'); window.location='javascript:history.back()';</script>", 500

    finally:
        cursor.close()
        db.close()


@app.route('/get_volumes/<pedido_id>', methods=['GET'])
def get_volumes(pedido_id):
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Consulta para obter volumes do pedido
        sql_volumes = """
            SELECT 
                v.codigo_barra,
                v.data_conferencia,
                v.status
            FROM volumes v
            WHERE v.pedido_id = %s
        """
        cursor.execute(sql_volumes, (pedido_id,))
        volumes = cursor.fetchall()

        # Consulta para obter informações do pedido
        sql_pedido = """
            SELECT 
                id,
                numero_pedido,
                total_volumes
            FROM pedidos
            WHERE id = %s
        """
        cursor.execute(sql_pedido, (pedido_id,))
        pedido = cursor.fetchone()

        return jsonify({"status": "ok", "pedido": pedido, "volumes": volumes})

    except Exception as e:
        print(f"Erro ao buscar volumes: {str(e)}")
        return jsonify({"status": "error", "msg": str(e)}), 500

    finally:
        cursor.close()
        db.close()


@app.route('/pda_resumo_romaneio/<romaneio_id>')
@login_required
def pda_resumo_romaneio(romaneio_id):
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Dados do Romaneio
        cursor.execute("SELECT * FROM romaneios WHERE id = %s", (romaneio_id,))
        romaneio = cursor.fetchone()

        if not romaneio:
            return "Romaneio não encontrado", 404
    # Logs para debug
        print(f"Dados do Romaneio: {romaneio}")
        # Log placa
        print(f"Placa do Caminhão: {romaneio.get('placa_caminhao', '-')}")
        # Log filial
        print(f"Nome da Filial: {romaneio.get('nome_filial', '-')}")

        data_inicio = romaneio['data_inicio'].strftime(
            "%d/%m/%Y %H:%M") if romaneio['data_inicio'] else "-"
        data_fim = romaneio['data_fim'].strftime(
            "%d/%m/%Y %H:%M") if romaneio.get('data_fim') else "-"

        # Buscar pedidos + nome da filial corretamente
        sql_pedidos = """
    SELECT 
        p.id AS pedido_id,
        p.numero_pedido,
        p.filial_id,
        COALESCE(f.filial_nome1, '-') AS destinatario,  -- Garante que exibe '-' se for NULL
        p.total_volumes,
        COUNT(v.id) AS volumes_escaneados
    FROM pedidos p
    LEFT JOIN volumes v ON p.id = v.pedido_id AND v.status = 'escaneado'
    LEFT JOIN filiais f ON p.filial_id = f.filial_id1
    WHERE p.romaneio_id = %s
    GROUP BY p.id, p.numero_pedido, p.filial_id, f.filial_nome1, p.total_volumes
"""
        cursor.execute(sql_pedidos, (romaneio_id,))
        pedidos = cursor.fetchall()

        # Logs para debug
        print(f"Dados dos Pedidos: {pedidos}")
        for pedido in pedidos:
            print(
                f"Pedido ID: {pedido['pedido_id']}, Destinatário: {pedido['destinatario']}")

        return render_template(
            'pda_imprimir_romaneio.html',
            romaneio=romaneio,
            data_inicio=data_inicio,
            data_fim=data_fim,
            pedidos=pedidos
        )

    except Exception as e:
        print(f"Erro ao carregar resumo do romaneio: {str(e)}")
        return f"Erro ao carregar resumo do romaneio: {str(e)}", 500

    finally:
        cursor.close()
        db.close()


# @app.route('/pda_ajuste_fornec_lojas', methods=['GET', 'POST'])
# @login_required
# def pda_ajuste_fornec_lojas():
#     produtos = []
#     erro = None
#     fornecedor = None
#     grupo = None
#     loja = request.form.get('loja', '1').strip(
#     ) if request.method == 'POST' else '1'
#     exibir_zerados = request.form.get('exibir_zerados', '0') == '1'
#     page = request.args.get('page', 1, type=int)
#     per_page = 3000

#     if request.method == 'POST':
#         fornecedor = request.form.get('fornecedor', '').strip()
#         grupo = request.form.get('grupo', '').strip().upper()
#         action = request.form.get('action', None)

#         if action == 'enviar':
#             logging.info(
#                 f"Enviar acionado: loja={loja}, fornecedor={fornecedor}, grupo={grupo}")
#             erro = "Ação 'Enviar' não implementada. Contate o suporte."

#         try:
#             session = requests.Session()
#             retries = Retry(total=3, backoff_factor=1)
#             session.mount('http://', HTTPAdapter(max_retries=retries))

#             # Busca estoque primeiro
#             params_estoque = {
#                 'operacao': 'estoque',
#                 'operador': '999',
#                 'loja': loja
#             }
#             if grupo:
#                 params_estoque['grupo'] = grupo
#             if fornecedor:
#                 params_estoque['fornecedor'] = fornecedor

#             url_api = "http://192.168.4.1:8480/ws/api_sacolao"
#             resp_estoque = session.get(
#                 url_api, params=params_estoque, timeout=30)
#             resp_estoque.raise_for_status()
#             dados_estoque = resp_estoque.json().get("dados", [])

#             if not dados_estoque:
#                 erro = "Nenhum estoque encontrado para os filtros aplicados."
#             else:
#                 # Log para depuração
#                 logging.info(f"Dados de estoque: {dados_estoque[:5]}")

#                 # Extrai códigos de estoque para busca de produtos
#                 codigos_estoque = [str(item.get('produto', ''))
#                                    for item in dados_estoque if item.get('produto')]
#                 if codigos_estoque:
#                     # Busca detalhes dos produtos
#                     params_produtos = {
#                         'operacao': 'produtos',
#                         'operador': '999',
#                         'loja': loja  # Inclui loja para garantir consistência
#                     }
#                     # Não aplicamos os filtros de grupo e fornecedor aqui para maximizar os resultados
#                     # Se necessário, podemos reintroduzir os filtros posteriormente
#                     resp_produtos = session.get(
#                         url_api, params=params_produtos, timeout=30)
#                     resp_produtos.raise_for_status()
#                     dados_produtos = resp_produtos.json().get("dados", [])

#                     # Log para depuração
#                     logging.info(f"Dados de produtos: {dados_produtos[:5]}")

#                     # Cria dicionário para lookup rápido de produtos
#                     produtos_dict = {
#                         str(p.get('codigo', '')): p for p in dados_produtos if p.get('codigo')}

#                     # Combina estoque com detalhes dos produtos
#                     for item in dados_estoque:
#                         cod = str(item.get('produto', ''))
#                         estoque_str = str(
#                             item.get('estoque', '0,000')).replace(',', '.')
#                         try:
#                             estoque = float(estoque_str) if estoque_str.replace(
#                                 '.', '').replace('-', '').isdigit() else 0
#                         except ValueError:
#                             logging.warning(
#                                 f"Estoque inválido para produto {cod}: {item.get('estoque')}")
#                             estoque = 0

#                         if not exibir_zerados and estoque == 0:
#                             continue

#                         produto_info = produtos_dict.get(cod, {
#                             'grupo': 'DESCONHECIDO',
#                             'descricao': f"Produto {cod}",
#                             'fornecedor': '0'
#                         })

#                         produtos.append({
#                             'grupo': produto_info.get('grupo', 'DESCONHECIDO'),
#                             'codigo': cod,
#                             'descricao': produto_info.get('descricao', 'Sem descrição'),
#                             'estoque_loja': int(estoque) if estoque.is_integer() else round(estoque, 2),
#                             'negativo': estoque < 0,
#                             'saldo_positivo': estoque > 0
#                         })

#                 # Ordena por estoque (negativos primeiro, depois positivos)
#                 produtos.sort(key=lambda x: (
#                     x['negativo'], -x['saldo_positivo'], abs(x['estoque_loja'])), reverse=True)

#                 # Log para depuração
#                 logging.info(f"Produtos combinados: {produtos[:5]}")

#         except requests.exceptions.RequestException as e:
#             erro = f"Erro na conexão com a API: {str(e)}"
#         except Exception as e:
#             erro = f"Erro inesperado: {str(e)}"
#             logging.error(
#                 f"Erro em pda_ajuste_fornec_lojas: {str(e)}", exc_info=True)

#     # Paginação
#     total = len(produtos)
#     total_pages = (total + per_page - 1) // per_page if total > 0 else 1
#     start = (page - 1) * per_page
#     end = min(start + per_page, total)
#     produtos_paginados = produtos[start:end]

#     return render_template(
#         'pda_ajuste_fornec_lojas.html',
#         produtos=produtos_paginados,
#         erro=erro,
#         fornecedor=fornecedor,
#         grupo=grupo,
#         loja=loja,
#         exibir_zerados=exibir_zerados,
#         page=page,
#         total=total,
#         total_pages=total_pages,
#         per_page=per_page
#     )




@app.route('/monitoramento_pedidos')
@login_required
def monitoramento_pedidos():
    return render_template('monitoramento_pedidos.html')







# @app.route('/monitoramento_pedidos', methods=['GET'])
# @login_required
# def monitoramento_pedidos():
#     erro = None
#     lojas = []

#     try:
#         # Lista de filiais
#         filiais = [
#             {"codigo": "1", "nome": "Ponta Negra"},
#             {"codigo": "2", "nome": "Alecrim"},
#             {"codigo": "7", "nome": "SAC - Centro VI"},
#             {"codigo": "100", "nome": "Lagoa Nova"},
#             {"codigo": "121", "nome": "Norte Shopping"},
#             {"codigo": "122", "nome": "Parnamirim"},
#             {"codigo": "131", "nome": "ZN2"},
#             {"codigo": "137", "nome": "Macaíba"},
#             {"codigo": "140", "nome": "Maria Lacerda"},
#             {"codigo": "141", "nome": "Igapó"}
#         ]

#         # Simulando uma consulta à API para obter os dados dos pedidos
#         session = requests.Session()
#         retries = Retry(total=5, backoff_factor=1.0, status_forcelist=[
#                         500, 502, 503, 504], raise_on_status=False)
#         session.mount('http://', HTTPAdapter(max_retries=retries))

#         for filial in filiais:
#             loja_id = filial["codigo"]
#             # Consulta de pedidos por loja
#             url_pedidos = f"http://192.168.4.1:8480/ws/api_sacolao?operacao=pedido_loja&operador=2370&inicio=2025-05-30&final=2025-06-05&token=s4c0140_$b4tm4n_r0b1n_790883_000103&loja={999}"
#             resp_pedidos = session.get(url_pedidos, timeout=50)
#             resp_pedidos.raise_for_status()
#             dados_pedidos = resp_pedidos.json().get("dados", [])

#             # Processar os pedidos para calcular total e organizar por status
#             total_pedidos = 0
#             pedidos_por_status = {
#                 0: [],  # Aberto
#                 1: [],  # Acatado
#                 2: [],  # Separando
#                 3: [],  # Conferencia
#                 4: [],  # Despachado
#                 5: [],  # Recebido
#                 6: [],  # Cancelado
#                 8: []   # Em Andamento
#             }

#             # Organizar pedidos por status, filtrando pelo código da loja (destino)
#             for pedido in dados_pedidos:
#                 # Converter para string para comparar com loja_id
#                 destino = str(pedido.get("destino", ""))
#                 if destino == loja_id:  # Filtra apenas os pedidos da loja atual
#                     # Valor padrão 0 se status não existir
#                     status = pedido.get("status", 0)
#                     if status in pedidos_por_status:
#                         pedido_id = pedido.get("pedido", "Desconhecido")
#                         pedidos_por_status[status].append(pedido_id)
#                         total_pedidos += 1  # Incrementa o total apenas para pedidos da loja

#             lojas.append({
#                 "loja_id": loja_id,
#                 "nome": filial["nome"],
#                 "total_pedidos": total_pedidos,
#                 "pedidos_por_status": pedidos_por_status
#             })

#         if not lojas:
#             erro = "Nenhuma loja encontrada para exibir os pedidos."

#     except requests.Timeout:
#         erro = "Erro ao consultar a API: A requisição excedeu o tempo limite."
#     except requests.RequestException as e:
#         erro = f"Erro ao consultar a API: Falha na conexão com o servidor. {str(e)}"
#     except Exception as e:
#         logging.error(f"Erro inesperado: {e}")
#         erro = f"Ocorreu um erro inesperado: {str(e)}"

#     return render_template(
#         'monitoramento_pedidos.html',
#         lojas=lojas,
#         erro=erro
#     )



# DB_USER = os.getenv("DB_USER")
# DB_PASSWORD = os.getenv("DB_PASSWORD")
# DB_HOST = os.getenv("DB_HOST")

# DB_CONFIG = {}
# TABLE_MAPPING = {}
# lojas_codigos = ["1", "2", "7", "100",
#                  "121", "122", "131", "137", "140", "141"]
# tabelas_vendas_nomes = ["vendas_pn", "vendas_alecrim", "vendas_sac6", "vendas_ln",
#                         "vendas_shop", "vendas_parna", "vendas_zn2", "vendas_mac", "vendas_ml", "vendas_igapo"]

# for i, codigo in enumerate(lojas_codigos):
#     db_name = os.getenv(f"LOJA_{codigo}")
#     if db_name:
#         DB_CONFIG[codigo] = {
#             "uri": f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{db_name}"}
#         TABLE_MAPPING[codigo] = tabelas_vendas_nomes[i]

# # --- Função Auxiliar para Buscar Vendas ---


# def get_vendas_30d(engine, tabela_vendas, codigo_produto):
#     try:
#         data_inicio = datetime.now() - timedelta(days=30)
#         query = text(f"""
#             SELECT SUM(quantidade) 
#             FROM {tabela_vendas} 
#             WHERE codigo_produto = :cod_prod 
#             AND data_venda >= :data_inicio
#         """)
#         with engine.connect() as connection:
#             result = connection.execute(query, {"cod_prod": str(
#                 codigo_produto), "data_inicio": data_inicio}).scalar_one_or_none()
#         return int(result) if result is not None else 0
#     except Exception as e:
#         logging.error(
#             f"Erro ao buscar vendas para o produto {codigo_produto} na tabela {tabela_vendas}: {e}")
#         return 0


# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)


# @app.route('/dados_pedidos', methods=['GET'], endpoint='get_dados_pedidos_endpoint')
# @login_required
# def get_dados_pedidos():
#     loja = request.args.get('loja')
#     # Optional, for future filtering if needed
#     grupo = request.args.get('grupo')
#     erro = None
#     dados = {}

#     try:
#         # Lista de filiais
#         filiais = [
#             {"codigo": "1", "nome": "Ponta Negra"},
#             {"codigo": "2", "nome": "Alecrim"},
#             {"codigo": "7", "nome": "SAC - Centro VI"},
#             {"codigo": "100", "nome": "Lagoa Nova"},
#             {"codigo": "121", "nome": "Norte Shopping"},
#             {"codigo": "122", "nome": "Parnamirim"},
#             {"codigo": "131", "nome": "ZN2"},
#             {"codigo": "137", "nome": "Macaíba"},
#             {"codigo": "140", "nome": "Maria Lacerda"},
#             {"codigo": "141", "nome": "Igapó"}
#         ]

#         # Validate loja parameter
#         if not loja:
#             return jsonify({"erro": "Parâmetro 'loja' é obrigatório."}), 400

#         # Find the store in filiais
#         filial = next((f for f in filiais if f["codigo"] == loja), None)
#         if not filial:
#             return jsonify({"erro": f"Loja com código {loja} não encontrada."}), 404

#         # Set up the API request
#         session = requests.Session()
#         retries = Retry(total=5, backoff_factor=1.0, status_forcelist=[
#                         500, 502, 503, 504], raise_on_status=False)
#         session.mount('http://', HTTPAdapter(max_retries=retries))

#         # Calculate the date range: last 7 days from today
#         final_date = datetime.now().date()  # Current date (e.g., 2025-06-05)
#         # 6 days prior (e.g., 2025-05-29)
#         inicio_date = final_date - timedelta(days=6)
#         inicio_str = inicio_date.strftime('%Y-%m-%d')  # Format as YYYY-MM-DD
#         final_str = final_date.strftime('%Y-%m-%d')    # Format as YYYY-MM-DD
#         logger.debug(
#             f"Date range for API: inicio={inicio_str}, final={final_str}")

#         # Fetch orders from origem=999, filter by destino in the backend
#         url_pedidos = f"http://192.168.4.1:8480/ws/api_sacolao?operacao=pedido_loja&operador=2370&inicio={inicio_str}&final={final_str}&token=s4c0140_$b4tm4n_r0b1n_790883_000103&loja=999"
#         resp_pedidos = session.get(url_pedidos, timeout=50)
#         resp_pedidos.raise_for_status()
#         dados_pedidos = resp_pedidos.json().get("dados", [])
#         logger.debug(f"API Response for loja {loja}: {dados_pedidos}")

#         # Initialize order counts
#         total_pedidos = 0
#         pedidos_por_status = {
#             0: 0,  # Aberto
#             1: 0,  # Acatado
#             2: 0,  # Separando
#             3: 0,  # Conferência
#             4: 0,  # Despachado
#             5: 0,  # Recebido
#             6: 0,  # Cancelado
#             8: 0   # Em Andamento
#         }

#         # Filter orders by destino and categorize by status
#         loja_id = filial["codigo"]
#         for pedido in dados_pedidos:
#             destino = str(pedido.get("destino", ""))
#             logger.debug(
#                 f"Pedido - destino: {destino}, loja_id: {loja_id}, status: {pedido.get('status', 0)}")
#             if destino == loja_id:
#                 status = pedido.get("status", 0)
#                 if status in pedidos_por_status:
#                     pedidos_por_status[status] += 1
#                     total_pedidos += 1

#         # Prepare response data
#         dados = {
#             "nome_filial": filial["nome"],
#             "pedidos_por_status": pedidos_por_status,
#             "total_pedidos": total_pedidos
#         }
#         logger.debug(f"Dados preparados para loja {loja}: {dados}")

#     except requests.Timeout:
#         erro = "Erro ao consultar a API: A requisição excedeu o tempo limite."
#         logger.error(erro)
#         return jsonify({"erro": erro}), 504
#     except requests.RequestException as e:
#         erro = f"Erro ao consultar a API: Falha na conexão com o servidor. {str(e)}"
#         logger.error(erro)
#         return jsonify({"erro": erro}), 503
#     except Exception as e:
#         erro = f"Ocorreu um erro inesperado: {str(e)}"
#         logger.error(erro)
#         return jsonify({"erro": erro}), 500

#     return jsonify(dados)


# logging.basicConfig(level=logging.INFO)


# # Função auxiliar para fazer chamadas de API de forma robusta
# def fetch_api_data(url, session):
#     """Faz uma chamada de API e retorna os dados ou um dicionário de erro."""
#     try:
#         response = session.get(url, timeout=60)
#         response.raise_for_status()  # Lança um erro para respostas HTTP 4xx/5xx
#         return response.json().get("dados", [])
#     except requests.RequestException as e:
#         logging.error(f"Erro na requisição para {url}: {e}")
#         return {"erro": str(e), "url": url}
#     except ValueError:  # Erro se a resposta não for um JSON válido
#         logging.error(f"Não foi possível decodificar o JSON da URL: {url}")
#         return {"erro": "json_decode_error", "url": url}













# @app.route('/alerta_lojas', methods=['GET', 'POST'])
# @login_required
# def alerta_lojas():
#     # 1. Inicialização de todas as variáveis para garantir que sempre existam
#     produtos_faltando = []
#     erro = None
#     loja, grupo, fornecedor = None, None, None
#     saldo_min_cd, saldo_max_loja = None, None
#     dados_pizza, dados_ranking, fornecedores, rupturas = {}, [], [], []
#     total_skus_cd_com_saldo, total_skus_cd_com_saldo_sem_loja = 0, 0

#     if request.method == 'POST':
#         # 2. Coleta e validação dos dados do formulário
#         loja = request.form.get('loja', '').strip()
#         grupo = request.form.get('grupo', '').strip()
#         fornecedor = request.form.get('fornecedor', '').strip()
#         saldo_min_cd_str = request.form.get('saldo_min_cd', '').strip()
#         saldo_max_loja_str = request.form.get('saldo_max_loja', '').strip()

#         if not loja or not loja.isdigit():
#             erro = "Por favor, informe um número de loja válido."
#         else:
#             try:
#                 # Define valores padrão para os filtros de saldo se estiverem vazios
#                 if not saldo_min_cd_str and not saldo_max_loja_str:
#                     saldo_min_cd = 1.0
#                     saldo_max_loja = 0.0
#                 else:
#                     saldo_min_cd = float(
#                         saldo_min_cd_str) if saldo_min_cd_str else 0.0
#                     saldo_max_loja = float(
#                         saldo_max_loja_str) if saldo_max_loja_str else 0.0
#             except ValueError:
#                 erro = "Os valores de saldo devem ser numéricos."

#         # Se houver um erro de validação, para a execução e informa o usuário
#         if erro:
#             return render_template('alerta_lojas.html', erro=erro, loja=loja, grupo=grupo, fornecedor=fornecedor, saldo_min_cd=saldo_min_cd_str, saldo_max_loja=saldo_max_loja_str)

#         # 3. Bloco principal de busca e processamento de dados
#         try:
#             session = requests.Session()
#             retries = Retry(total=3, backoff_factor=0.5,
#                             status_forcelist=[500, 502, 503, 504])
#             session.mount('http://', HTTPAdapter(max_retries=retries))

#             base_url = "http://192.168.4.1:8480/ws/api_sacolao?operador=2370&token=s4c0140_$b4tm4n_r0b1n_790883_000103"

#             # Constrói as URLs para as chamadas de API
#             url_produtos = f"{base_url}&operacao=produtos&loja=999"
#             url_estoque_loja = f"{base_url}&operacao=estoque&loja={loja}"
#             url_estoque_cd = f"{base_url}&operacao=estoque&loja=999"

#             if grupo:
#                 url_produtos += f"&grupo={grupo}"
#                 url_estoque_loja += f"&grupo={grupo}"
#                 url_estoque_cd += f"&grupo={grupo}"

#             urls_para_buscar = [url_produtos, url_estoque_loja, url_estoque_cd]

#             # Executa as chamadas de API em paralelo para máxima velocidade
#             with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
#                 resultados_api = list(executor.map(
#                     lambda url: fetch_api_data(url, session), urls_para_buscar))

#             dados_produtos, dados_estoque, dados_estoque_cd = resultados_api

#             # Verifica se alguma das chamadas de API falhou
#             for res in resultados_api:
#                 if isinstance(res, dict) and 'erro' in res:
#                     raise requests.RequestException(
#                         f"Falha na API: {res['erro']} na URL {res.get('url', '')}")

#             # 4. Processamento completo dos dados recebidos
#             if fornecedor:
#                 dados_produtos = [
#                     p for p in dados_produtos
#                     if fornecedor.lower() in str(p.get('fornecedor', '')).lower()
#                 ]

#             produtos_dict = {str(p.get('codigo')): p for p in dados_produtos}
#             estoque_cd_dict = {str(p.get('produto')): float(
#                 p.get('estoque') or 0.0) for p in dados_estoque_cd}

#             total_skus_cd_com_saldo = sum(
#                 1 for cod in produtos_dict if estoque_cd_dict.get(cod, 0) > 0)
#             fornecedor_rupturas = {}

#             for item_loja in dados_estoque:
#                 cod = str(item_loja.get('produto'))
#                 if cod not in produtos_dict:
#                     continue

#                 est_loja = float(item_loja.get('estoque') or 0.0)
#                 est_cd = estoque_cd_dict.get(cod, 0.0)

#                 if est_cd >= saldo_min_cd and est_loja <= saldo_max_loja:
#                     produto_info = produtos_dict.get(cod, {})
#                     produto_fornecedor = produto_info.get(
#                         'fornecedor', 'Desconhecido')
#                     fornecedor_rupturas[produto_fornecedor] = fornecedor_rupturas.get(
#                         produto_fornecedor, 0) + 1

#                     produtos_faltando.append({
#                         'grupo': produto_info.get('grupo', ''),
#                         'codigo': cod,
#                         'descricao': produto_info.get('descricao', 'Sem descrição'),
#                         'fornecedor': produto_fornecedor,
#                         'estoque_cd': est_cd,
#                         'estoque_loja': est_loja,
#                         'preco': float(produto_info.get('preco') or 0.0),
#                         'custo': float(produto_info.get('custo') or 0.0)
#                     })

#             total_skus_cd_com_saldo_sem_loja = len(produtos_faltando)

#             # Cálculo dos dados para os gráficos
#             if total_skus_cd_com_saldo > 0:
#                 percentual_ruptura = (
#                     total_skus_cd_com_saldo_sem_loja / total_skus_cd_com_saldo * 100)
#                 dados_pizza = {
#                     'rupturas': round(percentual_ruptura, 2),
#                     'com_estoque': round(100 - percentual_ruptura, 2)
#                 }

#             dados_ranking_tuplas = sorted(
#                 fornecedor_rupturas.items(), key=lambda x: x[1], reverse=True)[:10]
#             dados_ranking = [{'fornecedor': f, 'rupturas': r}
#                              for f, r in dados_ranking_tuplas]
#             fornecedores = [item['fornecedor'] for item in dados_ranking]
#             rupturas = [item['rupturas'] for item in dados_ranking]

#             if not produtos_faltando:
#                 erro = "Nenhum produto em ruptura encontrado com os filtros aplicados."

#         except Exception as e:
#             logging.error(
#                 f"Erro inesperado no processamento: {e}", exc_info=True)
#             erro = f"Ocorreu um erro ao processar a sua solicitação. Detalhe: {e}"

#     # 5. Renderiza a página com todos os dados calculados (ou erros)
#     return render_template(
#         'alerta_lojas.html',
#         produtos=produtos_faltando,
#         erro=erro,
#         loja=loja,
#         grupo=grupo,
#         fornecedor=fornecedor,
#         saldo_min_cd=saldo_min_cd,
#         saldo_max_loja=saldo_max_loja,
#         dados_pizza=dados_pizza if dados_pizza else None,
#         dados_ranking=dados_ranking if dados_ranking else None,
#         fornecedores=fornecedores,
#         rupturas=rupturas,
#         total_skus_cd_com_saldo=total_skus_cd_com_saldo,
#         total_skus_cd_com_saldo_sem_loja=total_skus_cd_com_saldo_sem_loja
#     )






# # --- CONFIGURAÇÕES DO BANCO DE DADOS MySQL (PARA PRODUTOS) ---
# DB_CONFIG_PRODUCTS = {
#     'database': os.getenv('DB_NAME'),
#     'user': os.getenv('DB_USER'),
#     'password': os.getenv('DB_PASSWORD'),
#     'host': os.getenv('DB_HOST'),
#     'port': int(os.getenv('DB_PORT', '3306'))
# }

# # Verifica se todas as variáveis essenciais para o DB foram carregadas
# if not all([DB_CONFIG_PRODUCTS['database'], DB_CONFIG_PRODUCTS['user'],
#             DB_CONFIG_PRODUCTS['password'], DB_CONFIG_PRODUCTS['host']]):
#     logging.critical("Erro: Variáveis de ambiente do banco de dados (para produtos) não carregadas corretamente do .env")
#     # Em um ambiente de produção, é melhor parar o aplicativo aqui.
#     # raise ValueError("Credenciais do banco de dados ausentes ou incompletas para produtos.")

# # --- Pool de Conexões MySQL para Produtos ---
# try:
#     db_pool_products = mysql.connector.pooling.MySQLConnectionPool(
#         pool_name="alerta_lojas_products_pool",
#         pool_size=5, # Tamanho do pool para as conexões de produtos
#         **DB_CONFIG_PRODUCTS
#     )
#     logging.info("Pool de conexões MySQL para produtos criado com sucesso.")
# except Error as e:
#     logging.critical(f"Erro FATAL ao criar pool de conexões MySQL para produtos: {e}", exc_info=True)
#     db_pool_products = None # Garante que a variável seja None se falhar

# # --- Função auxiliar para buscar dados da API externa (para estoque) ---
# def fetch_api_data(url, session):
#     try:
#         response = session.get(url, timeout=10) # Adicionado timeout
#         response.raise_for_status() # Lança um erro para códigos de status ruins (4xx ou 5xx)
#         return response.json()
#     except requests.exceptions.RequestException as e:
#         logging.error(f"Erro ao buscar dados da API externa para URL {url}: {e}")
#         return {"erro": str(e), "url": url}
#     except ValueError as e: # Erro ao decodificar JSON (e.g., API retorna HTML ou texto)
#         logging.error(f"Erro ao decodificar JSON da API externa para URL {url}: {e}. Resposta: {response.text if 'response' in locals() else 'N/A'}")
#         return {"erro": "Erro ao decodificar resposta JSON da API externa", "url": url}


# @app.route('/alerta_lojas', methods=['GET', 'POST'])
# @login_required
# def alerta_lojas():
#     # 1. Inicialização de todas as variáveis para garantir que sempre existam
#     produtos_faltando = []
#     erro = None
#     loja, grupo, fornecedor = None, None, None
#     saldo_min_cd, saldo_max_loja = None, None
#     dados_pizza, dados_ranking, fornecedores_chart, rupturas_chart = {}, [], [], []
#     total_skus_cd_com_saldo, total_skus_cd_com_saldo_sem_loja = 0, 0

#     # Inicializa dados para evitar NameError no caso de um GET inicial ou erro
#     dados_produtos = []
#     dados_estoque_loja = []
#     dados_estoque_cd = []

#     if request.method == 'POST':
#         # 2. Coleta e validação dos dados do formulário
#         loja = request.form.get('loja', '').strip()
#         grupo = request.form.get('grupo', '').strip()
#         fornecedor = request.form.get('fornecedor', '').strip()
#         saldo_min_cd_str = request.form.get('saldo_min_cd', '').strip()
#         saldo_max_loja_str = request.form.get('saldo_max_loja', '').strip()

#         if not loja or not loja.isdigit():
#             erro = "Por favor, informe um número de loja válido."
#         else:
#             try:
#                 if not saldo_min_cd_str and not saldo_max_loja_str:
#                     saldo_min_cd = 1.0
#                     saldo_max_loja = 0.0
#                 else:
#                     saldo_min_cd = float(saldo_min_cd_str) if saldo_min_cd_str else 0.0
#                     saldo_max_loja = float(saldo_max_loja_str) if saldo_max_loja_str else 0.0
#             except ValueError:
#                 erro = "Os valores de saldo devem ser numéricos."

#         # Se houver um erro de validação do formulário, renderiza a página e para a execução.
#         if erro:
#             return render_template('alerta_lojas.html', erro=erro, loja=loja, grupo=grupo, fornecedor=fornecedor,
#                                    saldo_min_cd=saldo_min_cd_str, saldo_max_loja=saldo_max_loja_str)

#         # 3. Bloco principal de busca e processamento de dados

#         # --- BUSCA DE PRODUTOS DIRETAMENTE DO MYSQL ---
#         conn_mysql_products = None
#         try:
#             if not db_pool_products:
#                 raise Exception("Pool de conexões com o banco de dados de produtos não está disponível.")

#             conn_mysql_products = db_pool_products.get_connection()
#             cur_mysql_products = conn_mysql_products.cursor(dictionary=True)

#             query_products = """
#                 SELECT
#                     codigo,
#                     descricao,
#                     nome_fantasia AS fornecedor,
#                     grupo,
#                     preco,
#                     custo
#                 FROM
#                     produtos
#             """
#             params_products = []
#             if grupo:
#                 query_products += " WHERE grupo LIKE %s"
#                 params_products.append(f"%{grupo}%")
            
#             logging.info(f"Buscando produtos do MySQL: {query_products} com params: {params_products}")
#             cur_mysql_products.execute(query_products, params_products)
#             dados_produtos = [dict(row) for row in cur_mysql_products.fetchall()]
#             logging.info(f"Produtos do MySQL obtidos: {len(dados_produtos)} itens.")
            
#             cur_mysql_products.close()

#         except Error as e:
#             logging.error(f"Erro MySQL ao buscar produtos em alerta_lojas: {e}", exc_info=True)
#             erro = f"Erro ao conectar ou consultar o banco de dados de produtos: {e}"
#             dados_produtos = [] # Garante que dados_produtos esteja vazio em caso de erro
#         except Exception as e:
#             logging.error(f"Erro inesperado ao buscar produtos em alerta_lojas: {e}", exc_info=True)
#             erro = f"Ocorreu um erro inesperado ao buscar produtos: {e}"
#             dados_produtos = [] # Garante que dados_produtos esteja vazio em caso de erro
#         finally:
#             if conn_mysql_products and conn_mysql_products.is_connected():
#                 conn_mysql_products.close() # Retorna a conexão ao pool
#                 logging.info("Conexão MySQL de produtos retornada ao pool.")
        
#         # --- BUSCA DE ESTOQUE DA API EXTERNA ---
#         if not erro: # Só prossegue se não houve erro na busca de produtos
#             try:
#                 session = requests.Session()
#                 retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
#                 session.mount('http://', HTTPAdapter(max_retries=retries))

#                 base_url = "http://192.168.4.1:8480/ws/api_sacolao?operador=2370&token=s4c0140_$b4tm4n_r0b1n_790883_000103"

#                 # As URLs de estoque CHAMAM A API EXTERNA
#                 url_estoque_loja = f"{base_url}&operacao=estoque&loja={loja}"
#                 url_estoque_cd = f"{base_url}&operacao=estoque&loja=999"

#                 if grupo:
#                     # O filtro de grupo é passado para a API de estoque também
#                     url_estoque_loja += f"&grupo={grupo}"
#                     url_estoque_cd += f"&grupo={grupo}"

#                 urls_para_buscar_estoque = [url_estoque_loja, url_estoque_cd]

#                 logging.info(f"Buscando estoque da API externa: {urls_para_buscar_estoque}")
#                 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
#                     resultados_api_estoque = list(executor.map(
#                         lambda url: fetch_api_data(url, session), urls_para_buscar_estoque))

#                 # Extrai dados de estoque da loja e do CD dos resultados da API
#                 dados_estoque_loja, dados_estoque_cd = resultados_api_estoque

#                 # Verifica se alguma das chamadas da API de estoque falhou
#                 for res in resultados_api_estoque:
#                     if isinstance(res, dict) and 'erro' in res:
#                         raise requests.RequestException(
#                             f"Falha na API de Estoque: {res['erro']} na URL {res.get('url', '')}")

#             except requests.exceptions.RequestException as e:
#                 logging.error(f"Erro de comunicação com a API externa (estoque): {e}", exc_info=True)
#                 erro = f"Ocorreu um erro de comunicação com o sistema de estoque. Detalhe: {e}"
#                 # Em caso de erro na API de estoque, esvazia os dados para evitar problemas
#                 dados_estoque_loja = []
#                 dados_estoque_cd = []
#             except Exception as e:
#                 logging.error(f"Erro inesperado no processamento da API de estoque: {e}", exc_info=True)
#                 erro = f"Ocorreu um erro inesperado ao buscar estoque: {e}"
#                 dados_estoque_loja = []
#                 dados_estoque_cd = []

#         # --- Processamento dos dados recebidos (MESMA LÓGICA ANTERIOR) ---
#         if not erro: # Só prossegue se não houve erro nas buscas
#             if fornecedor: # Filtra os produtos obtidos do DB localmente se o fornecedor for preenchido
#                 dados_produtos = [
#                     p for p in dados_produtos
#                     if fornecedor.lower() in str(p.get('fornecedor', '')).lower()
#                 ]

#             produtos_dict = {str(p.get('codigo')): p for p in dados_produtos}
            
#             # Garante que dados_estoque_cd seja uma lista de dicionários antes de processar
#             if not isinstance(dados_estoque_cd, list):
#                 logging.error(f"dados_estoque_cd não é uma lista após API call: {dados_estoque_cd}. Tratando como vazio.")
#                 dados_estoque_cd = []

#             estoque_cd_dict = {str(item.get('produto')): float(item.get('estoque') or 0.0)
#                                for item in dados_estoque_cd}

#             total_skus_cd_com_saldo = sum(
#                 1 for cod in produtos_dict if estoque_cd_dict.get(cod, 0) > 0)
#             fornecedor_rupturas = {}

#             # Garante que dados_estoque_loja seja uma lista de dicionários antes de processar
#             if not isinstance(dados_estoque_loja, list):
#                 logging.error(f"dados_estoque_loja não é uma lista após API call: {dados_estoque_loja}. Tratando como vazio.")
#                 dados_estoque_loja = []

#             for item_loja in dados_estoque_loja:
#                 cod = str(item_loja.get('produto'))
#                 if cod not in produtos_dict:
#                     continue

#                 est_loja = float(item_loja.get('estoque') or 0.0)
#                 est_cd = estoque_cd_dict.get(cod, 0.0)

#                 if est_cd >= saldo_min_cd and est_loja <= saldo_max_loja:
#                     produto_info = produtos_dict.get(cod, {})
#                     produto_fornecedor = produto_info.get('fornecedor', 'Desconhecido')
#                     fornecedor_rupturas[produto_fornecedor] = fornecedor_rupturas.get(
#                         produto_fornecedor, 0) + 1

#                     produtos_faltando.append({
#                         'grupo': produto_info.get('grupo', ''),
#                         'codigo': cod,
#                         'descricao': produto_info.get('descricao', 'Sem descrição'),
#                         'fornecedor': produto_fornecedor,
#                         'estoque_cd': est_cd,
#                         'estoque_loja': est_loja,
#                         'preco': float(produto_info.get('preco') or 0.0),
#                         'custo': float(produto_info.get('custo') or 0.0)
#                     })

#             total_skus_cd_com_saldo_sem_loja = len(produtos_faltando)

#             # Cálculo dos dados para os gráficos
#             if total_skus_cd_com_saldo > 0:
#                 percentual_ruptura = (
#                     total_skus_cd_com_saldo_sem_loja / total_skus_cd_com_saldo * 100)
#                 dados_pizza = {
#                     'rupturas': round(percentual_ruptura, 2),
#                     'com_estoque': round(100 - percentual_ruptura, 2)
#                 }

#             dados_ranking_tuplas = sorted(
#                 fornecedor_rupturas.items(), key=lambda x: x[1], reverse=True)[:10]
#             dados_ranking = [{'fornecedor': f, 'rupturas': r}
#                              for f, r in dados_ranking_tuplas]
#             fornecedores_chart = [item['fornecedor'] for item in dados_ranking]
#             rupturas_chart = [item['rupturas'] for item in dados_ranking]

#             if not produtos_faltando and not erro: # Se não há produtos em ruptura E não houve erro
#                 erro = "Nenhum produto em ruptura encontrado com os filtros aplicados."
        
#     # Se o método for GET, as variáveis serão renderizadas com seus valores iniciais (vazios)
#     # ou se houve erro no POST, serão renderizadas com os dados do erro.
#     return render_template(
#         'alerta_lojas.html',
#         produtos=produtos_faltando,
#         erro=erro,
#         loja=loja,
#         grupo=grupo,
#         fornecedor=fornecedor,
#         saldo_min_cd=saldo_min_cd,
#         saldo_max_loja=saldo_max_loja,
#         dados_pizza=dados_pizza if dados_pizza else None,
#         dados_ranking=dados_ranking if dados_ranking else None,
#         fornecedores=fornecedores_chart,
#         rupturas=rupturas_chart,
#         total_skus_cd_com_saldo=total_skus_cd_com_saldo,
#         total_skus_cd_com_saldo_sem_loja=total_skus_cd_com_saldo_sem_loja
#     )




# # --- CONFIGURAÇÕES DO BANCO DE DADOS MySQL (PARA PRODUTOS) ---
# DB_CONFIG_PRODUCTS = {
#     'database': os.getenv('DB_NAME'),
#     'user': os.getenv('DB_USER'),
#     'password': os.getenv('DB_PASSWORD'),
#     'host': os.getenv('DB_HOST'),
#     'port': int(os.getenv('DB_PORT', '3306'))
# }

# if not all([DB_CONFIG_PRODUCTS['database'], DB_CONFIG_PRODUCTS['user'],
#             DB_CONFIG_PRODUCTS['password'], DB_CONFIG_PRODUCTS['host']]):
#     logging.critical("Erro: Variáveis de ambiente do banco de dados (para produtos) não carregadas corretamente do .env")

# try:
#     db_pool_products = mysql.connector.pooling.MySQLConnectionPool(
#         pool_name="alerta_lojas_products_pool",
#         pool_size=5,
#         **DB_CONFIG_PRODUCTS
#     )
#     logging.info("Pool de conexões MySQL para produtos criado com sucesso.")
# except Error as e:
#     logging.critical(f"Erro FATAL ao criar pool de conexões MySQL para produtos: {e}", exc_info=True)
#     db_pool_products = None

# # --- FUNÇÃO AUXILIAR PARA BUSCAR DADOS DA API EXTERNA (PARA ESTOQUE) ---
# def fetch_api_data(url, session):
#     try:
#         response = session.get(url, timeout=10)
#         response.raise_for_status() # Lança HTTPError para status 4xx/5xx

#         # Tenta decodificar o JSON
#         try:
#             data = response.json()
            
#             # *** NOVA LÓGICA AQUI: VERIFICA ERRO E MSG NO JSON RETORNADO ***
#             if isinstance(data, dict) and data.get('erro') is not None:
#                 # Se 'erro' estiver presente, mas 'msg' não, usa uma mensagem padrão
#                 error_message = data.get('msg', 'Erro desconhecido da API externa.')
#                 # Se 'erro' for True ou 1, a API está sinalizando um erro.
#                 # Se 'erro' for uma string, usá-la.
#                 if isinstance(data['erro'], bool) and data['erro']:
#                      return {"erro": f"API sinalizou erro: {error_message}", "url": url}
#                 elif isinstance(data['erro'], str):
#                      return {"erro": f"API sinalizou erro: {data['erro']} - {error_message}", "url": url}
#                 else: # Outro tipo de valor para 'erro'
#                      return {"erro": f"API sinalizou erro com valor inesperado: {data['erro']} - {error_message}", "url": url}
#             # FIM DA NOVA LÓGICA

#             return data # Se não for um dicionário de erro, retorna os dados normalmente

#         except requests.exceptions.JSONDecodeError: # Captura erro específico de JSON inválido
#             logging.error(f"Erro ao decodificar JSON para URL {url}. Resposta não-JSON: {response.text}")
#             return {"erro": f"Resposta inválida (não-JSON) da API. Conteúdo: {response.text[:200]}...", "url": url}

#     except requests.exceptions.RequestException as e: # Captura erros de conexão, timeout, HTTP 4xx/5xx
#         error_detail = str(e)
#         if hasattr(e, 'response') and e.response is not None:
#             # Tenta pegar a mensagem de erro do corpo da resposta HTTP
#             try:
#                 error_json = e.response.json()
#                 if isinstance(error_json, dict) and 'msg' in error_json:
#                     error_detail = f"{error_detail}. API Message: {error_json['msg']}"
#                 elif isinstance(error_json, dict) and 'erro' in error_json:
#                      error_detail = f"{error_detail}. API Error Field: {error_json['erro']}"
#             except requests.exceptions.JSONDecodeError:
#                 error_detail = f"{error_detail}. Resposta da API: {e.response.text[:200]}..."
            
#         logging.error(f"Erro de comunicação/HTTP com a API externa para URL {url}: {error_detail}")
#         return {"erro": f"Falha na comunicação com a API externa: {error_detail}", "url": url}


# @app.route('/alerta_lojas', methods=['GET', 'POST'])
# @login_required
# def alerta_lojas():
#     # 1. Inicialização de todas as variáveis para garantir que sempre existam
#     produtos_faltando = []
#     erro = None
#     loja, grupo, fornecedor = None, None, None
#     saldo_min_cd, saldo_max_loja = None, None
#     dados_pizza, dados_ranking, fornecedores_chart, rupturas_chart = {}, [], [], []
#     total_skus_cd_com_saldo, total_skus_cd_com_saldo_sem_loja = 0, 0

#     dados_produtos = []
#     dados_estoque_loja = []
#     dados_estoque_cd = []

#     if request.method == 'POST':
#         # ... (Coleta e validação dos dados do formulário - Sem mudanças) ...
#         loja = request.form.get('loja', '').strip()
#         grupo = request.form.get('grupo', '').strip()
#         fornecedor = request.form.get('fornecedor', '').strip()
#         saldo_min_cd_str = request.form.get('saldo_min_cd', '').strip()
#         saldo_max_loja_str = request.form.get('saldo_max_loja', '').strip()

#         if not loja or not loja.isdigit():
#             erro = "Por favor, informe um número de loja válido."
#         else:
#             try:
#                 if not saldo_min_cd_str and not saldo_max_loja_str:
#                     saldo_min_cd = 1.0
#                     saldo_max_loja = 0.0
#                 else:
#                     saldo_min_cd = float(saldo_min_cd_str) if saldo_min_cd_str else 0.0
#                     saldo_max_loja = float(saldo_max_loja_str) if saldo_max_loja_str else 0.0
#             except ValueError:
#                 erro = "Os valores de saldo devem ser numéricos."

#         if erro:
#             return render_template('alerta_lojas.html', erro=erro, loja=loja, grupo=grupo, fornecedor=fornecedor,
#                                    saldo_min_cd=saldo_min_cd_str, saldo_max_loja=saldo_max_loja_str)

#         # --- BUSCA DE PRODUTOS DIRETAMENTE DO MYSQL ---
#         conn_mysql_products = None
#         try:
#             if not db_pool_products:
#                 raise Exception("Pool de conexões com o banco de dados de produtos não está disponível.")

#             conn_mysql_products = db_pool_products.get_connection()
#             cur_mysql_products = conn_mysql_products.cursor(dictionary=True)

#             query_products = """
#                 SELECT
#                     codigo,
#                     descricao,
#                     nome_fantasia AS fornecedor,
#                     grupo,
#                     preco,
#                     custo
#                 FROM
#                     produtos
#             """
#             params_products = []
#             if grupo:
#                 query_products += " WHERE grupo LIKE %s"
#                 params_products.append(f"%{grupo}%")
            
#             logging.info(f"Buscando produtos do MySQL: {query_products} com params: {params_products}")
#             cur_mysql_products.execute(query_products, params_products)
#             dados_produtos = [dict(row) for row in cur_mysql_products.fetchall()]
#             logging.info(f"Produtos do MySQL obtidos: {len(dados_produtos)} itens.")
            
#             cur_mysql_products.close()

#         except Error as e:
#             logging.error(f"Erro MySQL ao buscar produtos em alerta_lojas: {e}", exc_info=True)
#             erro = f"Erro ao conectar ou consultar o banco de dados de produtos: {e}"
#             dados_produtos = []
#         except Exception as e:
#             logging.error(f"Erro inesperado ao buscar produtos em alerta_lojas: {e}", exc_info=True)
#             erro = f"Ocorreu um erro inesperado ao buscar produtos: {e}"
#             dados_produtos = []
#         finally:
#             if conn_mysql_products and conn_mysql_products.is_connected():
#                 conn_mysql_products.close()
#                 logging.info("Conexão MySQL de produtos retornada ao pool.")
        
#         # --- BUSCA DE ESTOQUE DA API EXTERNA ---
#         if not erro:
#             try:
#                 session = requests.Session()
#                 retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
#                 session.mount('http://', HTTPAdapter(max_retries=retries))

#                 base_url = "http://192.168.4.1:8480/ws/api_sacolao?operador=2370&token=s4c0140_$b4tm4n_r0b1n_790883_000103"

#                 url_estoque_loja = f"{base_url}&operacao=estoque&loja={loja}"
#                 url_estoque_cd = f"{base_url}&operacao=estoque&loja=999"

#                 if grupo:
#                     url_estoque_loja += f"&grupo={grupo}"
#                     url_estoque_cd += f"&grupo={grupo}"

#                 urls_para_buscar_estoque = [url_estoque_loja, url_estoque_cd]

#                 logging.info(f"Buscando estoque da API externa: {urls_para_buscar_estoque}")
#                 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
#                     resultados_api_estoque = list(executor.map(
#                         lambda url: fetch_api_data(url, session), urls_para_buscar_estoque))

#                 # Extrai dados de estoque da loja e do CD
#                 dados_estoque_loja, dados_estoque_cd = resultados_api_estoque

#                 # AQUI É ONDE VAMOS TRATAR O NOVO FORMATO DE ERRO
#                 for res in resultados_api_estoque:
#                     if isinstance(res, dict) and 'erro' in res:
#                         # Se res já é um dicionário de erro formatado pela fetch_api_data,
#                         # pegamos a mensagem diretamente e a passamos para 'erro'.
#                         # A raise_for_status() dentro de fetch_api_data já transformou erros HTTP em exceções,
#                         # e ValueErrors de JSON Decode já foram tratados lá também.
#                         # Então 'res' aqui DEVE ser o dicionário {"erro": "...", "url": "..."}
#                         erro = f"Falha na API de Estoque: {res['erro']} (URL: {res.get('url', 'N/A')})"
#                         # Quebra o loop assim que um erro é encontrado
#                         break 
                
#                 # Se um erro foi encontrado no loop acima, esvazie os dados de estoque
#                 # para que o processamento subsequente não falhe.
#                 if erro:
#                     dados_estoque_loja = []
#                     dados_estoque_cd = []

#             except requests.exceptions.RequestException as e:
#                 logging.error(f"Erro de comunicação com a API externa (estoque): {e}", exc_info=True)
#                 erro = f"Ocorreu um erro de comunicação com o sistema de estoque. Detalhe: {e}"
#                 dados_estoque_loja = []
#                 dados_estoque_cd = []
#             except Exception as e:
#                 logging.error(f"Erro inesperado no processamento da API de estoque: {e}", exc_info=True)
#                 erro = f"Ocorreu um erro inesperado ao buscar estoque: {e}"
#                 dados_estoque_loja = []
#                 dados_estoque_cd = []

#         # --- Processamento dos dados recebidos (MESMA LÓGICA ANTERIOR) ---
#         if not erro:
#             if fornecedor:
#                 dados_produtos = [
#                     p for p in dados_produtos
#                     if fornecedor.lower() in str(p.get('fornecedor', '')).lower()
#                 ]

#             produtos_dict = {str(p.get('codigo')): p for p in dados_produtos}
            
#             if not isinstance(dados_estoque_cd, list):
#                 logging.error(f"dados_estoque_cd não é uma lista após API call: {dados_estoque_cd}. Tratando como vazio.")
#                 dados_estoque_cd = []

#             estoque_cd_dict = {str(item.get('produto')): float(item.get('estoque') or 0.0)
#                                for item in dados_estoque_cd}

#             total_skus_cd_com_saldo = sum(
#                 1 for cod in produtos_dict if estoque_cd_dict.get(cod, 0) > 0)
#             fornecedor_rupturas = {}

#             if not isinstance(dados_estoque_loja, list):
#                 logging.error(f"dados_estoque_loja não é uma lista após API call: {dados_estoque_loja}. Tratando como vazio.")
#                 dados_estoque_loja = []

#             for item_loja in dados_estoque_loja:
#                 cod = str(item_loja.get('produto'))
#                 if cod not in produtos_dict:
#                     continue

#                 est_loja = float(item_loja.get('estoque') or 0.0)
#                 est_cd = estoque_cd_dict.get(cod, 0.0)

#                 if est_cd >= saldo_min_cd and est_loja <= saldo_max_loja:
#                     produto_info = produtos_dict.get(cod, {})
#                     produto_fornecedor = produto_info.get('fornecedor', 'Desconhecido')
#                     fornecedor_rupturas[produto_fornecedor] = fornecedor_rupturas.get(
#                         produto_fornecedor, 0) + 1

#                     produtos_faltando.append({
#                         'grupo': produto_info.get('grupo', ''),
#                         'codigo': cod,
#                         'descricao': produto_info.get('descricao', 'Sem descrição'),
#                         'fornecedor': produto_fornecedor,
#                         'estoque_cd': est_cd,
#                         'estoque_loja': est_loja,
#                         'preco': float(produto_info.get('preco') or 0.0),
#                         'custo': float(produto_info.get('custo') or 0.0)
#                     })

#             total_skus_cd_com_saldo_sem_loja = len(produtos_faltando)

#             if total_skus_cd_com_saldo > 0:
#                 percentual_ruptura = (
#                     total_skus_cd_com_saldo_sem_loja / total_skus_cd_com_saldo * 100)
#                 dados_pizza = {
#                     'rupturas': round(percentual_ruptura, 2),
#                     'com_estoque': round(100 - percentual_ruptura, 2)
#                 }

#             dados_ranking_tuplas = sorted(
#                 fornecedor_rupturas.items(), key=lambda x: x[1], reverse=True)[:10]
#             dados_ranking = [{'fornecedor': f, 'rupturas': r}
#                              for f, r in dados_ranking_tuplas]
#             fornecedores_chart = [item['fornecedor'] for item in dados_ranking]
#             rupturas_chart = [item['rupturas'] for item in dados_ranking]

#             if not produtos_faltando and not erro:
#                 erro = "Nenhum produto em ruptura encontrado com os filtros aplicados."
        
#     return render_template(
#         'alerta_lojas.html',
#         produtos=produtos_faltando,
#         erro=erro,
#         loja=loja,
#         grupo=grupo,
#         fornecedor=fornecedor,
#         saldo_min_cd=saldo_min_cd,
#         saldo_max_loja=saldo_max_loja,
#         dados_pizza=dados_pizza if dados_pizza else None,
#         dados_ranking=dados_ranking if dados_ranking else None,
#         fornecedores=fornecedores_chart,
#         rupturas=rupturas_chart,
#         total_skus_cd_com_saldo=total_skus_cd_com_saldo,
#         total_skus_cd_com_saldo_sem_loja=total_skus_cd_com_saldo_sem_loja
#     )











# # --- FUNÇÃO AUXILIAR PARA BUSCAR DADOS DA API EXTERNA (PARA ESTOQUE) ---
# def fetch_api_data(url, session):
#     try:
#         response = session.get(url, timeout=50)
#         response.raise_for_status() # Lança HTTPError para status 4xx/5xx (e.g., 404, 500)

#         # Tenta decodificar o JSON da resposta
#         try:
#             data = response.json()
            
#             # *** MENSAGEM EXATA DA API ***
#             if isinstance(data, dict):
#                 # Se 'erro' for explicitamente true E 'msg' existir, use 'msg'
#                 if data.get('erro') is True and 'msg' in data:
#                     logging.warning(f"API retornou erro com mensagem específica: {data['msg']} para URL: {url}")
#                     return {"erro": data['msg'], "url": url}
#                 # Se 'erro' for uma string não vazia E 'msg' existir, ainda priorize 'msg'
#                 elif isinstance(data.get('erro'), str) and data.get('erro').strip() != '' and 'msg' in data:
#                      logging.warning(f"API retornou erro com campo 'erro' e 'msg': {data['msg']} para URL: {url}")
#                      return {"erro": data['msg'], "url": url}
#                 # Se 'erro' for True mas 'msg' não existir, ou 'erro' é uma string vazia
#                 elif data.get('erro') is not None:
#                     # Fallback para o valor de 'erro' se 'msg' não estiver presente
#                     error_message = data.get('erro', 'Erro desconhecido da API externa.')
#                     logging.warning(f"API retornou erro sem 'msg' explícita ou com 'erro' genérico: {error_message} para URL: {url}")
#                     return {"erro": error_message, "url": url}
            
#             return data # Se não for um dicionário de erro, retorna os dados normalmente

#         except requests.exceptions.JSONDecodeError: # Captura erro específico de JSON inválido
#             logging.error(f"Erro ao decodificar JSON para URL {url}. Resposta não-JSON: {response.text}")
#             # Retorna o texto bruto da resposta se não for JSON válido
#             return {"erro": f"Resposta inválida (não-JSON) da API: {response.text[:200]}...", "url": url}

#     except requests.exceptions.RequestException as e: # Captura erros de conexão, timeout, HTTP 4xx/5xx
#         error_detail = str(e)
#         if hasattr(e, 'response') and e.response is not None:
#             # Tenta pegar a mensagem de erro do corpo da resposta HTTP, se for JSON
#             try:
#                 error_json = e.response.json()
#                 if isinstance(error_json, dict) and 'msg' in error_json:
#                     error_detail = error_json['msg'] # Usa a 'msg' da resposta HTTP de erro
#                 elif isinstance(error_json, dict) and 'erro' in error_json:
#                      error_detail = error_json['erro'] # Se 'erro' é a mensagem principal
#                 elif hasattr(e.response, 'text'):
#                      error_detail = e.response.text[:200] # Fallback para texto puro da resposta
#             except requests.exceptions.JSONDecodeError:
#                 error_detail = f"Resposta da API: {e.response.text[:200]}..."
            
#         logging.error(f"Erro de comunicação/HTTP com a API externa para URL {url}: {error_detail}")
#         return {"erro": f"Falha na comunicação com a API externa: {error_detail}", "url": url}




# # --- FUNÇÃO AUXILIAR PARA BUSCAR DADOS DA API EXTERNA (PARA ESTOQUE) ---
# def fetch_api_data(url, session):
#     try:
#         response = session.get(url, timeout=50)
#         response.raise_for_status()

#         try:
#             data = response.json()
            
#             # *** VERIFICA SE O ESTOQUE ESTÁ NA CHAVE 'dados' ***
#             if isinstance(data, dict):
#                 # Se a API externa retorna um erro de negócio no formato {"erro": true, "msg": "..."}
#                 if data.get('erro') is True and 'msg' in data:
#                     logging.warning(f"API retornou erro de negócio: {data['msg']} para URL: {url}")
#                     return {"erro": data['msg'], "url": url}
#                 # Se a API retorna sucesso mas os dados de estoque estão em 'dados'
#                 elif 'dados' in data and isinstance(data['dados'], list):
#                     return data['dados'] # <-- RETORNA A LISTA DE DADOS DIRETAMENTE!
#                 # Fallback se 'dados' não estiver presente ou não for lista, mas 'erro' não sinaliza problema explícito
#                 elif data.get('erro') is False:
#                     logging.warning(f"API retornou sucesso mas sem lista 'dados' ou formato inesperado: {data} para URL: {url}")
#                     return [] # Retorna lista vazia se não encontrar os dados de estoque esperados
                
#             # Se 'data' não é um dicionário ou não tem 'erro'/'dados' como esperado, logar e tratar como erro
#             logging.error(f"Formato de resposta inesperado da API: {data} para URL: {url}")
#             return {"erro": f"Formato inesperado da API: {str(data)[:200]}...", "url": url}

#         except requests.exceptions.JSONDecodeError:
#             logging.error(f"Erro ao decodificar JSON para URL {url}. Resposta não-JSON: {response.text}")
#             return {"erro": f"Resposta inválida (não-JSON) da API: {response.text[:200]}...", "url": url}

#     except requests.exceptions.RequestException as e:
#         error_detail = str(e)
#         if hasattr(e, 'response') and e.response is not None:
#             try:
#                 error_json = e.response.json()
#                 if isinstance(error_json, dict) and 'msg' in error_json:
#                     error_detail = error_json['msg']
#                 elif isinstance(error_json, dict) and 'erro' in error_json:
#                      error_detail = error_json['erro']
#                 elif hasattr(e.response, 'text'):
#                      error_detail = e.response.text[:200]
#             except requests.exceptions.JSONDecodeError:
#                 error_detail = f"Resposta da API: {e.response.text[:200]}..."
            
#         logging.error(f"Erro de comunicação/HTTP com a API externa para URL {url}: {error_detail}")
#         return {"erro": f"Falha na comunicação com a API externa: {error_detail}", "url": url}




# @app.route('/alerta_lojas', methods=['GET', 'POST'])
# @login_required
# def alerta_lojas():
#     # 1. Inicialização de todas as variáveis para garantir que sempre existam
#     produtos_faltando = []
#     erro = None
#     loja, grupo, fornecedor = None, None, None
#     saldo_min_cd, saldo_max_loja = None, None
#     dados_pizza, dados_ranking, fornecedores_chart, rupturas_chart = {}, [], [], []
#     total_skus_cd_com_saldo, total_skus_cd_com_saldo_sem_loja = 0, 0

#     dados_produtos = []
#     dados_estoque_loja = []
#     dados_estoque_cd = []

#     if request.method == 'POST':
#         # 2. Coleta e validação dos dados do formulário
#         loja = request.form.get('loja', '').strip()
#         grupo = request.form.get('grupo', '').strip()
#         fornecedor = request.form.get('fornecedor', '').strip()
#         saldo_min_cd_str = request.form.get('saldo_min_cd', '').strip()
#         saldo_max_loja_str = request.form.get('saldo_max_loja', '').strip()

#         if not loja or not loja.isdigit():
#             erro = "Por favor, informe um número de loja válido."
#         else:
#             try:
#                 if not saldo_min_cd_str and not saldo_max_loja_str:
#                     saldo_min_cd = 1.0
#                     saldo_max_loja = 0.0
#                 else:
#                     saldo_min_cd = float(saldo_min_cd_str) if saldo_min_cd_str else 0.0
#                     saldo_max_loja = float(saldo_max_loja_str) if saldo_max_loja_str else 0.0
#             except ValueError:
#                 erro = "Os valores de saldo devem ser numéricos."

#         if erro:
#             return render_template('alerta_lojas.html', erro=erro, loja=loja, grupo=grupo, fornecedor=fornecedor,
#                                    saldo_min_cd=saldo_min_cd_str, saldo_max_loja=saldo_max_loja_str)

#         # --- BUSCA DE PRODUTOS DIRETAMENTE DO MYSQL ---
#         conn_mysql_products = None
#         try:
#             if not db_pool_products:
#                 raise Exception("Pool de conexões com o banco de dados de produtos não está disponível.")

#             conn_mysql_products = db_pool_products.get_connection()
#             cur_mysql_products = conn_mysql_products.cursor(dictionary=True)

#             query_products = """
#                 SELECT
#                     codigo,
#                     descricao,
#                     nome_fantasia AS fornecedor,
#                     grupo,
#                     preco,
#                     custo
#                 FROM
#                     produtos
#             """
#             params_products = []
#             if grupo:
#                 query_products += " WHERE grupo LIKE %s"
#                 params_products.append(f"%{grupo}%")
            
#             logging.info(f"Buscando produtos do MySQL: {query_products} com params: {params_products}")
#             cur_mysql_products.execute(query_products, params_products)
#             dados_produtos = [dict(row) for row in cur_mysql_products.fetchall()]
#             logging.info(f"Produtos do MySQL obtidos: {len(dados_produtos)} itens.")
            
#             cur_mysql_products.close()

#         except Error as e:
#             logging.error(f"Erro MySQL ao buscar produtos em alerta_lojas: {e}", exc_info=True)
#             erro = f"Erro ao conectar ou consultar o banco de dados de produtos: {e}"
#             dados_produtos = []
#         except Exception as e:
#             logging.error(f"Erro inesperado ao buscar produtos em alerta_lojas: {e}", exc_info=True)
#             erro = f"Ocorreu um erro inesperado ao buscar produtos: {e}"
#             dados_produtos = []
#         finally:
#             if conn_mysql_products and conn_mysql_products.is_connected():
#                 conn_mysql_products.close()
#                 logging.info("Conexão MySQL de produtos retornada ao pool.")
        
#         # --- BUSCA DE ESTOQUE DA API EXTERNA ---
#         if not erro:
#             try:
#                 session = requests.Session()
#                 retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
#                 session.mount('http://', HTTPAdapter(max_retries=retries))

#                 base_url = "http://192.168.4.1:8480/ws/api_sacolao?operador=2370&token=s4c0140_$b4tm4n_r0b1n_790883_000103"

#                 url_estoque_loja = f"{base_url}&operacao=estoque&loja={loja}"
#                 url_estoque_cd = f"{base_url}&operacao=estoque&loja=999"

#                 if grupo:
#                     url_estoque_loja += f"&grupo={grupo}"
#                     url_estoque_cd += f"&grupo={grupo}"

#                 urls_para_buscar_estoque = [url_estoque_loja, url_estoque_cd]

#                 logging.info(f"Buscando estoque da API externa: {urls_para_buscar_estoque}")
#                 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
#                     resultados_api_estoque = list(executor.map(
#                         lambda url: fetch_api_data(url, session), urls_para_buscar_estoque))

#                 # Extrai dados de estoque da loja e do CD
#                 dados_estoque_loja, dados_estoque_cd = resultados_api_estoque

#                 # Processa os resultados para verificar erros da API
#                 for res in resultados_api_estoque:
#                     if isinstance(res, dict) and 'erro' in res:
#                         erro = res['erro']
#                         break # Para no primeiro erro encontrado
                
#                 # Se um erro foi encontrado no loop acima, esvazie os dados de estoque
#                 if erro:
#                     dados_estoque_loja = []
#                     dados_estoque_cd = []

#             except requests.exceptions.RequestException as e:
#                 logging.error(f"Erro de comunicação com a API externa (estoque): {e}", exc_info=True)
#                 erro = f"Ocorreu um erro de comunicação com o sistema de estoque. Detalhe: {e}"
#                 dados_estoque_loja = []
#                 dados_estoque_cd = []
#             except Exception as e:
#                 logging.error(f"Erro inesperado no processamento da API de estoque: {e}", exc_info=True)
#                 erro = f"Ocorreu um erro inesperado ao buscar estoque: {e}"
#                 dados_estoque_loja = []
#                 dados_estoque_cd = []

#         # --- Processamento dos dados recebidos ---
#         if not erro:
#             if fornecedor:
#                 dados_produtos = [
#                     p for p in dados_produtos
#                     if fornecedor.lower() in str(p.get('fornecedor', '')).lower()
#                 ]

#             produtos_dict = {str(p.get('codigo')): p for p in dados_produtos}
            
#             if not isinstance(dados_estoque_cd, list):
#                 logging.error(f"dados_estoque_cd não é uma lista após API call: {dados_estoque_cd}. Tratando como vazio.")
#                 dados_estoque_cd = []

#             estoque_cd_dict = {str(item.get('produto')): float(item.get('estoque') or 0.0)
#                                for item in dados_estoque_cd}

#             total_skus_cd_com_saldo = sum(
#                 1 for cod in produtos_dict if estoque_cd_dict.get(cod, 0) > 0)
#             fornecedor_rupturas = {}

#             if not isinstance(dados_estoque_loja, list):
#                 logging.error(f"dados_estoque_loja não é uma lista após API call: {dados_estoque_loja}. Tratando como vazio.")
#                 dados_estoque_loja = []

#             for item_loja in dados_estoque_loja:
#                 cod = str(item_loja.get('produto'))
#                 if cod not in produtos_dict:
#                     continue

#                 est_loja = float(item_loja.get('estoque') or 0.0)
#                 est_cd = estoque_cd_dict.get(cod, 0.0)

#                 if est_cd >= saldo_min_cd and est_loja <= saldo_max_loja:
#                     produto_info = produtos_dict.get(cod, {})
#                     produto_fornecedor = produto_info.get('fornecedor', 'Desconhecido')
#                     fornecedor_rupturas[produto_fornecedor] = fornecedor_rupturas.get(
#                         produto_fornecedor, 0) + 1

#                     produtos_faltando.append({
#                         'grupo': produto_info.get('grupo', ''),
#                         'codigo': cod,
#                         'descricao': produto_info.get('descricao', 'Sem descrição'),
#                         'fornecedor': produto_fornecedor,
#                         'estoque_cd': est_cd,
#                         'estoque_loja': est_loja,
#                         'preco': float(produto_info.get('preco') or 0.0),
#                         'custo': float(produto_info.get('custo') or 0.0)
#                     })

#             total_skus_cd_com_saldo_sem_loja = len(produtos_faltando)

#             if total_skus_cd_com_saldo > 0:
#                 percentual_ruptura = (
#                     total_skus_cd_com_saldo_sem_loja / total_skus_cd_com_saldo * 100)
#                 dados_pizza = {
#                     'rupturas': round(percentual_ruptura, 2),
#                     'com_estoque': round(100 - percentual_ruptura, 2)
#                 }

#             dados_ranking_tuplas = sorted(
#                 fornecedor_rupturas.items(), key=lambda x: x[1], reverse=True)[:10]
#             dados_ranking = [{'fornecedor': f, 'rupturas': r}
#                              for f, r in dados_ranking_tuplas]
#             fornecedores_chart = [item['fornecedor'] for item in dados_ranking]
#             rupturas_chart = [item['rupturas'] for item in dados_ranking]

#             if not produtos_faltando and not erro:
#                 erro = "Nenhum produto em ruptura encontrado com os filtros aplicados."
        
#     return render_template(
#         'alerta_lojas.html',
#         produtos=produtos_faltando,
#         erro=erro,
#         loja=loja,
#         grupo=grupo,
#         fornecedor=fornecedor,
#         saldo_min_cd=saldo_min_cd,
#         saldo_max_loja=saldo_max_loja,
#         dados_pizza=dados_pizza if dados_pizza else None,
#         dados_ranking=dados_ranking if dados_ranking else None,
#         fornecedores=fornecedores_chart,
#         rupturas=rupturas_chart,
#         total_skus_cd_com_saldo=total_skus_cd_com_saldo,
#         total_skus_cd_com_saldo_sem_loja=total_skus_cd_com_saldo_sem_loja
#     )








# # --- CONFIGURAÇÕES DO BANCO DE DADOS MySQL (PARA PRODUTOS) ---
# DB_CONFIG_PRODUCTS = {
#     'database': os.getenv('DB_NAME'),
#     'user': os.getenv('DB_USER'),
#     'password': os.getenv('DB_PASSWORD'),
#     'host': os.getenv('DB_HOST'),
#     'port': int(os.getenv('DB_PORT', '3306'))
# }

# if not all([DB_CONFIG_PRODUCTS['database'], DB_CONFIG_PRODUCTS['user'],
#             DB_CONFIG_PRODUCTS['password'], DB_CONFIG_PRODUCTS['host']]):
#     logging.critical("Erro: Variáveis de ambiente do banco de dados (para produtos) não carregadas corretamente do .env")

# try:
#     db_pool_products = mysql.connector.pooling.MySQLConnectionPool(
#         pool_name="alerta_lojas_products_pool",
#         pool_size=5,
#         **DB_CONFIG_PRODUCTS
#     )
#     logging.info("Pool de conexões MySQL para produtos criado com sucesso.")
# except Error as e:
#     logging.critical(f"Erro FATAL ao criar pool de conexões MySQL para produtos: {e}", exc_info=True)
#     db_pool_products = None




# @app.route('/alerta_lojas', methods=['GET', 'POST'])
# @login_required
# def alerta_lojas():
#     # 1. Inicialização de todas as variáveis para garantir que sempre existam
#     produtos_faltando = []
#     erro = None
#     loja_id_form, grupo_form, fornecedor_form = None, None, None 
#     saldo_min_cd, saldo_max_loja = None, None
#     dados_pizza, dados_ranking, fornecedores_chart, rupturas_chart = {}, [], [], []
#     total_skus_cd_com_saldo, total_skus_cd_com_saldo_sem_loja = 0, 0

#     dados_produtos = []
#     dados_estoque_loja = [] # do DB
#     dados_estoque_cd = []   #  do DB

#     if request.method == 'POST':
#         # 2. Coleta e validação dos dados do formulário
#         loja_id_form = request.form.get('loja', '').strip() # ID da loja do formulário
#         grupo_form = request.form.get('grupo', '').strip()
#         fornecedor_form = request.form.get('fornecedor', '').strip()
#         saldo_min_cd_str = request.form.get('saldo_min_cd', '').strip()
#         saldo_max_loja_str = request.form.get('saldo_max_loja', '').strip()

#         if not loja_id_form or not loja_id_form.isdigit():
#             erro = "Por favor, informe um número de loja válido."
#         else:
#             try:
#                 if not saldo_min_cd_str and not saldo_max_loja_str:
#                     saldo_min_cd = 1.0
#                     saldo_max_loja = 0.0
#                 else:
#                     saldo_min_cd = float(saldo_min_cd_str) if saldo_min_cd_str else 0.0
#                     saldo_max_loja = float(saldo_max_loja_str) if saldo_max_loja_str else 0.0
#             except ValueError:
#                 erro = "Os valores de saldo devem ser numéricos."

#         if erro:
#             return render_template('alerta_lojas.html', erro=erro, loja=loja_id_form, grupo=grupo_form, fornecedor=fornecedor_form,
#                                    saldo_min_cd=saldo_min_cd_str, saldo_max_loja=saldo_max_loja_str)

#         # --- BUSCA DE DADOS DIRETAMENTE DO BANCO DE DADOS MySQL ---
#         conn_mysql = None # única conexão do pool para ambas as tabelas
#         try:
#             if not db_pool_products: # db_pool_products é o pool para estoque_db
#                 raise Exception("Pool de conexões com o banco de dados não está disponível.")

#             conn_mysql = db_pool_products.get_connection()
#             cur_mysql = conn_mysql.cursor(dictionary=True)

#             # 1. BUSCA DE PRODUTOS (incluindo saldo do CD - assumindo coluna 'saldo' na tabela 'produtos')
#             query_products = """
#                 SELECT
#                     codigo,
#                     descricao,
#                     nu_fornecedor AS fornecedor,
#                     grupo,
#                     preco,
#                     custo,
#                     saldo 
#                 FROM
#                     produtos
#             """
#             params_products = []
#             if grupo_form:
#                 query_products += " WHERE grupo = %s" 
#                 params_products.append(grupo_form) 
            
#             logging.info(f"Buscando produtos do MySQL: {query_products} com params: {params_products}")
#             cur_mysql.execute(query_products, params_products)
            
#             dados_produtos = []
#             for row in cur_mysql.fetchall():
#                 product_data = dict(row)
#                 product_data['fornecedor'] = str(product_data.get('fornecedor') or 'Desconhecido')
#                 dados_produtos.append(product_data)

#             logging.info(f"Produtos do MySQL obtidos: {len(dados_produtos)} itens.")
            
#             # Mapeia o saldo do CD para cada produto
#             estoque_cd_dict = {str(p.get('codigo')): float(p.get('saldo') or 0.0)
#                                for p in dados_produtos}


#             # 2. BUSCA DE ESTOQUE DA LOJA (da tabela stq_lojas)
#             query_estoque_loja = """
#                 SELECT
#                     codigo,    -- Código do PRODUTO na stq_lojas
#                     saldo
#                 FROM
#                     stq_lojas
#                 WHERE
#                     tag_lojas = %s
#             """
#             params_estoque_loja = [str(loja_id_form)] # Converte para string 

#             if grupo_form: # Se o grupo também for um filtro em stq_lojas
#                 query_estoque_loja += " AND grupo = %s" 
#                 params_estoque_loja.append(grupo_form) 
            
#             logging.info(f"Buscando estoque da loja {loja_id_form} do MySQL: {query_estoque_loja} com params: {params_estoque_loja}")
#             cur_mysql.execute(query_estoque_loja, params_estoque_loja)
#             dados_estoque_loja_raw = cur_mysql.fetchall() # Obtém os resultados
            
#             # Converte para um dicionário para fácil acesso: {codigo_produto: saldo}
#             estoque_loja_dict = {str(item.get('codigo')): float(item.get('saldo') or 0.0)
#                                  for item in dados_estoque_loja_raw}
#             logging.info(f"Estoque da loja {loja_id_form} obtido: {len(estoque_loja_dict)} itens.")

#             cur_mysql.close()

#         except Error as e:
#             logging.error(f"Erro MySQL ao buscar dados em alerta_lojas: {e}", exc_info=True)
#             erro = f"Erro ao conectar ou consultar o banco de dados: {e}"
#             dados_produtos = []
#             estoque_cd_dict = {}
#             estoque_loja_dict = {}
#         except Exception as e:
#             logging.error(f"Erro inesperado ao buscar dados em alerta_lojas: {e}", exc_info=True)
#             erro = f"Ocorreu um erro inesperado ao buscar dados: {e}"
#             dados_produtos = []
#             estoque_cd_dict = {}
#             estoque_loja_dict = {}
#         finally:
#             if conn_mysql and conn_mysql.is_connected():
#                 conn_mysql.close()
#                 logging.info("Conexão MySQL retornada ao pool.")
        
#         # --- Processamento dos dados recebidos 
#         if not erro:
#             if fornecedor_form:
#                 dados_produtos = [
#                     p for p in dados_produtos
#                     if fornecedor_form.lower() in str(p.get('fornecedor', '')).lower()
#                 ]

#             produtos_dict = {str(p.get('codigo')): p for p in dados_produtos}
            
#             total_skus_cd_com_saldo = sum(
#                 1 for cod in produtos_dict if estoque_cd_dict.get(cod, 0) > 0)
#             fornecedor_rupturas = {}

#             # Itera sobre os produtos (que já contêm o saldo do CD)
#             for produto_info in dados_produtos:
#                 cod = str(produto_info.get('codigo'))
#                 est_loja = estoque_loja_dict.get(cod, 0.0) # Busca o saldo da loja do dicionário
#                 est_cd = estoque_cd_dict.get(cod, 0.0)     # Busca o saldo do CD do dicionário (já mapeado)

#                 if est_cd >= saldo_min_cd and est_loja <= saldo_max_loja:
#                     produto_fornecedor = produto_info.get('fornecedor', 'Desconhecido') 
#                     fornecedor_rupturas[produto_fornecedor] = fornecedor_rupturas.get(
#                         produto_fornecedor, 0) + 1

#                     produtos_faltando.append({
#                         'grupo': produto_info.get('grupo', ''),
#                         'codigo': cod,
#                         'descricao': produto_info.get('descricao', 'Sem descrição'),
#                         'fornecedor': produto_fornecedor,
#                         'estoque_cd': est_cd,
#                         'estoque_loja': est_loja,
#                         'preco': float(produto_info.get('preco') or 0.0),
#                         'custo': float(produto_info.get('custo') or 0.0)
#                     })

#             total_skus_cd_com_saldo_sem_loja = len(produtos_faltando)

#             if total_skus_cd_com_saldo > 0:
#                 percentual_ruptura = (
#                     total_skus_cd_com_saldo_sem_loja / total_skus_cd_com_saldo * 100)
#                 dados_pizza = {
#                     'rupturas': round(percentual_ruptura, 2),
#                     'com_estoque': round(100 - percentual_ruptura, 2)
#                 }

#             dados_ranking_tuplas = sorted(
#                 fornecedor_rupturas.items(), key=lambda x: x[1], reverse=True)[:10]
#             dados_ranking = [{'fornecedor': f, 'rupturas': r}
#                              for f, r in dados_ranking_tuplas]
#             fornecedores_chart = [item['fornecedor'] for item in dados_ranking]
#             rupturas_chart = [item['rupturas'] for item in dados_ranking]

#             if not produtos_faltando and not erro:
#                 erro = "Nenhum produto em ruptura encontrado com os filtros aplicados."
        
#     return render_template(
#         'alerta_lojas.html',
#         produtos=produtos_faltando,
#         erro=erro,
#         loja=loja_id_form,
#         grupo=grupo_form,
#         fornecedor=fornecedor_form,
#         saldo_min_cd=saldo_min_cd,
#         saldo_max_loja=saldo_max_loja,
#         dados_pizza=dados_pizza if dados_pizza else None,
#         dados_ranking=dados_ranking if dados_ranking else None,
#         fornecedores=fornecedores_chart,
#         rupturas=rupturas_chart,
#         total_skus_cd_com_saldo=total_skus_cd_com_saldo,
#         total_skus_cd_com_saldo_sem_loja=total_skus_cd_com_saldo_sem_loja
#     )




# --- CONFIGURAÇÕES DO BANCO DE DADOS MySQL (PARA PRODUTOS) ---
DB_CONFIG_PRODUCTS = {
    'database': os.getenv('DB_NAME_PRODUCTS', 'estoque_db'), # Assuming 'estoque_db' for products and sales
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306'))
}

if not all([DB_CONFIG_PRODUCTS['database'], DB_CONFIG_PRODUCTS['user'],
            DB_CONFIG_PRODUCTS['password'], DB_CONFIG_PRODUCTS['host']]):
    logging.critical("Erro: Variáveis de ambiente do banco de dados (para produtos) não carregadas corretamente do .env")

db_pool_products = None
try:
    db_pool_products = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="alerta_lojas_products_pool",
        pool_size=5,
        **DB_CONFIG_PRODUCTS
    )
    logging.info("Pool de conexões MySQL para produtos criado com sucesso.")
except Error as e:
    logging.critical(f"Erro FATAL ao criar pool de conexões MySQL para produtos: {e}", exc_info=True)
    db_pool_products = None




@app.route('/alerta_lojas', methods=['GET', 'POST'])
@login_required
def alerta_lojas():
    # 1. Inicialização de TODAS as variáveis que serão passadas para o template
    produtos_para_exibir_na_tabela = [] 
    erro = None
    loja_id_form = None 
    grupo_form = None 
    fornecedor_form = None 
    
    saldo_min_cd_str = "1" 
    saldo_max_loja_str = "0" 

    codigos_filtrados_str = "" 
    codigos_filtrados = [] 

    dados_pizza = {'rupturas': 0, 'com_estoque': 0} 
    dados_ranking = [] 
    fornecedores_chart = [] 
    rupturas_chart = [] 
    
    total_skus_cd_com_saldo_para_grafico = 0 
    total_skus_cd_com_saldo_sem_loja = 0 

    # Variáveis internas para cálculos
    saldo_min_cd = 1.0 
    saldo_max_loja = 0.0 


    if request.method == 'POST':
        # 2. Coleta e validação dos dados do formulário (apenas em POST)
        loja_id_form = request.form.get('loja', '').strip()
        grupo_form = request.form.get('grupo', '').strip()
        fornecedor_form = request.form.get('fornecedor', '').strip() 
        
        saldo_min_cd_str = request.form.get('saldo_min_cd', '').strip()
        saldo_max_loja_str = request.form.get('saldo_max_loja', '').strip()
        
        codigos_filtrados_str = request.form.get('codigos_filtrados', '').strip()
        codigos_filtrados = [c.strip() for c in codigos_filtrados_str.split(',') if c.strip()] 

        if not loja_id_form or not loja_id_form.isdigit():
            erro = "Por favor, informe um número de loja válido."
        else:
            try:
                saldo_min_cd = float(saldo_min_cd_str) if saldo_min_cd_str else 1.0 
                saldo_max_loja = float(saldo_max_loja_str) if saldo_max_loja_str else 0.0
                
            except ValueError:
                erro = "Os valores de saldo devem ser numéricos."

        # Se houver erro de validação do formulário, retorna o template com a mensagem
        if erro:
            return render_template('alerta_lojas.html', erro=erro, loja=loja_id_form, grupo=grupo_form, fornecedor=fornecedor_form,
                                   saldo_min_cd=saldo_min_cd_str, saldo_max_loja=saldo_max_loja_str, 
                                   codigos_filtrados_str=codigos_filtrados_str,
                                   dados_pizza={'rupturas': 0, 'com_estoque': 0}, 
                                   dados_ranking=[], fornecedores=[], rupturas=[],
                                   total_skus_cd_com_saldo=0, total_skus_cd_com_saldo_sem_loja=0,
                                   produtos=produtos_para_exibir_na_tabela)
                                   

        # --- BUSCA DE DADOS OTIMIZADA DIRETAMENTE DO BANCO DE DADOS MySQL ---
        conn_mysql = None 
        try:
            if not db_pool_products: 
                raise Exception("Pool de conexões com o banco de dados não está disponível.")

            conn_mysql = db_pool_products.get_connection()
            cur_mysql = conn_mysql.cursor(dictionary=True)

            # --- PREPARANDO CONDIÇÕES PARA AS QUERIES SQL (reaproveitáveis) ---
            base_sql_conditions = [] 
            base_sql_params = [] 

            if grupo_form:
                base_sql_conditions.append("p.grupo = %s")
                base_sql_params.append(grupo_form)
            
            if codigos_filtrados:
                base_sql_conditions.append(f"p.codigo IN ({','.join(['%s'] * len(codigos_filtrados))})")
                base_sql_params.extend(codigos_filtrados)

            if fornecedor_form and fornecedor_form.isdigit():
                 base_sql_conditions.append("p.nu_fornecedor = %s")
                 base_sql_params.append(fornecedor_form)

            base_where_clause = ""
            if base_sql_conditions:
                base_where_clause = " AND " + " AND ".join(base_sql_conditions)


            # --- 1. BUSCA TOTAL DE SKUs COM SALDO NO CD PARA O GRÁFICO ---
            query_total_skus_cd_base = f"""
                SELECT COUNT(p.codigo) AS total_count
                FROM produtos AS p
                WHERE p.saldo > 0 {base_where_clause}
            """
            logging.info(f"Buscando total de SKUs no CD para o gráfico: {query_total_skus_cd_base} com params: {base_sql_params}")
            cur_mysql.execute(query_total_skus_cd_base, base_sql_params)
            total_skus_cd_com_saldo_para_grafico = cur_mysql.fetchone()['total_count']
            logging.info(f"Total de SKUs no CD para gráfico: {total_skus_cd_com_saldo_para_grafico}")


            # --- 2. BUSCA CONSOLIDADA DE PRODUTOS PARA A TABELA (APLICA TODOS OS FILTROS DA INTERFACE) ---
            query_consolidada = f"""
                SELECT
                    p.codigo,
                    p.descricao,
                    p.grupo,
                    p.preco,
                    p.custo,
                    p.saldo AS estoque_cd, 
                    COALESCE(sl.saldo, 0) AS estoque_loja, 
                    p.nu_fornecedor 
                FROM
                    produtos AS p
                LEFT JOIN
                    stq_lojas AS sl ON p.codigo = sl.codigo AND sl.tag_lojas = %s
                WHERE 1=1 
                    AND p.saldo >= %s 
                    AND COALESCE(sl.saldo, 0) <= %s
                {base_where_clause}
                ORDER BY p.codigo
            """
            params_consolidada_final = [str(loja_id_form), saldo_min_cd, saldo_max_loja] + base_sql_params

            logging.info(f"Buscando dados consolidados para a tabela: {query_consolidada} com params: {params_consolidada_final}")
            cur_mysql.execute(query_consolidada, params_consolidada_final)
            produtos_filtrados_sql_raw = cur_mysql.fetchall()
            logging.info(f"Dados filtrados SQL para a tabela obtidos: {len(produtos_filtrados_sql_raw)} itens.")

            produtos_para_calculo_e_exibicao = {} 
            for row in produtos_filtrados_sql_raw:
                cod = str(row.get('codigo'))
                produto_data = {
                    'grupo': row.get('grupo', ''),
                    'codigo': cod,
                    'descricao': row.get('descricao', 'Sem descrição'),
                    'fornecedor': str(row.get('nu_fornecedor') or 'Desconhecido'), 
                    'estoque_cd': float(row.get('estoque_cd') or 0.0),
                    'estoque_loja': float(row.get('estoque_loja') or 0.0),
                    'preco': float(row.get('preco') or 0.0),
                    'custo': float(row.get('custo') or 0.0)
                }
                produtos_para_calculo_e_exibicao[cod] = produto_data


            # --- 3. BUSCA DE DADOS DE VENDAS (total 30d E última venda geral) ---
            
            # Garante que codigos_para_vendas_list seja uma lista válida para o IN clause
            codigos_para_vendas_list = list(produtos_para_calculo_e_exibicao.keys())
            
            if not codigos_para_vendas_list:
                vendas_geral_dict = {}
                vendas_30d_dict = {}
            else:
                codigos_placeholder = ','.join(['%s'] * len(codigos_para_vendas_list))

                # Query para total de vendas nos últimos 30 dias
                query_vendas_30d = f"""
                    SELECT
                        produto AS codigo_produto,
                        SUM(CASE WHEN qtddevolvido = 0 THEN qtd ELSE 0 END) AS total_vendido
                    FROM
                        itens_vendas
                    WHERE
                        data_hora >= %s AND loja = %s
                        AND produto IN ({codigos_placeholder})
                    GROUP BY produto
                """
                params_vendas_30d = [(datetime.now() - timedelta(days=30)), str(loja_id_form)] + codigos_para_vendas_list
                
                logging.info(f"Buscando vendas dos últimos 30 dias: {query_vendas_30d} com params: {params_vendas_30d}")
                cur_mysql.execute(query_vendas_30d, params_vendas_30d)
                vendas_30d_raw = cur_mysql.fetchall()
                vendas_30d_dict = {str(item['codigo_produto']): {'total_vendido': float(item['total_vendido'] or 0.0)} 
                                   for item in vendas_30d_raw}
                logging.info(f"Vendas 30d obtidas: {len(vendas_30d_dict)} itens.")

                # Query para a última venda (de todos os tempos)
                query_ultima_venda_geral = f"""
                    SELECT
                        produto AS codigo_produto,
                        MAX(data_hora) AS ultima_venda_geral
                    FROM
                        itens_vendas
                    WHERE
                        loja = %s
                        AND produto IN ({codigos_placeholder})
                    GROUP BY produto
                """
                params_ultima_venda_geral = [str(loja_id_form)] + codigos_para_vendas_list

                logging.info(f"Buscando última venda geral: {query_ultima_venda_geral} com params: {params_ultima_venda_geral}")
                cur_mysql.execute(query_ultima_venda_geral, params_ultima_venda_geral)
                ultima_venda_geral_raw = cur_mysql.fetchall()
                vendas_geral_dict = {str(item['codigo_produto']): {'ultima_venda_geral': item['ultima_venda_geral']} 
                                     for item in ultima_venda_geral_raw}
                logging.info(f"Últimas vendas gerais obtidas: {len(vendas_geral_dict)} itens.")

            cur_mysql.close()

        except Error as e:
            logging.error(f"Erro MySQL ao buscar dados em alerta_lojas: {e}", exc_info=True)
            erro = f"Erro ao conectar ou consultar o banco de dados: {e}"
            produtos_para_calculo_e_exibicao = {} 
            vendas_geral_dict = {} 
            vendas_30d_dict = {} 
            total_skus_cd_com_saldo_para_grafico = 0 
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar dados em alerta_lojas: {e}", exc_info=True)
            erro = f"Ocorreu um erro inesperado ao buscar dados: {e}"
            produtos_para_calculo_e_exibicao = {} 
            vendas_geral_dict = {} 
            vendas_30d_dict = {} 
            total_skus_cd_com_saldo_para_grafico = 0 
        finally:
            if conn_mysql and conn_mysql.is_connected():
                conn_mysql.close()
                logging.info("Conexão MySQL retornada ao pool.")
        
        
        if not erro: 
            produtos_para_exibir_na_tabela = [] 
            fornecedor_rupturas = {} 

            # Aplicar filtro de fornecedor por texto (número) 
            if fornecedor_form and not fornecedor_form.isdigit(): 
                produtos_filtrados_por_fornecedor_temp = {}
                for cod, p_data in produtos_para_calculo_e_exibicao.items():
                    if fornecedor_form.lower() in str(p_data.get('fornecedor', '')).lower(): 
                        produtos_filtrados_por_fornecedor_temp[cod] = p_data
                produtos_para_calculo_e_exibicao = produtos_filtrados_por_fornecedor_temp 
            
            hoje_date = datetime.now().date() # Pega a data de hoje uma vez para usar no loop

            # Iterar sobre os produtos e preparar para exibição e ranking
            for produto_info in produtos_para_calculo_e_exibicao.values(): 
                cod = produto_info.get('codigo')
                est_loja = produto_info.get('estoque_loja') 
                est_cd = produto_info.get('estoque_cd') 

                # Obter total de vendas nos últimos 30 dias
                total_vendido_30d = vendas_30d_dict.get(cod, {}).get('total_vendido', 0.0)
                
                # Obter a última venda geral (de todos os tempos)
                ultima_venda_geral = vendas_geral_dict.get(cod, {}).get('ultima_venda_geral', None)

                # Calculate Sugestão and Cobertura (baseado em total_vendido_30d)
                sugestao = 0.0
                cobertura = "N/A" 

                if total_vendido_30d > 0:
                    if est_loja <= saldo_max_loja: 
                         sugestao = total_vendido_30d
                    
                    if est_loja > 0:
                        avg_daily_sales = total_vendido_30d / 30 if total_vendido_30d > 0 else 0
                        if avg_daily_sales > 0:
                            cobertura = round(est_loja / avg_daily_sales, 2)
                        else:
                            cobertura = "Infinito" 
                    else:
                        cobertura = "0 dias" 

                # Lógica  "S/ Venda"
                sem_venda_display = "" 
                
                if ultima_venda_geral: # Se há uma última venda registrada (mesmo que muito antiga)
                    # ultima_venda_geral pode vir como datetime.datetime ou datetime.date do DB
                    ultima_venda_date = ultima_venda_geral.date() if isinstance(ultima_venda_geral, datetime) else ultima_venda_geral
                    dias_desde_ultima_venda = (hoje_date - ultima_venda_date).days
                    sem_venda_display = f"{dias_desde_ultima_venda} d"
                else: # Nunca teve venda registrada
                    sem_venda_display = "Nunca vendeu"
                

                fornecedor_para_ranking = produto_info.get('fornecedor', 'Desconhecido') 
                fornecedor_rupturas[fornecedor_para_ranking] = fornecedor_rupturas.get(
                    fornecedor_para_ranking, 0) + 1

                produtos_para_exibir_na_tabela.append({ 
                    'grupo': produto_info.get('grupo', ''),
                    'codigo': cod,
                    'descricao': produto_info.get('descricao', 'Sem descrição'),
                    'fornecedor': produto_info.get('fornecedor'), 
                    'estoque_cd': est_cd,
                    'estoque_loja': est_loja,
                    'vendas_30d': total_vendido_30d, # Continua sendo o total dos últimos 30 dias
                    'sugestao': sugestao,
                    'cobertura': cobertura,
                    'sem_venda': sem_venda_display, # Passa o valor formatado
                    'preco': float(produto_info.get('preco') or 0.0),
                    'custo': float(produto_info.get('custo') or 0.0)
                })
            
            total_skus_cd_com_saldo_sem_loja = len(produtos_para_exibir_na_tabela) 

            if total_skus_cd_com_saldo_para_grafico > 0: 
                percentual_ruptura_pizza = (
                    total_skus_cd_com_saldo_sem_loja / total_skus_cd_com_saldo_para_grafico * 100)
                dados_pizza = {
                    'rupturas': round(percentual_ruptura_pizza, 2),
                    'com_estoque': round(100 - percentual_ruptura_pizza, 2)
                }
            else:
                dados_pizza = {'rupturas': 0, 'com_estoque': 0} 

            dados_ranking_tuplas = sorted(
                fornecedor_rupturas.items(), key=lambda x: x[1], reverse=True)[:10]
            dados_ranking = [{'fornecedor': f, 'rupturas': r}
                             for f, r in dados_ranking_tuplas]
            fornecedores_chart = [item['fornecedor'] for item in dados_ranking] 
            rupturas_chart = [item['rupturas'] for item in dados_ranking]

            if not produtos_para_exibir_na_tabela and not erro: 
                erro = "Nenhum produto em ruptura encontrado com os filtros aplicados."
        
    return render_template(
        'alerta_lojas.html',
        produtos=produtos_para_exibir_na_tabela, 
        erro=erro,
        loja=loja_id_form,
        grupo=grupo_form,
        fornecedor=fornecedor_form,
        saldo_min_cd=saldo_min_cd_str, 
        saldo_max_loja=saldo_max_loja_str, 
        codigos_filtrados_str=codigos_filtrados_str, 
        dados_pizza=dados_pizza, 
        dados_ranking=dados_ranking, 
        fornecedores=fornecedores_chart, 
        rupturas=rupturas_chart,
        total_skus_cd_com_saldo=total_skus_cd_com_saldo_para_grafico, 
        total_skus_cd_com_saldo_sem_loja=total_skus_cd_com_saldo_sem_loja
    )


@app.route('/api/produtos_por_codigo', methods=['POST'])
def get_produtos_por_codigo():
    data = request.get_json()
    if not data or 'codes' not in data or 'loja' not in data:
        return jsonify({"erro": "Códigos e loja são obrigatórios"}), 400
    
    codigos = data.get('codes')
    lojaId = data.get('loja')

    if not codigos:
        return jsonify([])

    conn = None
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        cursor = conn.cursor(dictionary=True)
        
        placeholders = ','.join(['%s'] * len(codigos))
        
        # =====> ESTA É A QUERY SQL FINAL E COMPLETA <======
        query = f"""
            SELECT 
                p.grupo, 
                p.codigo, 
                p.descricao, 
                p.nome_fantasia AS fornecedor,
                p.saldo AS estoque_cd,
                p.preco, 
                p.custo,
                
                -- Pega o saldo da loja usando JOIN e trata o caso de não haver registro (COALESCE)
                COALESCE(sl.saldo, 0) AS estoque_loja,
                
                -- Subquery para calcular as vendas dos últimos 30 dias para este produto e loja
                (SELECT SUM(iv.qtd) 
                 FROM itens_vendas iv 
                 WHERE iv.produto = p.codigo AND iv.loja = %s AND iv.data_hora >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                ) AS vendas_30d,
                
                -- Subquery para calcular os dias desde a última venda
                (SELECT DATEDIFF(NOW(), MAX(iv.data_hora))
                 FROM itens_vendas iv
                 WHERE iv.produto = p.codigo AND iv.loja = %s
                ) AS dias_sem_venda

            FROM 
                produtos p
            LEFT JOIN 
                stq_lojas sl ON p.codigo = sl.codigo AND sl.tag_lojas = %s
            WHERE 
                p.codigo IN ({placeholders})
        """
        
        # Os parâmetros precisam ser passados na ordem correta
        params = [lojaId, lojaId, lojaId] + codigos
        cursor.execute(query, params)
        produtos_db = cursor.fetchall()

        # --- Pós-processamento em Python para Cálculos de Negócio (VERSÃO CORRIGIDA) ---
        produtos_processados = []
        for p in produtos_db:
            # Converte os valores Decimais para float para poder fazer cálculos
            vendas_30d = float(p.get('vendas_30d') or 0.0)
            estoque_loja = float(p.get('estoque_loja') or 0.0)
            
            # Cálculo da Cobertura
            if vendas_30d > 0:
                venda_diaria = vendas_30d / 30.0
                # Certifica que estoque_loja também é float para a divisão
                cobertura = math.floor(estoque_loja / venda_diaria)
                p['cobertura'] = f"{cobertura} d"
            else:
                p['cobertura'] = "Infinito"

            # Cálculo da Sugestão (agora com floats)
            sugestao = vendas_30d - estoque_loja
            p['sugestao'] = max(0, math.ceil(sugestao))

            # Formatação dos dias sem venda
            dias_sem_venda = p.get('dias_sem_venda')
            if dias_sem_venda is None:
                p['sem_venda'] = "Nunca vendeu"
            else:
                p['sem_venda'] = f"{dias_sem_venda} d"

            produtos_processados.append(p)
        
        return jsonify(produtos_processados)

    except mysql.connector.Error as err:
        print(f"Erro de banco de dados: {err}")
        return jsonify({"erro": f"Erro no servidor: {err}"}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()









# de conexões prontas para serem usadas, o que é muito mais rápido.
try:
    db_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="meu_pool",
        pool_size=5,
        pool_reset_session=True,
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    print("Pool de conexões criado com sucesso.")
except mysql.connector.Error as err:
    print(f"Erro ao criar o pool de conexões: {err}")
    exit()

# --- Rota Principal ---
@app.route('/mapa')
def mapa():
    return render_template('mapa.html')

# --- API Endpoints (Adaptados para usar o pool de conexões) ---

@app.route('/api/transportadoras', methods=['GET'])
def get_todas_transportadoras():
    conn = db_pool.get_connection()
    cursor = conn.cursor(dictionary=True) # dictionary=True é como o DictCursor
    
    cursor.execute("SELECT id, nome, cor FROM transp ORDER BY nome")
    transportadoras = cursor.fetchall()
    
    for transportadora in transportadoras:
        cursor.execute("SELECT cidade FROM transp_cidades WHERE transp_id = %s", (transportadora['id'],))
        cidades_raw = cursor.fetchall()
        transportadora['cidades'] = [c['cidade'] for c in cidades_raw]
        
    cursor.close()
    conn.close() # Devolve a conexão para o pool
    return jsonify(transportadoras)

@app.route('/api/transportadoras', methods=['POST'])
def criar_transportadora():
    dados = request.get_json()
    nome = dados.get('nome')
    cor = dados.get('cor')
    if not nome or not cor:
        return jsonify({'error': 'Nome e cor são obrigatórios'}), 400
    
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO transp(nome, cor) VALUES (%s, %s)", (nome, cor))
    conn.commit()
    novo_id = cursor.lastrowid
    cursor.close()
    conn.close()
    
    return jsonify({'id': novo_id, 'nome': nome, 'cor': cor, 'cidades': []}), 201

@app.route('/api/transportadoras/<int:id>', methods=['DELETE'])
def deletar_transportadora(id):
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transp WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify(None), 204

@app.route('/api/transportadoras/<int:id>/cor', methods=['PUT'])
def atualizar_cor(id):
    dados = request.get_json()
    nova_cor = dados.get('cor')
    
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE transp SET cor = %s WHERE id = %s", (nova_cor, id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Cor atualizada com sucesso'})

@app.route('/api/transportadoras/<int:id>/cidades', methods=['POST'])
def adicionar_cidade(id):
    dados = request.get_json()
    nome_cidade = dados.get('nome_cidade')

    conn = db_pool.get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO transp_cidades(transp_id, cidade) VALUES (%s, %s)", (id, nome_cidade))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Cidade adicionada com sucesso'}), 201

@app.route('/api/transportadoras/<int:id>/cidades', methods=['DELETE'])
def remover_cidade(id):
    dados = request.get_json()
    nome_cidade = dados.get('nome_cidade')
    
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transp_cidades WHERE transp_id = %s AND cidade = %s", (id, nome_cidade))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify(None), 204





















logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MAIN_SALES_DB_NAME = os.getenv("DB_NAME", "estoque_db") 
MAIN_SALES_TABLE_NAME = "itens_vendas" 

LOJAS_MAP = {
    1: "PONTA NEGRA", 2: "ALECRIM", 7: "SAC - CENTRO VI", 100: "LAGOA NOVA",
    121: "NORTE SHOPPING", 122: "PARNAMIRIM", 131: "ZN2", 137: "MACAIBA",
    140: "MARIA LACERDA", 141: "IGAPO"
}

GRUPOS_PRODUTOS = {
    1: "UTILIDADES",2: "BRINQUEDOS",4: "ELETRÔ SALÃO",5: "COSMÉTICOS",6: "VIDROS",
    7: "MOVEIS / SALÃO",8: "NATALINO",9: "MÓVEIS INFANTIS",10: "PAPELARIA",12: "BABY",
    13: "CAMA, MESA E BANHO",22: "ELETRODOMÉSTICOS",23: "ACESSÓRIOS SALÃO",
    24: "MAQUIAGEM E AFINS",25: "ESMALTES",26: "PLÁSTICOS",32: "CONFECÇÕES",
    33: "BOMBOREIRE",34: "CALÇADOS",36: "COLORAÇÃO",37: "PET",
   
}

PRODUCT_DETAILS_CACHE = {}
LAST_PRODUCT_CACHE_UPDATE = None
CACHE_TTL_SECONDS = 3600

# =====================================================================
# Funções Auxiliares
# =====================================================================

def get_db_connection(db_name):
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=db_name,
        )
        return conn
    except mysql.connector.Error as err:
        logging.error(f"!!! ERRO AO CONECTAR AO BANCO '{db_name}': {err} !!!")
        raise


def fetch_all_sales_items_from_unified_table(data_inicio, data_fim, loja_id=None):
    """
    Busca itens de vendas da tabela UNIFICADA 'itens_vendas', fazendo JOIN com 'produtos'
    para obter 'nu_fornecedor' e 'nome_fantasia' (ambos da tabela produtos).
    """
    conn = None
    try:
        conn = get_db_connection(MAIN_SALES_DB_NAME)
        cursor = conn.cursor(dictionary=True)

        query = f"""
            SELECT 
                iv.id, iv.loja, iv.nfce, iv.serie, iv.produto, iv.qtd, iv.qtddevolvido, iv.preco, iv.custo,
                iv.desconto, iv.vendedor, DATE_FORMAT(iv.data_hora, '%Y-%m-%d') AS data_item,
                iv.data_hora,
                p.nu_fornecedor AS fornecedor_id,    /* ID do fornecedor da tabela PRODUTOS */
                p.nome_fantasia AS fornecedor_nome    /* NOME FANTASIA do fornecedor da tabela PRODUTOS */
            FROM 
                {MAIN_SALES_TABLE_NAME} AS iv 
            JOIN 
                produtos AS p ON iv.produto = p.codigo /* JOIN SOMENTE COM PRODUTOS */
            WHERE 
                iv.data_hora BETWEEN %(data_inicio)s AND %(data_fim)s
        """
        
        params = {
            'data_inicio': f"{data_inicio} 00:00:00",
            'data_fim': f"{data_fim} 23:59:59"
        }

        if loja_id: 
            query += " AND iv.loja = %(loja_id)s"
            params['loja_id'] = loja_id 

        logging.info(f"Executando SQL para período {data_inicio} a {data_fim}, Loja: {loja_id or 'Todas'} no DB {MAIN_SALES_DB_NAME}.{MAIN_SALES_TABLE_NAME}")
        cursor.execute(query, params)
        items = cursor.fetchall()
        
        return (items, None)
    except Exception as e:
        logging.error(f"Erro ao buscar dados da tabela unificada '{MAIN_SALES_TABLE_NAME}': {e}")
        return ([], str(e))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


def get_product_details_from_cache_or_db():
    global PRODUCT_DETAILS_CACHE, LAST_PRODUCT_CACHE_UPDATE

    now = datetime.now()
    if not PRODUCT_DETAILS_CACHE or (LAST_PRODUCT_CACHE_UPDATE and (now - LAST_PRODUCT_CACHE_UPDATE).total_seconds() > CACHE_TTL_SECONDS):
        logging.info("Recarregando cache de produtos...")
        temp_conn = None
        try:
            temp_conn = get_db_connection(MAIN_SALES_DB_NAME) 
            cursor = temp_conn.cursor(dictionary=True)
            # A query de produtos pode continuar simples se nome_fantasia for puxado via JOIN na query principal
            cursor.execute("SELECT codigo, descricao, grupo FROM produtos") 
            new_cache = {}
            for row in cursor.fetchall():
                new_cache[str(row['codigo'])] = {'nome': row['descricao'], 'grupo': row['grupo']}
            PRODUCT_DETAILS_CACHE = new_cache
            LAST_PRODUCT_CACHE_UPDATE = now
            logging.info(f"Cache de produtos recarregado com {len(PRODUCT_DETAILS_CACHE)} itens.")
        except Exception as e:
            logging.error(f"Erro ao recarregar cache de produtos: {e}")
        finally:
            if temp_conn and temp_conn.is_connected():
                cursor.close()
                temp_conn.close()
    return PRODUCT_DETAILS_CACHE


def calculate_net_revenue_and_enrich(df, all_product_details):
    """
    Calcula faturamento, lucro, etc., e enriquece o DataFrame.
    Agora usa 'fornecedor_id' e 'fornecedor_nome' que vêm do SQL.
    """
    if df.empty:
        return pd.DataFrame(columns=[
            'id', 'loja', 'nfce', 'serie', 'produto', 'qtd', 'qtddevolvido',
            'preco', 'custo', 'desconto', 'vendedor', 'data_item', 'data_hora',
            'fornecedor_id', 'fornecedor_nome', # <-- INCLUIR NOVO CAMPO
            'qtd_liquida', 'faturamento_liquido', 'lucro_liquido',
            'nome_produto', 'grupo_produto_id', 'nome_grupo', 'nome_loja', 'venda_id'
        ])
    
    df['preco'] = pd.to_numeric(df['preco'], errors='coerce').fillna(0)
    df['custo'] = pd.to_numeric(df['custo'], errors='coerce').fillna(0)
    df['qtd'] = pd.to_numeric(df['qtd'], errors='coerce').fillna(0)
    df['qtddevolvido'] = pd.to_numeric(df['qtddevolvido'], errors='coerce').fillna(0)
    df['desconto'] = pd.to_numeric(df['desconto'], errors='coerce').fillna(0) 
    
    df['loja'] = pd.to_numeric(df['loja'], errors='coerce').fillna(0).astype(int)
    df['produto'] = df['produto'].astype(str)
    
    # 'fornecedor_id' virá do SQL, 'fornecedor_nome' também.
    # É bom garantir que 'fornecedor_nome' seja string e tratar nulos.
    df['fornecedor_nome'] = df['fornecedor_nome'].astype(str).fillna('Desconhecido')


    df['qtd_liquida'] = df['qtd'] - df['qtddevolvido']
    df['faturamento_liquido'] = (df['preco'] * df['qtd_liquida'].clip(lower=0)) - (df['desconto'] * (df['qtd_liquida'].clip(lower=0) > 0).astype(int))
    df['lucro_liquido'] = (df['faturamento_liquido'] - (df['custo'] * df['qtd_liquida'].clip(lower=0)))

    df['nome_produto'] = df['produto'].map(lambda x: all_product_details.get(str(x), {}).get('nome', f"Cód: {x}"))
    df['grupo_produto_id'] = df['produto'].map(lambda x: all_product_details.get(str(x), {}).get('grupo', 0))
    df['nome_grupo'] = df['grupo_produto_id'].map(lambda x: GRUPOS_PRODUTOS.get(x, 'Outros'))
    
    df['nome_loja'] = df['loja'].map(lambda x: LOJAS_MAP.get(x, f"Loja {x}"))

    df['venda_id'] = df['loja'].astype(str) + '-' + df['nfce'].astype(str) + '-' + df['serie'].astype(str)

    return df

# =====================================================================
# Rotas Flask da Aplicação
# =====================================================================

@app.route('/analise_vendas', methods=['GET'])
def analise_vendas():
    return render_template('analise_vendas.html')


@app.route('/api/vendas', methods=['GET'])
def get_vendas():
    id_loja_param = request.args.get('id_loja')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    if not data_inicio or not data_fim:
        return jsonify({"erro": "As datas de início e fim são obrigatórias."}), 400

    try:
        datetime.strptime(data_inicio, '%Y-%m-%d')
        datetime.strptime(data_fim, '%Y-%m-%d')
    except ValueError:
        return jsonify({"erro": "Formato de data inválido. Use YYYY-MM-DD."}), 400

    loja_id_filtro = int(id_loja_param) if id_loja_param else None

    sales_items_raw, error_msg = fetch_all_sales_items_from_unified_table(data_inicio, data_fim, loja_id_filtro)
    
    lojas_com_erro = []
    if error_msg:
        lojas_com_erro.append({"loja": "Global", "motivo": error_msg})

    all_product_details = get_product_details_from_cache_or_db()

    df_vendas = pd.DataFrame(sales_items_raw)
    df_vendas = calculate_net_revenue_and_enrich(df_vendas, all_product_details)

    if df_vendas.empty:
        logging.warning("DataFrame de vendas vazio após processamento. Nenhuma venda encontrada para os filtros.")
        return jsonify({
            "kpis": {
                "faturamento": 0.0, "lucro": 0.0, "quantidade_vendida": 0, "ticket_medio": 0.0
            },
            "chart_faturamento_grupo": {"labels": [], "data": []},
            "chart_faturamento_diario": {"labels": [], "data": []},
            "top_produtos_faturamento": [],
            "top_fornecedores_faturamento": [], # Vazio se não houver dados
            "info_processamento": {"lojas_com_erro": lojas_com_erro, "lojas_consultadas": [loja_id_filtro] if loja_id_filtro else list(LOJAS_MAP.keys())}
        })

    # --- Cálculo dos KPIs ---
    total_faturamento = df_vendas['faturamento_liquido'].sum()
    total_lucro = df_vendas['lucro_liquido'].sum()
    total_quantidade_vendida = df_vendas['qtd_liquida'].sum()
    total_vendas_unicas = df_vendas['venda_id'].nunique()
    ticket_medio_geral = total_faturamento / total_vendas_unicas if total_vendas_unicas > 0 else 0.0

    kpis = {
        "faturamento": total_faturamento,
        "lucro": total_lucro,
        "quantidade_vendida": total_quantidade_vendida,
        "ticket_medio": ticket_medio_geral
    }

    # --- Geração de Dados para Gráficos ---

    # Faturamento por Grupo (Bar Chart)
    faturamento_por_grupo = df_vendas.groupby('nome_grupo')['faturamento_liquido'].sum().sort_values(ascending=False)
    chart_faturamento_grupo = {
        "labels": faturamento_por_grupo.index.tolist(),
        "data": faturamento_por_grupo.round(2).tolist()
    }

    # Faturamento Diário (Line Chart)
    faturamento_diario = df_vendas.groupby('data_item')['faturamento_liquido'].sum().sort_index()
    chart_faturamento_diario = {
        "labels": faturamento_diario.index.tolist(),
        "data": faturamento_diario.round(2).tolist()
    }

    # Top 10 Produtos por Faturamento (para o gráfico de Barras Horizontais)
    top_produtos_faturamento_list = []
    if total_faturamento > 0:
        produtos_faturamento = df_vendas.groupby(['produto', 'nome_produto'])['faturamento_liquido'].sum().nlargest(10).reset_index()
        for idx, row in produtos_faturamento.iterrows():
            percentual = (row['faturamento_liquido'] / total_faturamento) * 100
            top_produtos_faturamento_list.append({
                "nome": row['nome_produto'],
                "faturamento": row['faturamento_liquido'],
                "percentual": round(percentual, 2)
            })

    # Top 10 Fornecedores por Faturamento (para o Gráfico de Rosca)
    # AGORA USA 'fornecedor_nome' para o label e 'faturamento' para o valor
    top_fornecedores_faturamento_list = []
    if total_faturamento > 0:
        fornecedores_faturamento = df_vendas.groupby('fornecedor_nome')['faturamento_liquido'].sum().nlargest(10).reset_index()
        for idx, row in fornecedores_faturamento.iterrows():
            percentual = (row['faturamento_liquido'] / total_faturamento) * 100
            top_fornecedores_faturamento_list.append({
                "nome": row['fornecedor_nome'], # <--- AGORA USA O NOME FANTASIA
                "faturamento": row['faturamento_liquido'],
                "percentual": round(percentual, 2)
            })

    # --- Montagem da Resposta Final da API ---
    resposta_final = {
        "kpis": kpis,
        "chart_faturamento_grupo": chart_faturamento_grupo,
        "chart_faturamento_diario": chart_faturamento_diario,
        "top_produtos_faturamento": top_produtos_faturamento_list,
        "top_fornecedores_faturamento": top_fornecedores_faturamento_list, # Dados do fornecedor com nome fantasia
        "info_processamento": {"lojas_com_erro": lojas_com_erro, "lojas_consultadas": [loja_id_filtro] if loja_id_filtro else list(LOJAS_MAP.keys())}
    }
    
    return jsonify(resposta_final)


# # Configuração de logging para depuração
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# # Nomes do banco de dados e da tabela principal, lidos do .env
# MAIN_SALES_DB_NAME = os.getenv("DB_NAME", "estoque_db") 
# MAIN_SALES_TABLE_NAME = "itens_vendas" # O nome da sua tabela UNIFICADA

# # Mapeamento de IDs de Loja para Nomes Legíveis (Frontend também usa isso)
# LOJAS_MAP = {
#     1: "PONTA NEGRA", 2: "ALECRIM", 7: "SAC - CENTRO VI", 100: "LAGOA NOVA",
#     121: "NORTE SHOPPING", 122: "PARNAMIRIM", 131: "ZN2", 137: "MACAIBA",
#     140: "MARIA LACERDA", 141: "IGAPO"
# }

# # Mapeamento de IDs de Grupo de Produtos para Nomes Legíveis (Frontend também usa isso)
# GRUPOS_PRODUTOS = {
#     1: "MÓVEIS INFANTIS", 2: "ELETRÔ SALÃO", 3: "ELETRODOMÉSTICOS", 4: "BABY",
#     5: "BRINQUEDOS", 6: "CONFECÇÕES", 7: "COSMÉTICOS", 8: "CAMA, MESA E BANHO",
#     9: "UTILIDADES", 10: "CALÇADOS", 11: "VIDROS", 12: "COLORAÇÃO",
#     13: "MAQUIAGEM E AFINS", 14: "NATALINO",
#     0: "Outros" # Grupo padrão para IDs não mapeados
# }

# # Cache para detalhes de produtos (para evitar consultas repetidas à tabela 'produtos')
# PRODUCT_DETAILS_CACHE = {}
# LAST_PRODUCT_CACHE_UPDATE = None
# CACHE_TTL_SECONDS = 3600 # 1 hora de vida para o cache

# # =====================================================================
# # Funções Auxiliares de Banco de Dados e Processamento
# # =====================================================================

# def get_db_connection(db_name):
#     """
#     Função para obter uma conexão ao banco de dados usando mysql.connector.
#     As credenciais são lidas do .env.
#     """
#     try:
#         conn = mysql.connector.connect(
#             host=os.getenv("DB_HOST", "localhost"),
#             user=os.getenv("DB_USER", "root"),
#             password=os.getenv("DB_PASSWORD", ""),
#             database=db_name, # O nome do banco (ex: "estoque_db")
#         )
#         return conn
#     except mysql.connector.Error as err:
#         logging.error(f"!!! ERRO AO CONECTAR AO BANCO '{db_name}': {err} !!!")
#         raise # Levanta a exceção para ser capturada na rota


# def fetch_all_sales_items_from_unified_table(data_inicio, data_fim, loja_id=None):
#     """
#     Busca itens de vendas da tabela UNIFICADA 'itens_vendas' no banco principal.
#     Realiza JOIN com a tabela 'produtos' para obter 'nu_fornecedor'.
#     Pode filtrar por loja_id opcionalmente.
#     """
#     conn = None
#     try:
#         conn = get_db_connection(MAIN_SALES_DB_NAME)
#         cursor = conn.cursor(dictionary=True) # Retorna resultados como dicionários

#         query = f"""
#             SELECT 
#                 iv.id, iv.loja, iv.nfce, iv.serie, iv.produto, iv.qtd, iv.qtddevolvido, iv.preco, iv.custo,
#                 iv.desconto, iv.vendedor, DATE_FORMAT(iv.data_hora, '%Y-%m-%d') AS data_item,
#                 iv.data_hora, /* Mantém a data_hora original se precisar de granularidade de tempo */
#                 p.nu_fornecedor AS fornecedor /* CORREÇÃO AQUI: BUSCA nu_fornecedor DA TABELA 'produtos' E RENOMEIA PARA 'fornecedor' */
#             FROM 
#                 {MAIN_SALES_TABLE_NAME} AS iv /* Sua tabela de vendas unificada */
#             JOIN 
#                 produtos AS p ON iv.produto = p.codigo /* JOIN para ligar itens_vendas a produtos */
#             WHERE 
#                 iv.data_hora BETWEEN %(data_inicio)s AND %(data_fim)s
#         """
        
#         params = {
#             'data_inicio': f"{data_inicio} 00:00:00",
#             'data_fim': f"{data_fim} 23:59:59"
#         }

#         if loja_id: # Adiciona o filtro de loja SE um ID de loja for fornecido
#             query += " AND iv.loja = %(loja_id)s"
#             params['loja_id'] = loja_id 

#         logging.info(f"Executando SQL para período {data_inicio} a {data_fim}, Loja: {loja_id or 'Todas'} no DB {MAIN_SALES_DB_NAME}.{MAIN_SALES_TABLE_NAME}")
#         cursor.execute(query, params)
#         items = cursor.fetchall()
        
#         return (items, None) # Retorna a lista de itens e 'None' para erro
#     except Exception as e:
#         logging.error(f"Erro ao buscar dados da tabela unificada '{MAIN_SALES_TABLE_NAME}': {e}")
#         return ([], str(e)) # Retorna lista vazia e a mensagem de erro
#     finally:
#         if conn and conn.is_connected():
#             cursor.close()
#             conn.close()


# def get_product_details_from_cache_or_db():
#     """
#     Busca (e cacheia) detalhes de produtos (nome, grupo) da tabela 'produtos'.
#     Assume que 'produtos' está no MAIN_SALES_DB_NAME.
#     """
#     global PRODUCT_DETAILS_CACHE, LAST_PRODUCT_CACHE_UPDATE

#     now = datetime.now()
#     # Recarrega o cache se ele estiver vazio ou muito antigo
#     if not PRODUCT_DETAILS_CACHE or (LAST_PRODUCT_CACHE_UPDATE and (now - LAST_PRODUCT_CACHE_UPDATE).total_seconds() > CACHE_TTL_SECONDS):
#         logging.info("Recarregando cache de produtos...")
#         temp_conn = None
#         try:
#             # Usa MAIN_SALES_DB_NAME, que é o DB_NAME do .env
#             temp_conn = get_db_connection(MAIN_SALES_DB_NAME) 
#             cursor = temp_conn.cursor(dictionary=True)
#             cursor.execute("SELECT codigo, descricao, grupo FROM produtos")
#             new_cache = {}
#             for row in cursor.fetchall():
#                 new_cache[str(row['codigo'])] = {'nome': row['descricao'], 'grupo': row['grupo']}
#             PRODUCT_DETAILS_CACHE = new_cache
#             LAST_PRODUCT_CACHE_UPDATE = now
#             logging.info(f"Cache de produtos recarregado com {len(PRODUCT_DETAILS_CACHE)} itens.")
#         except Exception as e:
#             logging.error(f"Erro ao recarregar cache de produtos: {e}")
#         finally:
#             if temp_conn and temp_conn.is_connected():
#                 cursor.close()
#                 temp_conn.close()
#     return PRODUCT_DETAILS_CACHE


# def calculate_net_revenue_and_enrich(df, all_product_details):
#     """
#     Calcula o faturamento líquido, quantidade líquida e lucro,
#     e enriquece o DataFrame com nomes de produtos, grupos e lojas.
#     Converte os tipos de dados das colunas relevantes.
#     """
#     if df.empty:
#         # Retorna um DataFrame vazio mas com as colunas esperadas para evitar KeyErrors
#         return pd.DataFrame(columns=[
#             'id', 'loja', 'nfce', 'serie', 'produto', 'qtd', 'qtddevolvido',
#             'preco', 'custo', 'desconto', 'vendedor', 'data_item', 'data_hora',
#             'fornecedor', # 'fornecedor' vem do SQL via AS nu_fornecedor
#             'qtd_liquida', 'faturamento_liquido', 'lucro_liquido',
#             'nome_produto', 'grupo_produto_id', 'nome_grupo', 'nome_loja', 'venda_id'
#         ])
    
#     # Converte colunas para numérico, tratando erros e preenchendo NaNs
#     df['preco'] = pd.to_numeric(df['preco'], errors='coerce').fillna(0)
#     df['custo'] = pd.to_numeric(df['custo'], errors='coerce').fillna(0)
#     df['qtd'] = pd.to_numeric(df['qtd'], errors='coerce').fillna(0)
#     df['qtddevolvido'] = pd.to_numeric(df['qtddevolvido'], errors='coerce').fillna(0)
#     df['desconto'] = pd.to_numeric(df['desconto'], errors='coerce').fillna(0) 
    
#     # Garante que 'loja' e 'produto' são tipos corretos para agrupamento/mapeamento
#     df['loja'] = pd.to_numeric(df['loja'], errors='coerce').fillna(0).astype(int)
#     df['produto'] = df['produto'].astype(str)
    
#     # Garante que 'fornecedor' é string (vem da query 'AS fornecedor')
#     df['fornecedor'] = df['fornecedor'].astype(str)

#     df['qtd_liquida'] = df['qtd'] - df['qtddevolvido']
#     # Cálculo do faturamento com desconto (aplicado por linha de item)
#     df['faturamento_liquido'] = (df['preco'] * df['qtd_liquida'].clip(lower=0)) - (df['desconto'] * (df['qtd_liquida'].clip(lower=0) > 0).astype(int))
#     df['lucro_liquido'] = (df['faturamento_liquido'] - (df['custo'] * df['qtd_liquida'].clip(lower=0)))

#     # Enriquecimento com detalhes de produtos (nome, grupo)
#     df['nome_produto'] = df['produto'].map(lambda x: all_product_details.get(str(x), {}).get('nome', f"Cód: {x}"))
#     df['grupo_produto_id'] = df['produto'].map(lambda x: all_product_details.get(str(x), {}).get('grupo', 0))
#     df['nome_grupo'] = df['grupo_produto_id'].map(lambda x: GRUPOS_PRODUTOS.get(x, 'Outros'))
    
#     # Enriquecimento com nomes de lojas (usando o LOJAS_MAP global)
#     df['nome_loja'] = df['loja'].map(lambda x: LOJAS_MAP.get(x, f"Loja {x}"))

#     # Criar ID de venda única para cálculo de Ticket Médio
#     df['venda_id'] = df['loja'].astype(str) + '-' + df['nfce'].astype(str) + '-' + df['serie'].astype(str)

#     return df

# # =====================================================================
# # Rotas Flask da Aplicação
# # =====================================================================

# @app.route('/analise_vendas', methods=['GET'])
# def analise_vendas():
#     """
#     Renderiza o template HTML do dashboard de análise de vendas.
#     """
#     return render_template('analise_vendas.html')


# @app.route('/api/vendas', methods=['GET'])
# def get_vendas():
#     """
#     API para buscar dados de vendas, processá-los com Pandas e retornar KPIs,
#     dados para gráficos e detalhes da tabela.
#     Filtra por loja (opcional) e período de data.
#     """
#     id_loja_param = request.args.get('id_loja') # Pode ser string vazia para todas as lojas
#     data_inicio = request.args.get('data_inicio')
#     data_fim = request.args.get('data_fim')

#     # Validações dos parâmetros de data
#     if not data_inicio or not data_fim:
#         return jsonify({"erro": "As datas de início e fim são obrigatórias."}), 400

#     try:
#         datetime.strptime(data_inicio, '%Y-%m-%d')
#         datetime.strptime(data_fim, '%Y-%m-%d')
#     except ValueError:
#         return jsonify({"erro": "Formato de data inválido. Use YYYY-MM-DD."}), 400

#     # Converter id_loja_param para int se não for vazio, senão None
#     loja_id_filtro = int(id_loja_param) if id_loja_param else None

#     # --- 1. Busca de Dados Brutos do Banco de Dados ---
#     sales_items_raw, error_msg = fetch_all_sales_items_from_unified_table(data_inicio, data_fim, loja_id_filtro)
    
#     lojas_com_erro = []
#     if error_msg:
#         lojas_com_erro.append({"loja": "Global", "motivo": error_msg}) # Erro na busca principal

#     # --- 2. Carregar/Atualizar Cache de Produtos ---
#     all_product_details = get_product_details_from_cache_or_db()

#     # --- 3. Processamento e Enriquecimento com Pandas ---
#     df_vendas = pd.DataFrame(sales_items_raw)
#     df_vendas = calculate_net_revenue_and_enrich(df_vendas, all_product_details)

#     # --- 4. Verificação de DataFrame vazio após processamento (sem dados para os filtros) ---
#     if df_vendas.empty:
#         logging.warning("DataFrame de vendas vazio após processamento. Nenhuma venda encontrada para os filtros.")
#         return jsonify({
#             "kpis": {
#                 "faturamento": 0.0, "lucro": 0.0, "quantidade_vendida": 0, "ticket_medio": 0.0
#             },
#             "chart_faturamento_grupo": {"labels": [], "data": []},
#             "chart_faturamento_diario": {"labels": [], "data": []},
#             "top_produtos_faturamento": [],
#             "top_fornecedores_faturamento": [],
#             "tabela_detalhes_vendas": [],
#             "info_processamento": {"lojas_com_erro": lojas_com_erro, "lojas_consultadas": [loja_id_filtro] if loja_id_filtro else list(LOJAS_MAP.keys())}
#         })

#     # --- 5. Cálculo dos KPIs (Key Performance Indicators) ---
#     total_faturamento = df_vendas['faturamento_liquido'].sum()
#     total_lucro = df_vendas['lucro_liquido'].sum()
#     total_quantidade_vendida = df_vendas['qtd_liquida'].sum()
    
#     # Para Ticket Médio, contamos transações únicas (Loja-NFCe-Série)
#     total_vendas_unicas = df_vendas['venda_id'].nunique()
#     ticket_medio_geral = total_faturamento / total_vendas_unicas if total_vendas_unicas > 0 else 0.0

#     kpis = {
#         "faturamento": total_faturamento,
#         "lucro": total_lucro,
#         "quantidade_vendida": total_quantidade_vendida,
#         "ticket_medio": ticket_medio_geral
#     }

#     # --- 6. Geração de Dados para Gráficos ---

#     # Faturamento por Grupo (para o Bar Chart no Frontend)
#     faturamento_por_grupo = df_vendas.groupby('nome_grupo')['faturamento_liquido'].sum().sort_values(ascending=False)
#     chart_faturamento_grupo = {
#         "labels": faturamento_por_grupo.index.tolist(),
#         "data": faturamento_por_grupo.round(2).tolist()
#     }

#     # Faturamento Diário (para o Line Chart no Frontend)
#     faturamento_diario = df_vendas.groupby('data_item')['faturamento_liquido'].sum().sort_index()
#     chart_faturamento_diario = {
#         "labels": faturamento_diario.index.tolist(),
#         "data": faturamento_diario.round(2).tolist()
#     }

#     # Top 10 Produtos por Faturamento (para a Lista Rolável no Frontend)
#     top_produtos_faturamento_list = []
#     if total_faturamento > 0: # Evita divisão por zero
#         produtos_faturamento = df_vendas.groupby(['produto', 'nome_produto'])['faturamento_liquido'].sum().nlargest(10).reset_index()
#         for idx, row in produtos_faturamento.iterrows():
#             percentual = (row['faturamento_liquido'] / total_faturamento) * 100
#             top_produtos_faturamento_list.append({
#                 "nome": row['nome_produto'],
#                 "faturamento": row['faturamento_liquido'],
#                 "percentual": round(percentual, 2)
#             })

#     # Top 10 Fornecedores por Faturamento (para a Lista Rolável no Frontend)
#     top_fornecedores_faturamento_list = []
#     if total_faturamento > 0: # Evita divisão por zero
#         fornecedores_faturamento = df_vendas.groupby('fornecedor')['faturamento_liquido'].sum().nlargest(10).reset_index()
#         for idx, row in fornecedores_faturamento.iterrows():
#             percentual = (row['faturamento_liquido'] / total_faturamento) * 100
#             top_fornecedores_faturamento_list.append({
#                 "nome": row['fornecedor'],
#                 "faturamento": row['faturamento_liquido'],
#                 "percentual": round(percentual, 2)
#             })

#     # --- 7. Geração de Dados para Tabela Detalhada de Vendas ---
#     # Seleciona e renomeia colunas para o formato esperado pelo frontend
#     tabela_detalhes_vendas = df_vendas[[
#         'nome_grupo', 'nome_produto', 'faturamento_liquido', 'qtd_liquida',
#         'lucro_liquido', 'fornecedor', 'data_item'
#     ]].rename(columns={
#         'nome_grupo': 'grupo',
#         'faturamento_liquido': 'faturamento',
#         'qtd_liquida': 'quantidade_vendida',
#         'lucro_liquido': 'lucro',
#         'data_item': 'data'
#     }).to_dict(orient='records') # Converte para lista de dicionários

#     # --- 8. Montagem da Resposta Final da API ---
#     resposta_final = {
#         "kpis": kpis,
#         "chart_faturamento_grupo": chart_faturamento_grupo,
#         "chart_faturamento_diario": chart_faturamento_diario,
#         "top_produtos_faturamento": top_produtos_faturamento_list,
#         "top_fornecedores_faturamento": top_fornecedores_faturamento_list,
#         "tabela_detalhes_vendas": tabela_detalhes_vendas,
#         "info_processamento": {"lojas_com_erro": lojas_com_erro, "lojas_consultadas": [loja_id_filtro] if loja_id_filtro else list(LOJAS_MAP.keys())}
#     }
    
#     return jsonify(resposta_final)



# # Função para montar o mapeamento Loja → Banco dinamicamente
# def get_loja_para_banco():
#     loja_map = {}
#     for key in os.environ:
#         if key.startswith("LOJA_"):
#             loja_id = key.split("_")[1]
#             banco = os.getenv(key)
#             loja_map[loja_id] = banco
#     return loja_map


# LOJA_PARA_BANCO = get_loja_para_banco()


# @app.route('/analise_vendas', methods=['GET'])
# def analise_vendas():
#     # Esta rota renderiza o template HTML
#     return render_template('analise_vendas.html')


# @app.route('/api/vendas', methods=['GET'])
# def get_vendas():
#     id_loja = request.args.get('id_loja')
#     data_inicio = request.args.get('data_inicio')
#     data_fim = request.args.get('data_fim')

#     if not id_loja or id_loja not in LOJA_PARA_BANCO:
#         return jsonify({"erro": "ID de loja inválido ou não mapeado."}), 400

#     banco = LOJA_PARA_BANCO[id_loja]

#     # Mapeamento de id_loja para o nome da tabela
#     TABELA_POR_LOJA = {
#         "1": "vendas_pn",      # PONTA NEGRA
#         "2": "vendas_alecrim",  # ALECRIM
#         "7": "vendas_sac6",    # SAC - CENTRO VI
#         "100": "vendas_ln",    # LAGOA NOVA
#         "121": "vendas_nshop",  # NORTE SHOPPING
#         "122": "vendas_parna",  # PARNAMIRIM
#         "131": "vendas_zn2",   # ZN2
#         "137": "vendas_mac",   # MACAIBA
#         "140": "vendas_ml",    # MARIA LACERDA
#         "141": "vendas_igapo"  # IGAPO
#     }

#     # Fallback caso id_loja não esteja mapeado
#     tabela_vendas = TABELA_POR_LOJA.get(id_loja, f"vendas_{id_loja}")

#     db_config = {
#         'host': os.getenv("DB_HOST"),
#         'user': os.getenv("DB_USER"),
#         'password': os.getenv("DB_PASSWORD"),
#         'database': banco
#     }

#     try:
#         conn = mysql.connector.connect(**db_config)
#         cursor = conn.cursor(dictionary=True)

#         query = f"""
#         SELECT 
#             grupo,
#             produto,
#             fornecedor,
#             DATE_FORMAT(COALESCE(data_hora, '1970-01-01'), '%Y-%m-%d') AS data,
#             SUM(qtd * preco) AS faturamento,
#             SUM(qtd) AS quantidade_vendida,
#             SUM((preco - custo) * qtd) AS lucro
#         FROM {tabela_vendas}
#         WHERE 1=1
#         """

#         if data_inicio:
#             query += f" AND data_hora >= '{data_inicio} 00:00:00'"
#         if data_fim:
#             query += f" AND data_hora <= '{data_fim} 23:59:59'"

#         query += f" GROUP BY grupo, produto, fornecedor, DATE_FORMAT(COALESCE(data_hora, '1970-01-01'), '%Y-%m-%d') ORDER BY faturamento DESC"

#         # Log para depuração
#         print(f"Executando query em {banco}.{tabela_vendas}: {query}")
#         cursor.execute(query)
#         results = cursor.fetchall()

#         # Log para depuração
#         print(f"Dados retornados para loja {id_loja}: {results}")

#         cursor.close()
#         conn.close()

#         return jsonify(results)

#     except Exception as e:
#         error_msg = f"Erro ao consultar o banco de dados: {str(e)}"
#         print(error_msg)  # Log no servidor
#         return jsonify({"erro": error_msg}), 500





DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}
API_TOKEN = os.getenv('API_TOKEN')
API_BASE_URL = "http://192.168.4.1:8480/ws/api_sacolao"

LOJAS = {
    '1': 'PONTA NEGRA', '2': 'ALECRIM', '7': 'SAC - CENTRO VI', '100': 'LAGOA NOVA',
    '121': 'NORTE SHOPPING', '122': 'PARNAMIRIM', '131': 'ZN2', '137': 'MACAIBA',
    '140': 'MARIA LACERDA', '141': 'IGAPO'
}
ID_AVARIA = 126


def get_product_details(product_codes):
    if not product_codes:
        return {}
    details = {}
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        format_strings = ','.join(['%s'] * len(product_codes))
        query = f"SELECT codigo, preco, grupo FROM produtos WHERE codigo IN ({format_strings})"
        cursor.execute(query, tuple(product_codes))
        for row in cursor.fetchall():
            details[str(row['codigo'])] = {
                'preco': row['preco'], 'grupo': row['grupo']}
    except mysql.connector.Error as err:
        print(f"Erro no banco de dados: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
    return details


@app.route('/analise_avarias')
@login_required
def analise_avarias():

    return render_template('analise_avarias.html')


VENDAS_TABLES = {
    "1": "vendas_pn",        # PONTA NEGRA
    "2": "vendas_alecrim",   # ALECRIM
    "7": "vendas_sac6",      # SAC - CENTRO VI
    "100": "vendas_ln",      # LAGOA NOVA
    "121": "vendas_nshop",   # NORTE SHOPPING
    "122": "vendas_parna",   # PARNAMIRIM
    "131": "vendas_zn2",     # ZN2
    "137": "vendas_mac",     # MACAIBA
    "140": "vendas_ml",      # MARIA LACERDA
    "141": "vendas_igapo"    # IGAPO
}

# Versão final e limpa das funções do backend.
# Lembre-se que suas importações e constantes (LOJAS, VENDAS_TABLES, DB_CONFIG, etc.)
# devem estar definidas no seu arquivo.


def get_product_details(product_codes):
    """
    Busca os detalhes (custo, grupo e descrição) de uma lista de produtos no banco de dados.
    """
    if not product_codes:
        return {}
    details = {}
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        format_strings = ','.join(['%s'] * len(product_codes))
        query = f"SELECT codigo, descricao, custo, grupo FROM produtos WHERE codigo IN ({format_strings})"
        cursor.execute(query, tuple(product_codes))
        results = cursor.fetchall()
        for row in results:
            details[str(row['codigo'])] = {
                'custo': row.get('custo'),
                'grupo': row.get('grupo'),
                'descricao': row.get('descricao')
            }
    except mysql.connector.Error as err:
        print(f"!!! ERRO NO BANCO DE DADOS [get_product_details]: {err} !!!")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
    return details


def fetch_raw_avarias_for_period(start_date, end_date):
    """
    Busca os dados brutos de avarias de um período específico da API externa.
    """
    all_avarias = []
    date_format = "%Y-%m-%d"
    for loja_id, loja_nome in LOJAS.items():
        params = {
            'operacao': 'pedido_loja', 'operador': '999',
            'inicio': start_date.strftime(date_format), 'final': end_date.strftime(date_format),
            'token': API_TOKEN, 'loja': loja_id
        }
        try:
            response = requests.get(API_BASE_URL, params=params, timeout=25)
            response.raise_for_status()
            pedidos = response.json().get('dados', [])
            if pedidos:
                for pedido in pedidos:
                    if str(pedido.get('destino')) == str(ID_AVARIA):
                        for item in pedido.get('itens', []):
                            all_avarias.append({
                                'produto_id': str(item['produto']),
                                'quantidade': item['qtd'],
                                'loja_id': pedido.get('origem'),
                                'loja_nome': LOJAS.get(str(pedido.get('origem')), 'Desconhecida')
                            })
        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar dados da API para a loja {loja_id}: {e}")
    return all_avarias


def get_faturamento_por_loja(start_date, end_date):
    """
    Busca o faturamento de cada loja, conectando-se dinamicamente aos bancos.
    """
    faturamento_por_loja = {}
    for loja_id, loja_nome in LOJAS.items():
        db_env_var = f"LOJA_{loja_id}"
        db_name = os.getenv(db_env_var)
        table_name = VENDAS_TABLES.get(loja_id)
        if not db_name or not table_name:
            continue
        try:
            temp_db_config = DB_CONFIG.copy()
            temp_db_config['database'] = db_name
            conn = mysql.connector.connect(**temp_db_config)
            cursor = conn.cursor(dictionary=True)
            query = f"""
                SELECT SUM((IFNULL(qtd, 0) - IFNULL(qtddevolvido, 0)) * IFNULL(preco, 0) - IFNULL(desconto, 0)) as faturamento 
                FROM {table_name} 
                WHERE data_hora BETWEEN %s AND %s
            """
            cursor.execute(query, (start_date, end_date))
            result = cursor.fetchone()
            faturamento = result['faturamento'] if result and result['faturamento'] is not None else 0.0
            faturamento_por_loja[loja_id] = float(faturamento)
        except mysql.connector.Error as err:
            print(
                f"!!! ERRO NO BANCO DE DADOS [get_faturamento_por_loja] para a loja {loja_nome}: {err} !!!")
            faturamento_por_loja[loja_id] = 0.0
        finally:
            if 'conn' in locals() and conn.is_connected():
                cursor.close()
                conn.close()
    return faturamento_por_loja


@app.route('/api/dashboard-data')
def get_dashboard_data():
    """
    Rota da API completa, incluindo todos os cálculos e KPIs.
    """
    end_date_current = datetime.now()
    start_date_current = end_date_current - timedelta(days=30)
    end_date_previous = start_date_current - timedelta(days=1)
    start_date_previous = end_date_previous - timedelta(days=30)

    # Executa todas as buscas de dados necessárias
    all_avarias_current = fetch_raw_avarias_for_period(
        start_date_current, end_date_current)
    all_avarias_previous = fetch_raw_avarias_for_period(
        start_date_previous, end_date_previous)
    faturamento_lojas_current = get_faturamento_por_loja(
        start_date_current, end_date_current)
    faturamento_total_empresa = sum(faturamento_lojas_current.values())

    if not all_avarias_current:
        return jsonify({"valorTotalAvarias": 0, "totalSkusAvaria": 0, "avariasPorLoja": [], "avariasPorGrupo": [], "topProdutosAvaria": [], "detalhesCompletos": [], "kpiAvariaSobreFaturamentoEmpresa": 0})

    # Processa avarias do período anterior para cálculo de tendência
    previous_period_avarias_totals = defaultdict(float)
    if all_avarias_previous:
        unique_ids_previous = list(
            set(item['produto_id'] for item in all_avarias_previous))
        details_previous = get_product_details(unique_ids_previous)
        for avaria in all_avarias_previous:
            details = details_previous.get(avaria['produto_id'])
            if details and details.get('custo') is not None:
                previous_period_avarias_totals[avaria['loja_nome']] += float(
                    details['custo']) * int(avaria['quantidade'])

    # Processa avarias do período atual para os KPIs principais
    valor_total_avarias, skus_em_avaria, avarias_por_loja, avarias_por_grupo, avarias_por_produto, detalhes_completos_avarias = 0.0, set(
    ), defaultdict(float), defaultdict(float), defaultdict(lambda: {'valor': 0.0, 'descricao': 'N/A'}), []
    unique_ids_current = list(set(item['produto_id']
                              for item in all_avarias_current))
    product_details_current = get_product_details(unique_ids_current)

    for avaria in all_avarias_current:
        produto_id = avaria['produto_id']
        details = product_details_current.get(produto_id)
        if details and details.get('custo') is not None:
            custo, grupo, descricao, quantidade = float(details['custo']), details.get(
                'grupo', 'N/A'), details.get('descricao', 'N/A'), int(avaria['quantidade'])
            valor_item = custo * quantidade
            valor_total_avarias += valor_item
            skus_em_avaria.add(produto_id)
            avarias_por_loja[avaria['loja_nome']] += valor_item
            avarias_por_grupo[f"Grupo {grupo}"] += valor_item
            avarias_por_produto[produto_id]['valor'] += valor_item
            avarias_por_produto[produto_id]['descricao'] = descricao
            detalhes_completos_avarias.append({'loja_nome': avaria['loja_nome'], 'produto_id': produto_id,
                                              'descricao': descricao, 'grupo': grupo, 'quantidade': quantidade, 'valor_item': round(valor_item, 2)})

    # Formata os rankings e injeta os KPIs de Faturamento e Tendência
    lojas_rank = sorted([{"nomeLoja": n, "valor": round(
        v, 2)} for n, v in avarias_por_loja.items()], key=lambda item: item['valor'], reverse=True)
    loja_nome_para_id = {v: k for k, v in LOJAS.items()}

    for loja in lojas_rank:
        # Tendência vs Período Anterior
        valor_avaria_anterior = previous_period_avarias_totals.get(
            loja['nomeLoja'], 0)
        loja['variacaoPeriodoAnterior'] = None
        if valor_avaria_anterior > 0:
            variacao = ((loja['valor'] - valor_avaria_anterior) /
                        valor_avaria_anterior) * 100
            loja['variacaoPeriodoAnterior'] = round(variacao, 1)
        elif loja['valor'] > 0:
            loja['variacaoPeriodoAnterior'] = 100.0

        # % Avaria sobre Faturamento da Loja
        loja_id = loja_nome_para_id.get(loja['nomeLoja'])
        faturamento_loja = faturamento_lojas_current.get(loja_id, 0)
        loja['percentualSobreFaturamento'] = round(
            (loja['valor'] / faturamento_loja) * 100, 2) if faturamento_loja > 0 else 0.0

    # Formata os rankings restantes
    grupos_rank = sorted([{"grupoId": n, "valor": round(
        v, 2)} for n, v in avarias_por_grupo.items()], key=lambda item: item['valor'], reverse=True)
    top_10_produtos = sorted([{'produto_id': pid, 'descricao': pdata['descricao'], 'valor': pdata['valor']}
                             for pid, pdata in avarias_por_produto.items()], key=lambda item: item['valor'], reverse=True)[:10]

    # Calcula o KPI geral da empresa
    kpi_avaria_faturamento_empresa = round(
        (valor_total_avarias / faturamento_total_empresa) * 100, 2) if faturamento_total_empresa > 0 else 0

    # Monta e retorna o JSON final para o frontend
    return jsonify({
        "valorTotalAvarias": round(valor_total_avarias, 2),
        "totalSkusAvaria": len(skus_em_avaria),
        "avariasPorLoja": lojas_rank,
        "avariasPorGrupo": grupos_rank,
        "topProdutosAvaria": top_10_produtos,
        "detalhesCompletos": detalhes_completos_avarias,
        "kpiAvariaSobreFaturamentoEmpresa": kpi_avaria_faturamento_empresa
    })



# ===============================
# 2. MAPAS E DICIONÁRIOS GLOBAIS 
# ================================
LOJA_DB_MAP = {
    1: "db_ponta_negra", 2: "db_alecrim", 7: "db_sac6", 100: "db_lagoa_nova",
    121: "db_norte_shopping", 122: "db_parnamirim", 131: "db_zn2",
    137: "db_macaiba", 140: "db_maria_lacerda", 141: "db_igapo"
}

TABELAS_VENDAS_MAP = {
    1: "vendas_pn", 2: "vendas_alecrim", 7: "vendas_sac6", 100: "vendas_ln",
    121: "vendas_nshop", 122: "vendas_parna", 131: "vendas_zn2",
    137: "vendas_mac", 140: "vendas_ml", 141: "vendas_igapo"
}

LOJAS_MAP = {
    1: "PONTA NEGRA", 2: "ALECRIM", 7: "SAC - CENTRO VI", 100: "LAGOA NOVA", 121: "NORTE SHOPPING",
    122: "PARNAMIRIM", 131: "ZN2", 137: "MACAIBA", 140: "MARIA LACERDA", 141: "IGAPO"
}

GRUPOS_PRODUTOS = {
    1: "UTILIDADES", 2: "BRINQUEDOS", 4: "ELETRÔ SALÃO", 5: "COSMÉTICOS", 6: "VIDROS", 7: "MOVEIS / SALÃO", 
    8: "NATALINO", 9: "MÓVEIS INFANTIS", 10: "PAPELARIA", 11: "FESTIVO", 12: "BABY", 13: "CAMA, MESA E BANHO",
    22: "ELETRODOMÉSTICOS", 23: "ACESSÓRIOS SALÃO", 24: "MAQUIAGEM E AFINS", 25: "ESMALTES", 26: "PLÁSTICOS", 
    32: "CONFECÇÕES", 33: "BOMBOREIRE", 34: "CALÇADOS", 36: "COLORAÇÃO", 37: "PET"
}


def get_db_connection(database_name=None):
    
    # Define o banco de dados a ser usado
    db_to_connect = database_name if database_name is not None else os.getenv('DB_NAME')
    
    if not db_to_connect:
        logging.error("Nome do banco de dados não foi fornecido e DB_NAME não está no arquivo .env")
        raise ValueError("Nome do banco de dados não configurado.")

    try:
        # Usa os.getenv para buscar as credenciais do seu arquivo .env
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=db_to_connect,
            connect_timeout=15
        )
        return conn
    except mysql.connector.Error as err:
        logging.error(f"!!! ERRO AO CONECTAR AO BANCO '{db_to_connect}': {err} !!!")
        raise

# def fetch_dados_loja_do_banco(loja_id, data_inicio, data_final):
#     db_name = LOJA_DB_MAP.get(loja_id)
#     table_name = TABELAS_VENDAS_MAP.get(loja_id)
#     if not db_name or not table_name:
#         msg = f"Mapeamento de banco/tabela não encontrado para a loja {loja_id}"
#         logging.warning(msg)
#         return (loja_id, [], msg)
#     conn = None
#     try:
#         conn = get_db_connection(db_name)
#         cursor = conn.cursor(dictionary=True)
#         query = f"SELECT loja, produto, preco, qtd, qtddevolvido FROM {table_name} WHERE DATE(data_hora) BETWEEN %s AND %s"
#         cursor.execute(query, (data_inicio, data_final))
#         itens_vendidos = cursor.fetchall()
#         logging.info(f"Sucesso para loja {loja_id} ({db_name}). Itens: {len(itens_vendidos)}")
#         return (loja_id, itens_vendidos, None)
#     except Exception as err:
#         msg = f"Erro de banco de dados para loja {loja_id} ({db_name}): {err}"
#         logging.error(msg)
#         return (loja_id, [], str(err))
#     finally:
#         if conn and conn.is_connected():
#             conn.close()


# def fetch_dados_loja_do_banco(loja_id, data_inicio, data_final):
    
#     conn = None  
#     try:
#         conn = get_db_connection('estoque_db')
#         cursor = conn.cursor(dictionary=True)

#         query = """
#             SELECT 
#                 iv.loja,
#                 iv.produto,
#                 iv.qtd,
#                 iv.qtddevolvido,
#                 iv.preco,
#                 iv.custo,
#                 p.grupo,
#                 p.nu_fornecedor,
#                 p.descricao
#             FROM 
#                 itens_vendas AS iv
#             JOIN 
#                 produtos AS p ON iv.produto = p.codigo
#             WHERE 
#                 iv.loja = %(loja_id)s
#                 AND iv.data_hora BETWEEN %(data_inicio)s AND %(data_fim)s
#         """
        
#         params = {
#             'loja_id': loja_id,
#             'data_inicio': f"{data_inicio} 00:00:00",
#             'data_fim': f"{data_final} 23:59:59"
#         }

#         cursor.execute(query, params)
#         itens = cursor.fetchall()
        
#         return (loja_id, itens, None) # Retorna sucesso: (id_loja, lista_de_itens, None)

#     except Exception as e:
#         logging.error(f"Erro ao buscar dados para a loja {loja_id}: {e}")
#         return (loja_id, [], str(e)) # Retorna erro: (id_loja, lista_vazia, mensagem_de_erro)
    
#     finally:
#         # Garante que a conexão seja sempre fechada
#         if conn and conn.is_connected():
#             cursor.close()
#             conn.close()



# def fetch_dados_loja_do_banco(loja_id, data_inicio, data_final):
    
#     conn = None
#     try:
#         conn = get_db_connection('estoque_db')
#         cursor = conn.cursor(dictionary=True)

#         # Query com as colunas nfce e serie adicionadas
#         query = """
#             SELECT 
#                 iv.loja,
#                 iv.nfce,         
#                 iv.serie,        
#                 iv.produto,
#                 iv.qtd,
#                 iv.qtddevolvido,
#                 iv.preco,
#                 iv.custo,
#                 p.grupo,
#                 p.nu_fornecedor AS fornecedor,
#                 p.descricao
#             FROM 
#                 itens_vendas AS iv
#             JOIN 
#                 produtos AS p ON iv.produto = p.codigo
#             WHERE 
#                 iv.loja = %(loja_id)s
#                 AND iv.data_hora BETWEEN %(data_inicio)s AND %(data_fim)s
#         """
        
#         params = {
#             'loja_id': loja_id,
#             'data_inicio': f"{data_inicio} 00:00:00",
#             'data_fim': f"{data_final} 23:59:59"
#         }

#         cursor.execute(query, params)
#         itens = cursor.fetchall()
        
#         return (loja_id, itens, None)

#     except Exception as e:
#         logging.error(f"Erro ao buscar dados para a loja {loja_id}: {e}")
#         return (loja_id, [], str(e))
    
#     finally:
#         if conn and conn.is_connected():
#             cursor.close()
#             conn.close()

def fetch_dados_loja_do_banco(loja_id, data_inicio, data_final):
    
    conn = None
    try:
        # <<< CORREÇÃO PRINCIPAL AQUI: Chamando a função sem argumentos.
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Query com as colunas nfce e serie adicionadas
        query = """
            SELECT 
                iv.loja,
                iv.nfce,        
                iv.serie,        
                iv.produto,
                iv.qtd,
                iv.qtddevolvido,
                iv.preco,
                iv.custo,
                p.grupo,
                p.nu_fornecedor AS fornecedor,
                p.descricao
            FROM 
                itens_vendas AS iv
            JOIN 
                produtos AS p ON iv.produto = p.codigo
            WHERE 
                iv.loja = %(loja_id)s
                AND iv.data_hora BETWEEN %(data_inicio)s AND %(data_fim)s
        """
        
        params = {
            'loja_id': loja_id,
            'data_inicio': f"{data_inicio} 00:00:00",
            'data_fim': f"{data_final} 23:59:59"
        }

        cursor.execute(query, params)
        itens = cursor.fetchall()
        
        return (loja_id, itens, None)

    except Exception as e:
        # O erro "takes 0 positional arguments but 1 was given" estava acontecendo aqui.
        logging.error(f"Erro ao buscar dados para a loja {loja_id}: {e}")
        return (loja_id, [], str(e))
    
    finally:
        if conn and conn.is_connected():
            cursor.close()
            # <<< CORREÇÃO SECUNDÁRIA: Removido um '?' que causaria erro de sintaxe.
            conn.close()

# =================================
# 4. ROTA PRINCIPAL DO DASHBOARD 
# =================================
# @app.route('/api/dashboard/dados-diarios')
# @login_required
# def get_dados_diarios_dashboard():
#     """
#     Versão FINAL. Compara as vendas de dois dias específicos:
#     'dia_inicio' (Dia A) vs 'dia_fim' (Dia B).
#     """
#     def calcular_faturamento(lista_itens):
#         faturamento_total = 0.0
#         for item in lista_itens:
#             try:
#                 preco = float(item.get('preco') or 0.0)
#                 qtd = int(item.get('qtd') or 0)
#                 qtd_devolvido = int(item.get('qtddevolvido') or 0)
#                 faturamento_total += preco * max(0, qtd - qtd_devolvido)
#             except (ValueError, TypeError):
#                 logging.warning(f"Item com dados inválidos ignorado no cálculo: {item}")
#                 continue
#         return faturamento_total

#     # --- COLETA E VALIDAÇÃO DE DATAS ---
#     dia_inicio_str = request.args.get('inicio')
#     dia_final_str = request.args.get('final')
#     if not dia_inicio_str or not dia_final_str:
#         return jsonify({"erro": "As datas de início e fim são obrigatórias para a comparação."}), 400
    
#     # --- COLETA DE DADOS EM PARALELO PARA OS DOIS DIAS ---
#     todos_os_itens_dia_inicio, todos_os_itens_dia_fim, lojas_com_erro = [], [], []
#     LOJAS_IDS = list(LOJAS_MAP.keys())
    
#     with concurrent.futures.ThreadPoolExecutor(max_workers=len(LOJAS_IDS) * 2) as executor:
#         fetch_dia_inicio = partial(fetch_dados_loja_do_banco, data_inicio=dia_inicio_str, data_final=dia_inicio_str)
#         resultados_dia_inicio = list(executor.map(fetch_dia_inicio, LOJAS_IDS))
#         fetch_dia_fim = partial(fetch_dados_loja_do_banco, data_inicio=dia_final_str, data_final=dia_final_str)
#         resultados_dia_fim = list(executor.map(fetch_dia_fim, LOJAS_IDS))

#     for r in resultados_dia_inicio:
#         loja_id, itens, erro = r
#         if erro: lojas_com_erro.append({"loja": LOJAS_MAP.get(loja_id, loja_id), "data": f"Dia Início ({dia_inicio_str})", "motivo": erro})
#         else: todos_os_itens_dia_inicio.extend(itens)
#     for r in resultados_dia_fim:
#         loja_id, itens, erro = r
#         if erro: lojas_com_erro.append({"loja": LOJAS_MAP.get(loja_id, loja_id), "data": f"Dia Fim ({dia_final_str})", "motivo": erro})
#         else: todos_os_itens_dia_fim.extend(itens)

#     # --- ENRIQUECIMENTO DE DADOS ---
#     detalhes_produtos = {}
#     ids_produtos_vendidos = list(set(str(item.get('produto')) for item in todos_os_itens_dia_fim if item.get('produto')))
#     if ids_produtos_vendidos:
#         try:
#             conn_produtos = get_db_connection('estoque_db')
#             cursor = conn_produtos.cursor(dictionary=True)
#             placeholders = ','.join(['%s'] * len(ids_produtos_vendidos))
#             query = f"SELECT codigo, descricao, grupo FROM produtos WHERE codigo IN ({placeholders})"
#             cursor.execute(query, ids_produtos_vendidos)
#             for row in cursor.fetchall():
#                 detalhes_produtos[str(row['codigo'])] = {'nome': row['descricao'], 'grupo': row['grupo']}
#             conn_produtos.close()
#         except Exception as e:
#             logging.error(f"Erro ao buscar detalhes dos produtos: {e}")

#     # --- CÁLCULO DOS KPIS ---
#     faturamento_dia_fim = calcular_faturamento(todos_os_itens_dia_fim)
#     faturamento_dia_inicio = calcular_faturamento(todos_os_itens_dia_inicio)
#     diferenca = faturamento_dia_fim - faturamento_dia_inicio
#     percentual_texto = f"({diferenca / faturamento_dia_inicio:+.1%})" if faturamento_dia_inicio > 0 else ""
#     status_comp, texto_comp = ("positive", f"Positivo em R$ {diferenca:,.2f} {percentual_texto}") if diferenca >= 0 else ("negative", f"Negativo em R$ {abs(diferenca):,.2f} {percentual_texto}")
    
#     # --- CÁLCULO PARA OS GRÁFICOS ---
#     faturamento_loja_fim = defaultdict(float)
#     for item in todos_os_itens_dia_fim:
#         faturamento_loja_fim[int(item['loja'])] += calcular_faturamento([item])
    
#     faturamento_loja_inicio = defaultdict(float)
#     for item in todos_os_itens_dia_inicio:
#         faturamento_loja_inicio[int(item['loja'])] += calcular_faturamento([item])

#     dados_lojas_comp = [{'nome': loja_nome, 'faturamento_fim': faturamento_loja_fim.get(loja_id, 0), 'faturamento_inicio': faturamento_loja_inicio.get(loja_id, 0)} for loja_id, loja_nome in LOJAS_MAP.items()]
#     ranking_lojas = sorted(dados_lojas_comp, key=lambda x: x['faturamento_fim'], reverse=True)
    
#     bar_labels = [loja['nome'] for loja in ranking_lojas]
#     bar_data_fim = [round(loja['faturamento_fim'], 2) for loja in ranking_lojas]
#     bar_data_inicio = [round(loja['faturamento_inicio'], 2) for loja in ranking_lojas]

#     produtos_agregados = defaultdict(int)
#     for item in todos_os_itens_dia_fim:
#         pid = str(item.get('produto'))
#         qtd_liquida = int(item.get('qtd') or 0) - int(item.get('qtddevolvido') or 0)
#         if pid and qtd_liquida > 0: produtos_agregados[pid] += qtd_liquida
    
#     lista_produtos_ordenada = sorted(produtos_agregados.items(), key=lambda item: item[1], reverse=True)
#     top_10_produtos = [{'produto_id': pid, 'nome': detalhes_produtos.get(pid, {}).get('nome', f"Cód: {pid}"), 'categoria': GRUPOS_PRODUTOS.get(detalhes_produtos.get(pid, {}).get('grupo'), 'Outros'), 'total_vendido': qty} for pid, qty in lista_produtos_ordenada[:10]]
#     total_itens_vendidos = sum(produtos_agregados.values())
    
#     faturamento_por_grupo = defaultdict(float)
#     for item in todos_os_itens_dia_fim:
#         pid = str(item.get('produto'))
#         if pid and (detalhes := detalhes_produtos.get(pid)):
#             nome_grupo = GRUPOS_PRODUTOS.get(detalhes.get('grupo', 0), 'Outros')
#             faturamento_por_grupo[nome_grupo] += calcular_faturamento([item])
                
#     grupos_ordenados = sorted(faturamento_por_grupo.items(), key=lambda item: item[1], reverse=True)
#     radar_labels = [grupo[0] for grupo in grupos_ordenados[:5]]
#     radar_data = [round(grupo[1], 2) for grupo in grupos_ordenados[:5]]

#     # --- MONTAGEM DA RESPOSTA FINAL ---
#     resposta_final = {
#         "kpi_faturamento": {
#             "valor": faturamento_dia_fim, 
#             "valor_formatado": f"R$ {faturamento_dia_fim:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), 
#             "atualizado_em": datetime.now().strftime("%H:%M:%S")
#         },
#         "kpi_comparativo": {"texto": texto_comp.replace(",", "X").replace(".", ",").replace("X", "."), "status": status_comp},
#         "kpi_total_itens": {"valor": total_itens_vendidos},
#         "tabela_top_produtos": top_10_produtos,
#         "radar_chart_desempenho_grupo": {"labels": radar_labels, "data": radar_data},
#         "bar_chart_faturamento_loja": {"labels": bar_labels, "dataset_dia_fim": bar_data_fim, "dataset_dia_inicio": bar_data_inicio},
#         "info_processamento": {"lojas_com_erro": lojas_com_erro}
#     }
    
#     return jsonify(resposta_final)









# @app.route('/api/dashboard/dados-diarios') # A rota que o seu frontend realmente chama
# def get_dados_diarios_dashboard():
#     """
#     Versão FINAL CORRIGIDA. Compara as vendas de dois dias e calcula todos os KPIs
#     e dados para os gráficos, retornando um único JSON.
#     """
#     def calcular_faturamento(lista_itens):
#         faturamento_total = 0.0
#         for item in lista_itens:
#             try:
#                 preco = float(item.get('preco') or 0.0)
#                 qtd = int(item.get('qtd') or 0)
#                 qtd_devolvido = int(item.get('qtddevolvido') or 0)
#                 faturamento_total += preco * max(0, qtd - qtd_devolvido)
#             except (ValueError, TypeError):
#                 logging.warning(f"Item com dados inválidos ignorado no cálculo: {item}")
#                 continue
#         return faturamento_total

#     # --- COLETA E VALIDAÇÃO DE DATAS ---
#     dia_inicio_str = request.args.get('inicio')
#     dia_final_str = request.args.get('final')
#     if not dia_inicio_str or not dia_final_str:
#         return jsonify({"erro": "As datas de início e fim são obrigatórias para a comparação."}), 400
    
#     # --- COLETA DE DADOS EM PARALELO ---
#     todos_os_itens_dia_inicio, todos_os_itens_dia_fim, lojas_com_erro = [], [], []
#     LOJAS_IDS = list(LOJAS_MAP.keys())
    
#     with concurrent.futures.ThreadPoolExecutor(max_workers=len(LOJAS_IDS) * 2) as executor:
#         # Usando 'partial' para pré-configurar os argumentos da função de busca
#         fetch_dia_inicio = partial(fetch_dados_loja_do_banco, data_inicio=dia_inicio_str, data_final=dia_inicio_str)
#         resultados_dia_inicio = list(executor.map(fetch_dia_inicio, LOJAS_IDS))
        
#         fetch_dia_fim = partial(fetch_dados_loja_do_banco, data_inicio=dia_final_str, data_final=dia_final_str)
#         resultados_dia_fim = list(executor.map(fetch_dia_fim, LOJAS_IDS))

#     for r in resultados_dia_inicio:
#         loja_id, itens, erro = r
#         if erro: lojas_com_erro.append({"loja": LOJAS_MAP.get(loja_id, loja_id), "data": f"Dia Início ({dia_inicio_str})", "motivo": erro})
#         else: todos_os_itens_dia_inicio.extend(itens)
#     for r in resultados_dia_fim:
#         loja_id, itens, erro = r
#         if erro: lojas_com_erro.append({"loja": LOJAS_MAP.get(loja_id, loja_id), "data": f"Dia Fim ({dia_final_str})", "motivo": erro})
#         else: todos_os_itens_dia_fim.extend(itens)

#     # --- ENRIQUECIMENTO DE DADOS (BUSCA DE NOMES E GRUPOS DE PRODUTOS) ---
#     detalhes_produtos = {}
#     ids_produtos_vendidos = list(set(str(item.get('produto')) for item in todos_os_itens_dia_fim if item.get('produto')))
#     if ids_produtos_vendidos:
#         try:
#             # Assumindo que get_db_connection é sua função para conectar ao banco
#             conn_produtos = get_db_connection('estoque_db') 
#             cursor = conn_produtos.cursor(dictionary=True)
#             placeholders = ','.join(['%s'] * len(ids_produtos_vendidos))
#             query = f"SELECT codigo, descricao, grupo FROM produtos WHERE codigo IN ({placeholders})"
#             cursor.execute(query, ids_produtos_vendidos)
#             for row in cursor.fetchall():
#                 detalhes_produtos[str(row['codigo'])] = {'nome': row['descricao'], 'grupo': row['grupo']}
#             conn_produtos.close()
#         except Exception as e:
#             logging.error(f"Erro ao buscar detalhes dos produtos: {e}")

#     # --- CÁLCULO DOS KPIS ---
#     faturamento_dia_fim = calcular_faturamento(todos_os_itens_dia_fim)
#     faturamento_dia_inicio = calcular_faturamento(todos_os_itens_dia_inicio)
#     diferenca = faturamento_dia_fim - faturamento_dia_inicio
#     percentual_texto = f"({diferenca / faturamento_dia_inicio:+.1%})" if faturamento_dia_inicio > 0 else ""
#     status_comp, texto_comp = ("positive", f"Positivo em R$ {diferenca:,.2f} {percentual_texto}") if diferenca >= 0 else ("negative", f"Negativo em R$ {abs(diferenca):,.2f} {percentual_texto}")
    
#     # --- CÁLCULO PARA O GRÁFICO DE BARRAS (RANKING DE LOJAS) ---
#     faturamento_loja_fim = defaultdict(float)
#     for item in todos_os_itens_dia_fim:
#         faturamento_loja_fim[int(item['loja'])] += calcular_faturamento([item])
#     faturamento_loja_inicio = defaultdict(float)
#     for item in todos_os_itens_dia_inicio:
#         faturamento_loja_inicio[int(item['loja'])] += calcular_faturamento([item])

#     dados_lojas_comp = [{'nome': loja_nome, 'faturamento_fim': faturamento_loja_fim.get(loja_id, 0), 'faturamento_inicio': faturamento_loja_inicio.get(loja_id, 0)} for loja_id, loja_nome in LOJAS_MAP.items()]
#     ranking_lojas = sorted(dados_lojas_comp, key=lambda x: x['faturamento_fim'], reverse=True)
    
#     bar_labels = [loja['nome'] for loja in ranking_lojas]
#     bar_data_fim = [round(loja['faturamento_fim'], 2) for loja in ranking_lojas]
#     bar_data_inicio = [round(loja['faturamento_inicio'], 2) for loja in ranking_lojas]

#     # --- CÁLCULO PARA A TABELA E KPI DE ITENS VENDIDOS ---
#     produtos_agregados = defaultdict(int)
#     for item in todos_os_itens_dia_fim:
#         pid = str(item.get('produto'))
#         qtd_liquida = int(item.get('qtd') or 0) - int(item.get('qtddevolvido') or 0)
#         if pid and qtd_liquida > 0: produtos_agregados[pid] += qtd_liquida
    
#     lista_produtos_ordenada = sorted(produtos_agregados.items(), key=lambda item: item[1], reverse=True)
#     top_10_produtos = [{'produto_id': pid, 'nome': detalhes_produtos.get(pid, {}).get('nome', f"Cód: {pid}"), 'categoria': GRUPOS_PRODUTOS.get(detalhes_produtos.get(pid, {}).get('grupo'), 'Outros'), 'total_vendido': qty} for pid, qty in lista_produtos_ordenada[:10]]
#     total_itens_vendidos = sum(produtos_agregados.values())
    
#     # --- CÁLCULO PARA O GRÁFICO POLAR (TOP 5 GRUPOS) ---
#     faturamento_por_grupo = defaultdict(float)
#     for item in todos_os_itens_dia_fim:
#         pid = str(item.get('produto'))
#         detalhes = detalhes_produtos.get(pid)
#         if pid and detalhes:
#             # Garante que GRUPOS_PRODUTOS existe e faz a busca de forma segura
#             nome_grupo = GRUPOS_PRODUTOS.get(detalhes.get('grupo'), 'Outros')
#             faturamento_por_grupo[nome_grupo] += calcular_faturamento([item])
            
#     grupos_ordenados = sorted(faturamento_por_grupo.items(), key=lambda item: item[1], reverse=True)
#     radar_labels = [grupo[0] for grupo in grupos_ordenados[:5]]
#     radar_data = [round(grupo[1], 2) for grupo in grupos_ordenados[:5]]

#     # --- MONTAGEM DA RESPOSTA FINAL ---
#     resposta_final = {
#         "kpi_faturamento": {
#             "valor": faturamento_dia_fim, 
#             "valor_formatado": f"R$ {faturamento_dia_fim:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), 
#             "atualizado_em": datetime.now().strftime("%H:%M:%S")
#         },
#         "kpi_comparativo": {"texto": texto_comp.replace(",", "X").replace(".", ",").replace("X", "."), "status": status_comp},
#         "kpi_total_itens": {"valor": total_itens_vendidos},
#         "tabela_top_produtos": top_10_produtos,
#         "radar_chart_desempenho_grupo": {"labels": radar_labels, "data": radar_data}, # Chave correta
#         "bar_chart_faturamento_loja": {"labels": bar_labels, "dataset_dia_fim": bar_data_fim, "dataset_dia_inicio": bar_data_inicio},
#         "info_processamento": {
#             "lojas_com_erro": lojas_com_erro,
#             "lojas_consultadas": LOJAS_IDS # Adicionando lojas consultadas para o frontend
#         }
#     }
    
#     return jsonify(resposta_final)



# @app.route('/api/dashboard/dados-diarios')
# def get_dados_diarios_dashboard():
#     """
#     Versão FINAL. Compara um PERÍODO de vendas (ex: 01/01/25-15/01/25) com o
#     mesmo período no ANO ANTERIOR (01/01/24-15/01/24).
#     """
#     # Função interna para cálculo (sem alterações)
#     def calcular_faturamento(lista_itens):
#         # ... (sua função calcular_faturamento continua aqui, sem mudanças)
#         faturamento_total = 0.0
#         for item in lista_itens:
#             try:
#                 preco = float(item.get('preco') or 0.0)
#                 qtd = int(item.get('qtd') or 0)
#                 qtd_devolvido = int(item.get('qtddevolvido') or 0)
#                 faturamento_total += preco * max(0, qtd - qtd_devolvido)
#             except (ValueError, TypeError):
#                 logging.warning(f"Item com dados inválidos ignorado no cálculo: {item}")
#                 continue
#         return faturamento_total

#     # --- 1. COLETA E CÁLCULO DOS PERÍODOS ---
#     periodo_atual_inicio_str = request.args.get('inicio')
#     periodo_atual_fim_str = request.args.get('final')
#     if not periodo_atual_inicio_str or not periodo_atual_fim_str:
#         return jsonify({"erro": "As datas de início e fim do período são obrigatórias."}), 400

#     # Converte para objetos datetime para calcular o ano anterior
#     inicio_dt = datetime.strptime(periodo_atual_inicio_str, '%Y-%m-%d')
#     fim_dt = datetime.strptime(periodo_atual_fim_str, '%Y-%m-%d')
    
#     # Calcula o mesmo período no ano anterior
#     periodo_anterior_inicio_str = (inicio_dt - relativedelta(years=1)).strftime('%Y-%m-%d')
#     periodo_anterior_fim_str = (fim_dt - relativedelta(years=1)).strftime('%Y-%m-%d')
    
#     # --- 2. COLETA DE DADOS EM PARALELO PARA OS DOIS PERÍODOS ---
#     itens_periodo_anterior, itens_periodo_atual, lojas_com_erro = [], [], []
#     LOJAS_IDS = list(LOJAS_MAP.keys())
    
#     with concurrent.futures.ThreadPoolExecutor(max_workers=len(LOJAS_IDS) * 2) as executor:
#         # Busca dados para o período ANTERIOR
#         fetch_anterior = partial(fetch_dados_loja_do_banco, data_inicio=periodo_anterior_inicio_str, data_final=periodo_anterior_fim_str)
#         resultados_periodo_anterior = list(executor.map(fetch_anterior, LOJAS_IDS))
        
#         # Busca dados para o período ATUAL
#         fetch_atual = partial(fetch_dados_loja_do_banco, data_inicio=periodo_atual_inicio_str, data_final=periodo_atual_fim_str)
#         resultados_periodo_atual = list(executor.map(fetch_atual, LOJAS_IDS))

#     for r in resultados_periodo_anterior:
#         loja_id, itens, erro = r
#         if erro: lojas_com_erro.append({"loja": LOJAS_MAP.get(loja_id, loja_id), "data": f"Período Anterior", "motivo": erro})
#         else: itens_periodo_anterior.extend(itens)
#     for r in resultados_periodo_atual:
#         loja_id, itens, erro = r
#         if erro: lojas_com_erro.append({"loja": LOJAS_MAP.get(loja_id, loja_id), "data": f"Período Atual", "motivo": erro})
#         else: itens_periodo_atual.extend(itens)

#     # --- 3. ENRIQUECIMENTO DE DADOS (sem alterações, mas agora usa itens do período atual) ---
#     detalhes_produtos = {}
#     ids_produtos_vendidos = list(set(str(item.get('produto')) for item in itens_periodo_atual if item.get('produto')))
#     if ids_produtos_vendidos:
#         try:
#             conn_produtos = get_db_connection('estoque_db')
#             # ... (resto do seu código de enriquecimento sem alterações)
#             cursor = conn_produtos.cursor(dictionary=True)
#             placeholders = ','.join(['%s'] * len(ids_produtos_vendidos))
#             query = f"SELECT codigo, descricao, grupo FROM produtos WHERE codigo IN ({placeholders})"
#             cursor.execute(query, ids_produtos_vendidos)
#             for row in cursor.fetchall():
#                 detalhes_produtos[str(row['codigo'])] = {'nome': row['descricao'], 'grupo': row['grupo']}
#             conn_produtos.close()
#         except Exception as e:
#             logging.error(f"Erro ao buscar detalhes dos produtos: {e}")

#     # --- 4. CÁLCULO DOS KPIS E GRÁFICOS (usando os novos dados de PERÍODO) ---
#     faturamento_periodo_atual = calcular_faturamento(itens_periodo_atual)
#     faturamento_periodo_anterior = calcular_faturamento(itens_periodo_anterior)
#     diferenca = faturamento_periodo_atual - faturamento_periodo_anterior
#     percentual_texto = f"({diferenca / faturamento_periodo_anterior:+.1%})" if faturamento_periodo_anterior > 0 else ""
#     status_comp, texto_comp = ("positive", f"Positivo em R$ {diferenca:,.2f} {percentual_texto}") if diferenca >= 0 else ("negative", f"Negativo em R$ {abs(diferenca):,.2f} {percentual_texto}")
    
#     faturamento_loja_atual = defaultdict(float)
#     for item in itens_periodo_atual:
#         faturamento_loja_atual[int(item['loja'])] += calcular_faturamento([item])
#     faturamento_loja_anterior = defaultdict(float)
#     for item in itens_periodo_anterior:
#         faturamento_loja_anterior[int(item['loja'])] += calcular_faturamento([item])

#     dados_lojas_comp = [{'nome': loja_nome, 'faturamento_atual': faturamento_loja_atual.get(loja_id, 0), 'faturamento_anterior': faturamento_loja_anterior.get(loja_id, 0)} for loja_id, loja_nome in LOJAS_MAP.items()]
#     ranking_lojas = sorted(dados_lojas_comp, key=lambda x: x['faturamento_atual'], reverse=True)
    
#     bar_labels = [loja['nome'] for loja in ranking_lojas]
#     bar_data_atual = [round(loja['faturamento_atual'], 2) for loja in ranking_lojas]
#     bar_data_anterior = [round(loja['faturamento_anterior'], 2) for loja in ranking_lojas]

#     # ... (resto dos cálculos para tabela e radar chart usam o PERÍODO ATUAL)
#     produtos_agregados = defaultdict(int)
#     for item in itens_periodo_atual:
#         pid = str(item.get('produto'))
#         qtd_liquida = int(item.get('qtd') or 0) - int(item.get('qtddevolvido') or 0)
#         if pid and qtd_liquida > 0: produtos_agregados[pid] += qtd_liquida
    
#     lista_produtos_ordenada = sorted(produtos_agregados.items(), key=lambda item: item[1], reverse=True)
#     top_10_produtos = [{'produto_id': pid, 'nome': detalhes_produtos.get(pid, {}).get('nome', f"Cód: {pid}"), 'categoria': GRUPOS_PRODUTOS.get(detalhes_produtos.get(pid, {}).get('grupo'), 'Outros'), 'total_vendido': qty} for pid, qty in lista_produtos_ordenada[:10]]
#     total_itens_vendidos = sum(produtos_agregados.values())
    
#     faturamento_por_grupo = defaultdict(float)
#     for item in itens_periodo_atual:
#         pid = str(item.get('produto'))
#         if pid and (detalhes := detalhes_produtos.get(pid)):
#             nome_grupo = GRUPOS_PRODUTOS.get(detalhes.get('grupo', 0), 'Outros')
#             faturamento_por_grupo[nome_grupo] += calcular_faturamento([item])
            
#     grupos_ordenados = sorted(faturamento_por_grupo.items(), key=lambda item: item[1], reverse=True)
#     radar_labels = [grupo[0] for grupo in grupos_ordenados[:5]]
#     radar_data = [round(grupo[1], 2) for grupo in grupos_ordenados[:5]]
                                    
    

#     # --- MONTAGEM DA RESPOSTA FINAL (com nomes de variáveis atualizados) ---
#     resposta_final = {
#         "kpi_faturamento": {
#             "valor": faturamento_periodo_atual, 
#             "valor_formatado": f"R$ {faturamento_periodo_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), 
#             "atualizado_em": datetime.now().strftime("%H:%M:%S")
#         },
#         "kpi_comparativo": {"texto": texto_comp.replace(",", "X").replace(".", ",").replace("X", "."), "status": status_comp},
#         "kpi_total_itens": {"valor": total_itens_vendidos},
#         "tabela_top_produtos": top_10_produtos,
#         "radar_chart_desempenho_grupo": {"labels": radar_labels, "data": radar_data},
#         "bar_chart_faturamento_loja": {
#             "labels": bar_labels, 
#             "dataset_dia_fim": bar_data_atual,       # Agora representa o Período Atual
#             "dataset_dia_inicio": bar_data_anterior  # Agora representa o Período Anterior
#         },
#         "info_processamento": {"lojas_com_erro": lojas_com_erro, "lojas_consultadas": LOJAS_IDS}
#     }
    
#     return jsonify(resposta_final)





# ==============================================================================
# 2. ROTA PRINCIPAL DO DASHBOARD (VERSÃO COMPLETA E FINAL)
# ==============================================================================
# @app.route('/api/dashboard/dados-diarios')
# def get_dados_diarios_dashboard():
#     """
#     Versão final. Compara um PERÍODO de vendas com o mesmo período no ANO ANTERIOR,
#     calculando todos os KPIs e dados para os gráficos.
#     """
#     def calcular_faturamento(lista_itens):
#         faturamento_total = 0.0
#         for item in lista_itens:
#             try:
#                 preco = float(item.get('preco') or 0.0)
#                 qtd = int(item.get('qtd') or 0)
#                 qtd_devolvido = int(item.get('qtddevolvido') or 0)
#                 faturamento_total += preco * max(0, qtd - qtd_devolvido)
#             except (ValueError, TypeError):
#                 logging.warning(f"Item com dados inválidos ignorado no cálculo: {item}")
#                 continue
#         return faturamento_total

#     # --- 1. COLETA E CÁLCULO DOS PERÍODOS ---
#     periodo_atual_inicio_str = request.args.get('inicio')
#     periodo_atual_fim_str = request.args.get('final')
#     if not periodo_atual_inicio_str or not periodo_atual_fim_str:
#         return jsonify({"erro": "As datas de início e fim do período são obrigatórias."}), 400

#     inicio_dt = datetime.strptime(periodo_atual_inicio_str, '%Y-%m-%d')
#     fim_dt = datetime.strptime(periodo_atual_fim_str, '%Y-%m-%d')
    
#     periodo_anterior_inicio_str = (inicio_dt - relativedelta(years=1)).strftime('%Y-%m-%d')
#     periodo_anterior_fim_str = (fim_dt - relativedelta(years=1)).strftime('%Y-%m-%d')
    
#     # --- 2. COLETA DE DADOS EM PARALELO PARA OS DOIS PERÍODOS ---
#     itens_periodo_anterior, itens_periodo_atual, lojas_com_erro = [], [], []
#     LOJAS_IDS = list(LOJAS_MAP.keys())
    
#     with concurrent.futures.ThreadPoolExecutor(max_workers=len(LOJAS_IDS) * 2) as executor:
#         fetch_anterior = partial(fetch_dados_loja_do_banco, data_inicio=periodo_anterior_inicio_str, data_final=periodo_anterior_fim_str)
#         resultados_periodo_anterior = list(executor.map(fetch_anterior, LOJAS_IDS))
        
#         fetch_atual = partial(fetch_dados_loja_do_banco, data_inicio=periodo_atual_inicio_str, data_final=periodo_atual_fim_str)
#         resultados_periodo_atual = list(executor.map(fetch_atual, LOJAS_IDS))

#     for r in resultados_periodo_anterior:
#         loja_id, itens, erro = r
#         if erro: lojas_com_erro.append({"loja": LOJAS_MAP.get(loja_id, loja_id), "data": f"Período Anterior", "motivo": erro})
#         else: itens_periodo_anterior.extend(itens)
#     for r in resultados_periodo_atual:
#         loja_id, itens, erro = r
#         if erro: lojas_com_erro.append({"loja": LOJAS_MAP.get(loja_id, loja_id), "data": f"Período Atual", "motivo": erro})
#         else: itens_periodo_atual.extend(itens)

#     # --- 3. ENRIQUECIMENTO DE DADOS (BUSCA DE NOMES E GRUPOS DE PRODUTOS) ---
#     detalhes_produtos = {}
#     ids_produtos_vendidos = list(set(str(item.get('produto')) for item in itens_periodo_atual if item.get('produto')))
#     if ids_produtos_vendidos:
#         try:
#             conn_produtos = get_db_connection('estoque_db')
#             cursor = conn_produtos.cursor(dictionary=True)
#             placeholders = ','.join(['%s'] * len(ids_produtos_vendidos))
#             query = f"SELECT codigo, descricao, grupo FROM produtos WHERE codigo IN ({placeholders})"
#             cursor.execute(query, ids_produtos_vendidos)
#             for row in cursor.fetchall():
#                 detalhes_produtos[str(row['codigo'])] = {'nome': row['descricao'], 'grupo': row['grupo']}
#             conn_produtos.close()
#         except Exception as e:
#             logging.error(f"Erro ao buscar detalhes dos produtos: {e}")

#     # --- 4. CÁLCULO DOS KPIS E GRÁFICOS ---
#     faturamento_periodo_atual = calcular_faturamento(itens_periodo_atual)
#     faturamento_periodo_anterior = calcular_faturamento(itens_periodo_anterior)
#     diferenca = faturamento_periodo_atual - faturamento_periodo_anterior
#     percentual_texto = f"({diferenca / faturamento_periodo_anterior:+.1%})" if faturamento_periodo_anterior > 0 else ""
#     status_comp, texto_comp = ("positive", f"Positivo em R$ {diferenca:,.2f} {percentual_texto}") if diferenca >= 0 else ("negative", f"Negativo em R$ {abs(diferenca):,.2f} {percentual_texto}")
    
#     faturamento_loja_atual = defaultdict(float)
#     for item in itens_periodo_atual:
#         faturamento_loja_atual[int(item['loja'])] += calcular_faturamento([item])
#     faturamento_loja_anterior = defaultdict(float)
#     for item in itens_periodo_anterior:
#         faturamento_loja_anterior[int(item['loja'])] += calcular_faturamento([item])

#     dados_lojas_comp = [{'nome': loja_nome, 'faturamento_atual': faturamento_loja_atual.get(loja_id, 0), 'faturamento_anterior': faturamento_loja_anterior.get(loja_id, 0)} for loja_id, loja_nome in LOJAS_MAP.items()]
#     ranking_lojas = sorted(dados_lojas_comp, key=lambda x: x['faturamento_atual'], reverse=True)
    
#     bar_labels = [loja['nome'] for loja in ranking_lojas]
#     bar_data_atual = [round(loja['faturamento_atual'], 2) for loja in ranking_lojas]
#     bar_data_anterior = [round(loja['faturamento_anterior'], 2) for loja in ranking_lojas]

#     produtos_agregados = defaultdict(int)
#     for item in itens_periodo_atual:
#         pid = str(item.get('produto'))
#         qtd_liquida = int(item.get('qtd') or 0) - int(item.get('qtddevolvido') or 0)
#         if pid and qtd_liquida > 0: produtos_agregados[pid] += qtd_liquida
    
#     lista_produtos_ordenada = sorted(produtos_agregados.items(), key=lambda item: item[1], reverse=True)
#     top_10_produtos = [{'produto_id': pid, 'nome': detalhes_produtos.get(pid, {}).get('nome', f"Cód: {pid}"), 'categoria': GRUPOS_PRODUTOS.get(detalhes_produtos.get(pid, {}).get('grupo'), 'Outros'), 'total_vendido': qty} for pid, qty in lista_produtos_ordenada[:10]]
#     total_itens_vendidos = sum(produtos_agregados.values())
    
#     faturamento_por_grupo = defaultdict(float)
#     for item in itens_periodo_atual:
#         pid = str(item.get('produto'))
#         if pid and (detalhes := detalhes_produtos.get(pid)):
#             nome_grupo = GRUPOS_PRODUTOS.get(detalhes.get('grupo', 0), 'Outros')
#             faturamento_por_grupo[nome_grupo] += calcular_faturamento([item])
            
#     grupos_ordenados = sorted(faturamento_por_grupo.items(), key=lambda item: item[1], reverse=True)
#     radar_labels = [grupo[0] for grupo in grupos_ordenados[:5]]
#     radar_data = [round(grupo[1], 2) for grupo in grupos_ordenados[:5]]

#     faturamento_por_produto = defaultdict(float)
#     for item in itens_periodo_atual:
#         pid = str(item.get('produto'))
#         if pid: faturamento_por_produto[pid] += calcular_faturamento([item])
#     top_10_faturamento = sorted(faturamento_por_produto.items(), key=lambda item: item[1], reverse=True)[:10]

#     kpi_top_produtos_faturamento = []
#     if faturamento_periodo_atual > 0:
#         for pid, faturamento_item in top_10_faturamento:
#             percentual = (faturamento_item / faturamento_periodo_atual) * 100
#             kpi_top_produtos_faturamento.append({
#                 "nome": detalhes_produtos.get(pid, {}).get('nome', f'Cód: {pid}'),
#                 "faturamento_formatado": f"R$ {faturamento_item:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
#                 "percentual": round(percentual, 2)
#             })

#     # --- 5. MONTAGEM DA RESPOSTA FINAL ---
#     resposta_final = {
#         "kpi_faturamento": {
#             "valor": faturamento_periodo_atual, 
#             "valor_formatado": f"R$ {faturamento_periodo_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), 
#             "atualizado_em": datetime.now().strftime("%H:%M:%S")
#         },
#         "kpi_comparativo": {"texto": texto_comp.replace(",", "X").replace(".", ",").replace("X", "."), "status": status_comp},
#         "kpi_total_itens": {"valor": total_itens_vendidos},
#         "tabela_top_produtos": top_10_produtos,
#         "radar_chart_desempenho_grupo": {"labels": radar_labels, "data": radar_data},
#         "bar_chart_faturamento_loja": {
#             "labels": bar_labels, 
#             "dataset_dia_fim": bar_data_atual,
#             "dataset_dia_inicio": bar_data_anterior
#         },
#         "kpi_top_produtos_faturamento": kpi_top_produtos_faturamento,
#         "info_processamento": {"lojas_com_erro": lojas_com_erro, "lojas_consultadas": LOJAS_IDS}
#     }
    
#     return jsonify(resposta_final)




# @app.route('/api/dashboard/dados-diarios')
# def get_dados_diarios_dashboard():
#     """
#     Versão final. Compara um PERÍODO de vendas com o mesmo período no ANO ANTERIOR,
#     calculando todos os KPIs e dados para os gráficos.
#     """
#     def calcular_faturamento(lista_itens):
#         faturamento_total = 0.0
#         for item in lista_itens:
#             try:
#                 preco = float(item.get('preco') or 0.0)
#                 qtd = int(item.get('qtd') or 0)
#                 qtd_devolvido = int(item.get('qtddevolvido') or 0)
#                 faturamento_total += preco * max(0, qtd - qtd_devolvido)
#             except (ValueError, TypeError):
#                 logging.warning(f"Item com dados inválidos ignorado no cálculo: {item}")
#                 continue
#         return faturamento_total

#     # --- 1. COLETA E CÁLCULO DOS PERÍODOS ---
#     periodo_atual_inicio_str = request.args.get('inicio')
#     periodo_atual_fim_str = request.args.get('final')
#     if not periodo_atual_inicio_str or not periodo_atual_fim_str:
#         return jsonify({"erro": "As datas de início e fim do período são obrigatórias."}), 400

#     inicio_dt = datetime.strptime(periodo_atual_inicio_str, '%Y-%m-%d')
#     fim_dt = datetime.strptime(periodo_atual_fim_str, '%Y-%m-%d')
    
#     periodo_anterior_inicio_str = (inicio_dt - relativedelta(years=1)).strftime('%Y-%m-%d')
#     periodo_anterior_fim_str = (fim_dt - relativedelta(years=1)).strftime('%Y-%m-%d')
    
#     # --- 2. COLETA DE DADOS EM PARALELO PARA OS DOIS PERÍODOS ---
#     itens_periodo_anterior, itens_periodo_atual, lojas_com_erro = [], [], []
#     LOJAS_IDS = list(LOJAS_MAP.keys())
    
#     with concurrent.futures.ThreadPoolExecutor(max_workers=len(LOJAS_IDS) * 2) as executor:
#         fetch_anterior = partial(fetch_dados_loja_do_banco, data_inicio=periodo_anterior_inicio_str, data_final=periodo_anterior_fim_str)
#         resultados_periodo_anterior = list(executor.map(fetch_anterior, LOJAS_IDS))
        
#         fetch_atual = partial(fetch_dados_loja_do_banco, data_inicio=periodo_atual_inicio_str, data_final=periodo_atual_fim_str)
#         resultados_periodo_atual = list(executor.map(fetch_atual, LOJAS_IDS))

#     for r in resultados_periodo_anterior:
#         loja_id, itens, erro = r
#         if erro: lojas_com_erro.append({"loja": LOJAS_MAP.get(loja_id, loja_id), "data": f"Período Anterior", "motivo": erro})
#         else: itens_periodo_anterior.extend(itens)
#     for r in resultados_periodo_atual:
#         loja_id, itens, erro = r
#         if erro: lojas_com_erro.append({"loja": LOJAS_MAP.get(loja_id, loja_id), "data": f"Período Atual", "motivo": erro})
#         else: itens_periodo_atual.extend(itens)

#     # --- 3. ENRIQUECIMENTO DE DADOS (BUSCA DE NOMES E GRUPOS DE PRODUTOS) ---
#     detalhes_produtos = {}
#     ids_produtos_vendidos = list(set(str(item.get('produto')) for item in itens_periodo_atual if item.get('produto')))
#     if ids_produtos_vendidos:
#         try:
#             conn_produtos = get_db_connection('estoque_db')
#             cursor = conn_produtos.cursor(dictionary=True)
#             placeholders = ','.join(['%s'] * len(ids_produtos_vendidos))
#             query = f"SELECT codigo, descricao, grupo FROM produtos WHERE codigo IN ({placeholders})"
#             cursor.execute(query, ids_produtos_vendidos)
#             for row in cursor.fetchall():
#                 detalhes_produtos[str(row['codigo'])] = {'nome': row['descricao'], 'grupo': row['grupo']}
#             conn_produtos.close()
#         except Exception as e:
#             logging.error(f"Erro ao buscar detalhes dos produtos: {e}")

#     # --- 4. CÁLCULO DOS KPIS E GRÁFICOS ---
#     # ... (cálculos anteriores de faturamento, comparativo, ranking de lojas, etc., permanecem os mesmos) ...
#     faturamento_periodo_atual = calcular_faturamento(itens_periodo_atual)
#     faturamento_periodo_anterior = calcular_faturamento(itens_periodo_anterior)
#     diferenca = faturamento_periodo_atual - faturamento_periodo_anterior
#     percentual_texto = f"({diferenca / faturamento_periodo_anterior:+.1%})" if faturamento_periodo_anterior > 0 else ""
#     status_comp, texto_comp = ("positive", f"Positivo em R$ {diferenca:,.2f} {percentual_texto}") if diferenca >= 0 else ("negative", f"Negativo em R$ {abs(diferenca):,.2f} {percentual_texto}")
#     faturamento_loja_atual = defaultdict(float)
#     for item in itens_periodo_atual:
#         faturamento_loja_atual[int(item['loja'])] += calcular_faturamento([item])
#     faturamento_loja_anterior = defaultdict(float)
#     for item in itens_periodo_anterior:
#         faturamento_loja_anterior[int(item['loja'])] += calcular_faturamento([item])
#     dados_lojas_comp = [{'nome': loja_nome, 'faturamento_atual': faturamento_loja_atual.get(loja_id, 0), 'faturamento_anterior': faturamento_loja_anterior.get(loja_id, 0)} for loja_id, loja_nome in LOJAS_MAP.items()]
#     ranking_lojas = sorted(dados_lojas_comp, key=lambda x: x['faturamento_atual'], reverse=True)
#     bar_labels = [loja['nome'] for loja in ranking_lojas]
#     bar_data_atual = [round(loja['faturamento_atual'], 2) for loja in ranking_lojas]
#     bar_data_anterior = [round(loja['faturamento_anterior'], 2) for loja in ranking_lojas]
#     produtos_agregados = defaultdict(int)
#     for item in itens_periodo_atual:
#         pid = str(item.get('produto'))
#         qtd_liquida = int(item.get('qtd') or 0) - int(item.get('qtddevolvido') or 0)
#         if pid and qtd_liquida > 0: produtos_agregados[pid] += qtd_liquida
#     lista_produtos_ordenada = sorted(produtos_agregados.items(), key=lambda item: item[1], reverse=True)
#     top_10_produtos = [{'produto_id': pid, 'nome': detalhes_produtos.get(pid, {}).get('nome', f"Cód: {pid}"), 'categoria': GRUPOS_PRODUTOS.get(detalhes_produtos.get(pid, {}).get('grupo'), 'Outros'), 'total_vendido': qty} for pid, qty in lista_produtos_ordenada[:10]]
#     total_itens_vendidos = sum(produtos_agregados.values())
#     faturamento_por_grupo = defaultdict(float)
#     for item in itens_periodo_atual:
#         pid = str(item.get('produto'))
#         if pid and (detalhes := detalhes_produtos.get(pid)):
#             nome_grupo = GRUPOS_PRODUTOS.get(detalhes.get('grupo', 0), 'Outros')
#             faturamento_por_grupo[nome_grupo] += calcular_faturamento([item])
#     grupos_ordenados = sorted(faturamento_por_grupo.items(), key=lambda item: item[1], reverse=True)
#     radar_labels = [grupo[0] for grupo in grupos_ordenados[:5]]
#     radar_data = [round(grupo[1], 2) for grupo in grupos_ordenados[:5]]
#     faturamento_por_produto = defaultdict(float)
#     for item in itens_periodo_atual:
#         pid = str(item.get('produto'))
#         if pid: faturamento_por_produto[pid] += calcular_faturamento([item])
#     top_10_faturamento = sorted(faturamento_por_produto.items(), key=lambda item: item[1], reverse=True)[:10]
#     kpi_top_produtos_faturamento = []
#     if faturamento_periodo_atual > 0:
#         for pid, faturamento_item in top_10_faturamento:
#             percentual = (faturamento_item / faturamento_periodo_atual) * 100
#             kpi_top_produtos_faturamento.append({
#                 "nome": detalhes_produtos.get(pid, {}).get('nome', f'Cód: {pid}'),
#                 "faturamento_formatado": f"R$ {faturamento_item:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
#                 "percentual": round(percentual, 2)
#             })

#     # --- CÁLCULO PARA O KPI DE TICKET MÉDIO (AGORA PARA TODOS) ---
#     vendas_unicas_por_grupo = defaultdict(set)
#     faturamento_por_grupo_tkt = defaultdict(float)
#     for item in itens_periodo_atual:
#         pid = str(item.get('produto'))
#         detalhes = detalhes_produtos.get(pid)
#         if pid and detalhes:
#             nome_grupo = GRUPOS_PRODUTOS.get(detalhes.get('grupo'), 'Outros')
#             faturamento_por_grupo_tkt[nome_grupo] += calcular_faturamento([item])
#             venda_id = f"{item['loja']}-{item['nfce']}-{item['serie']}"
#             vendas_unicas_por_grupo[nome_grupo].add(venda_id)
    
#     ticket_medio_por_grupo = []
#     for grupo, faturamento in faturamento_por_grupo_tkt.items():
#         num_vendas = len(vendas_unicas_por_grupo[grupo])
#         if num_vendas > 0:
#             tkt_medio = faturamento / num_vendas
#             ticket_medio_por_grupo.append({"nome": grupo, "valor": tkt_medio})
    
#     # ====================== ALTERAÇÃO AQUI ======================
#     # Removemos o [:5] para pegar todos os grupos
#     kpi_ticket_medio_grupo = sorted(ticket_medio_por_grupo, key=lambda x: x['valor'], reverse=True)
#     # ==========================================================

#     vendas_unicas_por_loja = defaultdict(set)
#     for item in itens_periodo_atual:
#         venda_id = f"{item['loja']}-{item['nfce']}-{item['serie']}"
#         vendas_unicas_por_loja[int(item['loja'])].add(venda_id)
        
#     ticket_medio_por_loja = []
#     for loja_id, faturamento in faturamento_loja_atual.items():
#         num_vendas = len(vendas_unicas_por_loja[loja_id])
#         if num_vendas > 0:
#             tkt_medio = faturamento / num_vendas
#             ticket_medio_por_loja.append({"nome": LOJAS_MAP.get(loja_id, f"Loja {loja_id}"), "valor": tkt_medio})

#     # ====================== ALTERAÇÃO AQUI ======================
#     # Removemos o [:5] para pegar todas as lojas
#     kpi_ticket_medio_loja = sorted(ticket_medio_por_loja, key=lambda x: x['valor'], reverse=True)
#     # ==========================================================

#     # --- 5. MONTAGEM DA RESPOSTA FINAL ---
#     resposta_final = {
#         "kpi_faturamento": {
#             "valor": faturamento_periodo_atual, 
#             "valor_formatado": f"R$ {faturamento_periodo_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), 
#             "atualizado_em": datetime.now().strftime("%H:%M:%S")
#         },
#         "kpi_comparativo": {"texto": texto_comp.replace(",", "X").replace(".", ",").replace("X", "."), "status": status_comp},
#         "kpi_total_itens": {"valor": total_itens_vendidos},
#         "tabela_top_produtos": top_10_produtos,
#         "radar_chart_desempenho_grupo": {"labels": radar_labels, "data": radar_data},
#         "bar_chart_faturamento_loja": {
#             "labels": bar_labels, 
#             "dataset_dia_fim": bar_data_atual,
#             "dataset_dia_inicio": bar_data_anterior
#         },
#         "kpi_top_produtos_faturamento": kpi_top_produtos_faturamento,
#         "kpi_ticket_medio_grupo": kpi_ticket_medio_grupo,
#         "kpi_ticket_medio_loja": kpi_ticket_medio_loja,
#         "info_processamento": {"lojas_com_erro": lojas_com_erro, "lojas_consultadas": LOJAS_IDS}
#     }
    
#     return jsonify(resposta_final)


@app.route('/api/dashboard/dados-diarios')
def get_dados_diarios_dashboard():
    """
    Versão final. Compara um PERÍODO de vendas com o mesmo período no ANO ANTERIOR,
    calculando todos os KPIs e dados para os gráficos.
    """
    def calcular_faturamento(lista_itens):
        faturamento_total = 0.0
        for item in lista_itens:
            try:
                preco = float(item.get('preco') or 0.0)
                qtd = int(item.get('qtd') or 0)
                qtd_devolvido = int(item.get('qtddevolvido') or 0)
                faturamento_total += preco * max(0, qtd - qtd_devolvido)
            except (ValueError, TypeError):
                logging.warning(f"Item com dados inválidos ignorado no cálculo: {item}")
                continue
        return faturamento_total

    # --- 1. COLETA E CÁLCULO DOS PERÍODOS ---
    periodo_atual_inicio_str = request.args.get('inicio')
    periodo_atual_fim_str = request.args.get('final')
    if not periodo_atual_inicio_str or not periodo_atual_fim_str:
        return jsonify({"erro": "As datas de início e fim do período são obrigatórias."}), 400

    inicio_dt = datetime.strptime(periodo_atual_inicio_str, '%Y-%m-%d')
    fim_dt = datetime.strptime(periodo_atual_fim_str, '%Y-%m-%d')
    
    periodo_anterior_inicio_str = (inicio_dt - relativedelta(years=1)).strftime('%Y-%m-%d')
    periodo_anterior_fim_str = (fim_dt - relativedelta(years=1)).strftime('%Y-%m-%d')
    
    # --- 2. COLETA DE DADOS EM PARALELO PARA OS DOIS PERÍODOS ---
    itens_periodo_anterior, itens_periodo_atual, lojas_com_erro = [], [], []
    LOJAS_IDS = list(LOJAS_MAP.keys())
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(LOJAS_IDS) * 2) as executor:
        fetch_anterior = partial(fetch_dados_loja_do_banco, data_inicio=periodo_anterior_inicio_str, data_final=periodo_anterior_fim_str)
        resultados_periodo_anterior = list(executor.map(fetch_anterior, LOJAS_IDS))
        
        fetch_atual = partial(fetch_dados_loja_do_banco, data_inicio=periodo_atual_inicio_str, data_final=periodo_atual_fim_str)
        resultados_periodo_atual = list(executor.map(fetch_atual, LOJAS_IDS))

    for r in resultados_periodo_anterior:
        loja_id, itens, erro = r
        if erro: lojas_com_erro.append({"loja": LOJAS_MAP.get(loja_id, loja_id), "data": f"Período Anterior", "motivo": erro})
        else: itens_periodo_anterior.extend(itens)
    for r in resultados_periodo_atual:
        loja_id, itens, erro = r
        if erro: lojas_com_erro.append({"loja": LOJAS_MAP.get(loja_id, loja_id), "data": f"Período Atual", "motivo": erro})
        else: itens_periodo_atual.extend(itens)

    # --- 3. ENRIQUECIMENTO DE DADOS (BUSCA DE NOMES E GRUPOS DE PRODUTOS) ---
    detalhes_produtos = {}
    ids_produtos_vendidos = list(set(str(item.get('produto')) for item in itens_periodo_atual if item.get('produto')))
    if ids_produtos_vendidos:
        try:
            # <<< CORREÇÃO AQUI: A chamada agora não passa nenhum argumento.
            conn_produtos = get_db_connection()
            cursor = conn_produtos.cursor(dictionary=True)
            placeholders = ','.join(['%s'] * len(ids_produtos_vendidos))
            query = f"SELECT codigo, descricao, grupo FROM produtos WHERE codigo IN ({placeholders})"
            cursor.execute(query, ids_produtos_vendidos)
            for row in cursor.fetchall():
                detalhes_produtos[str(row['codigo'])] = {'nome': row['descricao'], 'grupo': row['grupo']}
            conn_produtos.close()
        except Exception as e:
            logging.error(f"Erro ao buscar detalhes dos produtos: {e}")

    # --- 4. CÁLCULO DOS KPIS E GRÁFICOS ---
    faturamento_periodo_atual = calcular_faturamento(itens_periodo_atual)
    faturamento_periodo_anterior = calcular_faturamento(itens_periodo_anterior)
    diferenca = faturamento_periodo_atual - faturamento_periodo_anterior
    percentual_texto = f"({diferenca / faturamento_periodo_anterior:+.1%})" if faturamento_periodo_anterior > 0 else ""
    status_comp, texto_comp = ("positive", f"Positivo em R$ {diferenca:,.2f} {percentual_texto}") if diferenca >= 0 else ("negative", f"Negativo em R$ {abs(diferenca):,.2f} {percentual_texto}")
    faturamento_loja_atual = defaultdict(float)
    for item in itens_periodo_atual:
        faturamento_loja_atual[int(item['loja'])] += calcular_faturamento([item])
    faturamento_loja_anterior = defaultdict(float)
    for item in itens_periodo_anterior:
        faturamento_loja_anterior[int(item['loja'])] += calcular_faturamento([item])
    dados_lojas_comp = [{'nome': loja_nome, 'faturamento_atual': faturamento_loja_atual.get(loja_id, 0), 'faturamento_anterior': faturamento_loja_anterior.get(loja_id, 0)} for loja_id, loja_nome in LOJAS_MAP.items()]
    ranking_lojas = sorted(dados_lojas_comp, key=lambda x: x['faturamento_atual'], reverse=True)
    bar_labels = [loja['nome'] for loja in ranking_lojas]
    bar_data_atual = [round(loja['faturamento_atual'], 2) for loja in ranking_lojas]
    bar_data_anterior = [round(loja['faturamento_anterior'], 2) for loja in ranking_lojas]
    produtos_agregados = defaultdict(int)
    for item in itens_periodo_atual:
        pid = str(item.get('produto'))
        qtd_liquida = int(item.get('qtd') or 0) - int(item.get('qtddevolvido') or 0)
        if pid and qtd_liquida > 0: produtos_agregados[pid] += qtd_liquida
    lista_produtos_ordenada = sorted(produtos_agregados.items(), key=lambda item: item[1], reverse=True)
    top_10_produtos = [{'produto_id': pid, 'nome': detalhes_produtos.get(pid, {}).get('nome', f"Cód: {pid}"), 'categoria': GRUPOS_PRODUTOS.get(detalhes_produtos.get(pid, {}).get('grupo'), 'Outros'), 'total_vendido': qty} for pid, qty in lista_produtos_ordenada[:10]]
    total_itens_vendidos = sum(produtos_agregados.values())
    faturamento_por_grupo = defaultdict(float)
    for item in itens_periodo_atual:
        pid = str(item.get('produto'))
        if pid and (detalhes := detalhes_produtos.get(pid)):
            nome_grupo = GRUPOS_PRODUTOS.get(detalhes.get('grupo', 0), 'Outros')
            faturamento_por_grupo[nome_grupo] += calcular_faturamento([item])
    grupos_ordenados = sorted(faturamento_por_grupo.items(), key=lambda item: item[1], reverse=True)
    radar_labels = [grupo[0] for grupo in grupos_ordenados[:5]]
    radar_data = [round(grupo[1], 2) for grupo in grupos_ordenados[:5]]
    faturamento_por_produto = defaultdict(float)
    for item in itens_periodo_atual:
        pid = str(item.get('produto'))
        if pid: faturamento_por_produto[pid] += calcular_faturamento([item])
    top_10_faturamento = sorted(faturamento_por_produto.items(), key=lambda item: item[1], reverse=True)[:10]
    kpi_top_produtos_faturamento = []
    if faturamento_periodo_atual > 0:
        for pid, faturamento_item in top_10_faturamento:
            percentual = (faturamento_item / faturamento_periodo_atual) * 100
            kpi_top_produtos_faturamento.append({
                "nome": detalhes_produtos.get(pid, {}).get('nome', f'Cód: {pid}'),
                "faturamento_formatado": f"R$ {faturamento_item:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "percentual": round(percentual, 2)
            })
    vendas_unicas_por_grupo = defaultdict(set)
    faturamento_por_grupo_tkt = defaultdict(float)
    for item in itens_periodo_atual:
        pid = str(item.get('produto'))
        detalhes = detalhes_produtos.get(pid)
        if pid and detalhes:
            nome_grupo = GRUPOS_PRODUTOS.get(detalhes.get('grupo'), 'Outros')
            faturamento_por_grupo_tkt[nome_grupo] += calcular_faturamento([item])
            venda_id = f"{item['loja']}-{item['nfce']}-{item['serie']}"
            vendas_unicas_por_grupo[nome_grupo].add(venda_id)
    ticket_medio_por_grupo = []
    for grupo, faturamento in faturamento_por_grupo_tkt.items():
        num_vendas = len(vendas_unicas_por_grupo[grupo])
        if num_vendas > 0:
            tkt_medio = faturamento / num_vendas
            ticket_medio_por_grupo.append({"nome": grupo, "valor": tkt_medio})
    kpi_ticket_medio_grupo = sorted(ticket_medio_por_grupo, key=lambda x: x['valor'], reverse=True)
    vendas_unicas_por_loja = defaultdict(set)
    for item in itens_periodo_atual:
        venda_id = f"{item['loja']}-{item['nfce']}-{item['serie']}"
        vendas_unicas_por_loja[int(item['loja'])].add(venda_id)
    ticket_medio_por_loja = []
    for loja_id, faturamento in faturamento_loja_atual.items():
        num_vendas = len(vendas_unicas_por_loja[loja_id])
        if num_vendas > 0:
            tkt_medio = faturamento / num_vendas
            ticket_medio_por_loja.append({"nome": LOJAS_MAP.get(loja_id, f"Loja {loja_id}"), "valor": tkt_medio})
    kpi_ticket_medio_loja = sorted(ticket_medio_por_loja, key=lambda x: x['valor'], reverse=True)

    # --- 5. MONTAGEM DA RESPOSTA FINAL ---
    resposta_final = {
        "kpi_faturamento": {
            "valor": faturamento_periodo_atual, 
            "valor_formatado": f"R$ {faturamento_periodo_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), 
            "atualizado_em": datetime.now().strftime("%H:%M:%S")
        },
        "kpi_comparativo": {"texto": texto_comp.replace(",", "X").replace(".", ",").replace("X", "."), "status": status_comp},
        "kpi_total_itens": {"valor": total_itens_vendidos},
        "tabela_top_produtos": top_10_produtos,
        "radar_chart_desempenho_grupo": {"labels": radar_labels, "data": radar_data},
        "bar_chart_faturamento_loja": {
            "labels": bar_labels, 
            "dataset_dia_fim": bar_data_atual,
            "dataset_dia_inicio": bar_data_anterior
        },
        "kpi_top_produtos_faturamento": kpi_top_produtos_faturamento,
        "kpi_ticket_medio_grupo": kpi_ticket_medio_grupo,
        "kpi_ticket_medio_loja": kpi_ticket_medio_loja,
        "info_processamento": {"lojas_com_erro": lojas_com_erro, "lojas_consultadas": LOJAS_IDS}
    }
    
    return jsonify(resposta_final)



# ===================================================================
# ROTA PARA ANÁLISE DE VENDA CASADA (CESTA DE COMPRAS)
# ===================================================================

def get_product_name(product_id):
    """Função auxiliar para buscar o nome de um único produto."""
    try:
        # Conecta-se ao banco de dados principal onde a tabela 'produtos' está
        conn = get_db_connection('estoque_db') 
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT descricao FROM produtos WHERE codigo = %s", (product_id,))
        result = cursor.fetchone()
        conn.close()
        return result['descricao'] if result else f"Produto {product_id}"
    except Exception as e:
        logging.error(f"Erro ao buscar nome do produto {product_id}: {e}")
        return f"Produto {product_id}"

# 
# ===================================================================
# ROTA PARA ANÁLISE GERAL DA LOJA 
# ===================================================================
@app.route('/api/analise-geral')
@login_required
def api_analise_geral():
    data_str = request.args.get('data')
    loja_id_param = request.args.get('loja_id', 'TODAS')

    if not data_str:
        return jsonify({"erro": "A Data é obrigatória."}), 400

    lojas_para_consultar = []
    if loja_id_param and loja_id_param.upper() != 'TODAS':
        try:
            lojas_para_consultar.append(int(loja_id_param))
        except ValueError:
            return jsonify({"erro": f"ID de loja inválido: {loja_id_param}"}), 400
    else:
        lojas_para_consultar = list(LOJAS_MAP.keys())

    # Estrutura para agrupar todos os produtos por nota
    notas_do_dia = defaultdict(list)
    for loja_id in lojas_para_consultar:
        db_name = LOJA_DB_MAP.get(loja_id)
        table_name = TABELAS_VENDAS_MAP.get(loja_id)
        if not db_name or not table_name: continue
        
        conn = None
        try:
            conn = get_db_connection(db_name)
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT CONCAT(loja, '-', nfce, '-', serie) as nota_id, produto FROM {table_name} WHERE DATE(data_hora) = %s"
            cursor.execute(query, (data_str,))
            for row in cursor.fetchall():
                notas_do_dia[row['nota_id']].append(str(row['produto']))
        except Exception as e:
            logging.error(f"Erro ao buscar vendas gerais na loja {loja_id}: {e}")
        finally:
            if conn and conn.is_connected(): conn.close()

    if not notas_do_dia:
        return jsonify({
            "total_cestas": 0, "total_itens_vendidos": 0, "media_itens_cesta": 0,
            "cestas_item_unico": 0, "percentual_item_unico": 0,
            "cestas_itens_multiplos": 0, "percentual_itens_multiplos": 0,
            "top_produtos_sozinhos": []
        })

    # Calcular os KPIs
    total_cestas = len(notas_do_dia)
    total_itens_vendidos = 0
    cestas_item_unico = 0
    produtos_vendidos_sozinhos = defaultdict(int)

    for nota_id, produtos_na_cesta in notas_do_dia.items():
        total_itens_vendidos += len(produtos_na_cesta)
        produtos_unicos = set(produtos_na_cesta)
        if len(produtos_unicos) == 1:
            cestas_item_unico += 1
            pid_sozinho = list(produtos_unicos)[0]
            produtos_vendidos_sozinhos[pid_sozinho] += 1
            
    cestas_itens_multiplos = total_cestas - cestas_item_unico
    
    # Busca nomes dos produtos mais vendidos sozinhos
    ranking_sozinhos = sorted(produtos_vendidos_sozinhos.items(), key=lambda item: item[1], reverse=True)[:20]
    ids_sozinhos = [item[0] for item in ranking_sozinhos]
    nomes_map = get_product_name_batch(ids_sozinhos) if ids_sozinhos else {}

    resultado_final = {
        "total_cestas": total_cestas,
        "total_itens_vendidos": total_itens_vendidos,
        "media_itens_cesta": (total_itens_vendidos / total_cestas) if total_cestas > 0 else 0,
        "cestas_item_unico": cestas_item_unico,
        "percentual_item_unico": (cestas_item_unico / total_cestas * 100) if total_cestas > 0 else 0,
        "cestas_itens_multiplos": cestas_itens_multiplos,
        "percentual_itens_multiplos": (cestas_itens_multiplos / total_cestas * 100) if total_cestas > 0 else 0,
        "top_produtos_sozinhos": [
            {"id": pid, "descricao": nomes_map.get(pid, f"Produto {pid}"), "frequencia": freq}
            for pid, freq in ranking_sozinhos
        ]
    }

    return jsonify(resultado_final)


# Adicione esta função auxiliar também, para buscar nomes de produtos em lote
def get_product_name_batch(product_ids):
    if not product_ids: return {}
    names = {}
    try:
        conn = get_db_connection('estoque_db')
        cursor = conn.cursor(dictionary=True)
        placeholders = ','.join(['%s'] * len(product_ids))
        query = f"SELECT codigo, descricao FROM produtos WHERE codigo IN ({placeholders})"
        cursor.execute(query, tuple(product_ids))
        for row in cursor.fetchall():
            names[str(row['codigo'])] = row['descricao']
        conn.close()
    except Exception as e:
        logging.error(f"Erro ao buscar nomes de produtos em lote: {e}")
    return names


@app.route('/analise_venda_casada')
@login_required
def analise_venda_casada():
    return render_template('analise_venda_casada.html')

@app.route('/faturamento')
@login_required
def faturamento():
    return render_template('faturamento.html')



@app.route('/pda')
@login_required
def pda_index():
    print("Acessando rota /pda (interface simplificada)")
    # Nova página simplificada para PDA
    return render_template('pda_index.html')


@app.route('/pda_principal')
@login_required
def pda_principal():
    print("Acessando rota /pda_principal")
    return render_template('pda_principal.html')


@app.route('/logout', methods=['GET'])
@login_required
# @login_required
def logout():
    print("Executando logout")
    session.pop('user', None)
    print("Usuário deslogado. Redirecionando para login.")
    return redirect(url_for('login_page'))


@app.route('/index')
@login_required
# @login_required
def index():
    print("Acessando rota /index (Gestão de Estoque)")
    return render_template('index.html')


@app.route('/')
@login_required
def pagina_principal():
    print("Acessando rota / (pagina_principal)")
    return render_template('pagina_principal.html')


@app.route('/relatorio', methods=['GET'])
@login_required
def relatorio_page():
    print("Acessando rota /relatorio")
    return render_template('relatorio.html')


@app.route('/notificacoes/count', methods=['GET'])
@login_required
# @login_required
def notificacoes_count():
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'count': 0}), 500

        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT COUNT(*) AS count FROM solicitacoes WHERE status = 'Pendente'")
        result = cur.fetchone()
        count = result['count'] if result else 0

        cur.close()
        conn.close()
        return jsonify({'count': count})
    except Exception as e:
        print(f"Erro ao contar notificações: {str(e)}")
        return jsonify({'count': 0}), 500


@app.route('/acomp_solic_deposito')
@login_required
def acomp_solic_deposito():
    print("Acessando rota /acomp_solic_deposito")
    filial_id = request.args.get('filial_id', '')
    status_filtrado = request.args.get('status', '')
    format_type = request.args.get('format', '')
    erro = None
    solicitacoes = []
    filiais = []

    try:
        conn = get_db_connection()
        if conn is None:
            print("Falha na conexão com o banco de dados")
            erro = "Erro ao conectar ao banco de dados"
            if format_type == 'json':
                return jsonify({'solicitacoes': [], 'erro': erro})
            return render_template('acomp_solic_deposito.html', solicitacoes=[], erro=erro, filiais=[], filial_id=filial_id, status_filtrado=status_filtrado)

        cur = conn.cursor(dictionary=True)

        # Buscar lista de filiais
        print("Buscando filiais...")
        cur.execute(
            "SELECT DISTINCT filial_id1, filial_nome1 FROM filiais ORDER BY filial_nome1")
        filiais = cur.fetchall()
        print(f"Filiais encontradas: {filiais}")

        # Consulta com JOIN para garantir nome da filial atualizado
        query = '''
            SELECT s.id, s.numero_solicitacao, s.filial_id, f.filial_nome1 AS filial_nome,
                   s.tipo_solicitacao, s.titulo, s.descricao,
                   s.quantidade, s.data_hora, s.matricula, s.nome_usuario, s.status
            FROM solicitacoes s
            JOIN filiais f ON s.filial_id = f.filial_id1
            WHERE 1=1
        '''
        params = []

        if filial_id and filial_id.isdigit():
            query += ' AND s.filial_id = %s'
            params.append(filial_id)
        if status_filtrado:
            query += ' AND s.status = %s'
            params.append(status_filtrado)

        query += ' ORDER BY s.data_hora DESC'

        print(f"Executando consulta: {query} com parâmetros: {params}")
        cur.execute(query, params)
        solicitacoes = cur.fetchall()
        print(f"Solicitações encontradas: {len(solicitacoes)}")
        print(f"Dados das solicitações: {solicitacoes}")

        cur.close()
        conn.close()

        if format_type == 'json':
            return jsonify({'solicitacoes': solicitacoes})

        print("Tentando renderizar o template...")
        return render_template(
            'acomp_solic_deposito.html',
            solicitacoes=solicitacoes,
            erro=erro,
            filiais=filiais,
            filial_id=filial_id,
            status_filtrado=status_filtrado
        )

    except Exception as e:
        print(f"Erro ao buscar solicitações: {str(e)}")
        erro = f"Ocorreu um erro ao carregar as solicitações: {str(e)}"
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        if format_type == 'json':
            return jsonify({'solicitacoes': [], 'erro': erro})
        return render_template(
            'acomp_solic_deposito.html',
            solicitacoes=[],
            erro=erro,
            filiais=[],
            filial_id=filial_id,
            status_filtrado=status_filtrado

        )


@app.route('/salvar_resposta', methods=['POST'])
@login_required
def salvar_resposta():
    print("Recebida requisição para salvar resposta")
    try:
        data = request.get_json()
        print(f"Dados recebidos: {data}")
        solicitacao_id = str(data.get('solicitacao_id')).strip()
        mensagem = data.get('mensagem')

        if not solicitacao_id or not mensagem:
            print("solicitacao_id ou mensagem não fornecidos")
            return jsonify({'success': False, 'error': 'solicitacao_id e mensagem são obrigatórios'}), 400

        # Conectar ao banco
        conn = get_db_connection()
        if conn is None:
            print("Falha na conexão com o banco de dados")
            return jsonify({'success': False, 'error': 'Erro ao conectar ao banco'}), 500

        # Garantir que a conexão não está em modo autocommit falso
        conn.autocommit = True
        cur = conn.cursor(dictionary=True)
        print(f"Conexão ao banco estabelecida. Database: {conn.database}")

        # Depuração: listar todas as solicitações visíveis
        cur.execute(
            "SELECT numero_solicitacao, data_hora, data_liberacao FROM solicitacoes")
        all_solicitacoes = cur.fetchall()
        print(f"Todas as solicitações visíveis: {all_solicitacoes}")

        # Validar a solicitação
        query = """
            SELECT s.id, s.numero_solicitacao, s.data_hora, s.data_liberacao
            FROM solicitacoes s
            JOIN filiais f ON s.filial_id = f.filial_id1
            WHERE CAST(s.numero_solicitacao AS CHAR) = %s
        """
        cur.execute(query, (solicitacao_id,))
        solicitacao = cur.fetchone()
        print(f"Resultado da consulta: {solicitacao}")

        if not solicitacao:
            print(
                f"Solicitação com numero_solicitacao {solicitacao_id} não encontrada")
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': f'Solicitação com numero_solicitacao {solicitacao_id} não encontrada'}), 404

        # Obter data atual
        data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"Data atual do sistema: {data_atual}")

        # Obter o nome do usuário logado da sessão
        user_session = session.get('user')
        nome_usuario = user_session['nome'] if user_session and 'nome' in user_session else 'Usuário Desconhecido'
        print(f"Usuário logado: {nome_usuario}")

        filial_nome = "Depósito Central"
        print(f"Filial: {filial_nome}")

        # Inserir a resposta
        query = """
            INSERT INTO respostas (solicitacao_id, mensagem, data_hora, nome_filial, nome_usuario)
            VALUES (%s, %s, %s, %s, %s)
        """
        params = (solicitacao_id, mensagem, data_atual,
                  filial_nome, nome_usuario)
        print(f"Executando query: {query} com parâmetros: {params}")
        cur.execute(query, params)
        conn.commit()

        # Verificar se a inserção foi bem-sucedida
        cur.execute("SELECT * FROM respostas WHERE solicitacao_id = %s AND data_hora = %s",
                    (solicitacao_id, data_atual))
        inserted_resposta = cur.fetchone()
        if not inserted_resposta:
            print("Falha ao verificar a inserção da resposta")
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Falha ao salvar a resposta no banco'}), 500

        print(
            f"Resposta salva com sucesso para solicitação {solicitacao_id}: {inserted_resposta}")
        cur.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Resposta salva com sucesso'})
    except mysql.connector.Error as sql_error:
        print(f"Erro de banco de dados: {str(sql_error)}")
        return jsonify({'success': False, 'error': f'Erro de banco de dados: {str(sql_error)}'}), 500
    except Exception as e:
        print(f"Erro genérico: {str(e)}")
        return jsonify({'success': False, 'error': f'Erro ao processar: {str(e)}'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


@app.route('/historico/<solicitacao_id>', methods=['GET'])
@login_required
def historico(solicitacao_id):
    print(f"Buscando histórico para solicitação {solicitacao_id}")
    try:
        conn = get_db_connection()
        if conn is None:
            print("Falha na conexão com o banco de dados")
            return jsonify({'success': False, 'error': 'Erro ao conectar ao banco'}), 500

        cur = conn.cursor(dictionary=True)
        query = """
            SELECT mensagem, data_hora, nome_filial, nome_usuario
            FROM respostas
            WHERE solicitacao_id = %s
            ORDER BY data_hora ASC
        """
        cur.execute(query, (solicitacao_id,))
        historico = cur.fetchall()
        print(f"Histórico encontrado: {historico}")

        cur.close()
        conn.close()
        return jsonify({'success': True, 'historico': historico})
    except mysql.connector.Error as sql_error:
        print(f"Erro de banco de dados: {str(sql_error)}")
        return jsonify({'success': False, 'error': f'Erro de banco de dados: {str(sql_error)}'}), 500
    except Exception as e:
        print(f"Erro genérico: {str(e)}")
        return jsonify({'success': False, 'error': f'Erro ao processar: {str(e)}'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


@app.route('/aprovar_solicitacao/<int:id>', methods=['POST'])
@login_required
def aprovar_solicitacao(id):
    print(f"Recebida requisição para aprovar solicitação ID: {id}")
    try:
        conn = get_db_connection()
        if conn is None:
            print("Falha na conexão com o banco de dados")
            return jsonify({'success': False, 'error': 'Erro ao conectar ao banco'}), 500

        cur = conn.cursor()

        cur.execute("SELECT id FROM solicitacoes WHERE id = %s", (id,))
        if not cur.fetchone():
            print(f"Solicitação ID {id} não encontrada")
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Solicitação não encontrada'}), 404

        data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"Data atual: {data_atual}")

        cur.execute("SHOW COLUMNS FROM solicitacoes LIKE 'data_liberacao'")
        data_liberacao_exists = cur.fetchone() is not None
        print(f"Coluna data_liberacao existe: {data_liberacao_exists}")

        # Obter o nome do usuário logado da sessão
        user_session = session.get('user')
        if not user_session or 'nome' not in user_session:
            print("Nenhuma sessão de usuário encontrada ou nome ausente")
            usuario = 'Usuário Desconhecido'
        else:
            usuario = user_session['nome']
        print(f"Usuário logado: {usuario}")

        query = "UPDATE solicitacoes SET status = %s"
        params = ['Aprovada']
        if data_liberacao_exists:
            query += ", data_liberacao = %s"
            params.append(data_atual)
        query += ", usuario_aprovou = %s WHERE id = %s"
        params.extend([usuario, id])

        print(f"Executando query: {query} com parâmetros: {params}")
        cur.execute(query, params)
        conn.commit()
        print(
            f"Solicitação {id} aprovada com sucesso em {data_atual} por {usuario}")

        cur.execute("SELECT status FROM solicitacoes WHERE id = %s", (id,))
        updated_status = cur.fetchone()[0]
        print(f"Status atualizado verificado: {updated_status}")

        cur.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Solicitação aprovada com sucesso'})
    except mysql.connector.Error as sql_error:
        print(
            f"Erro de banco de dados ao aprovar solicitação: {str(sql_error)}")
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        return jsonify({'success': False, 'error': f'Erro de banco de dados: {str(sql_error)}'}), 500
    except Exception as e:
        print(f"Erro genérico ao aprovar solicitação: {str(e)}")
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        return jsonify({'success': False, 'error': f'Erro ao processar a solicitação: {str(e)}'}), 500


@app.route('/cancelar_solicitacao/<int:id>', methods=['POST'])
@login_required
def cancelar_solicitacao(id):
    print(f"Recebida requisição para cancelar solicitação ID: {id}")
    try:
        conn = get_db_connection()
        if conn is None:
            print("Falha na conexão com o banco de dados")
            return jsonify({'success': False, 'error': 'Erro ao conectar ao banco'}), 500

        cur = conn.cursor()

        cur.execute("SELECT id, status FROM solicitacoes WHERE id = %s", (id,))
        solicitacao = cur.fetchone()
        if not solicitacao:
            print(f"Solicitação ID {id} não encontrada")
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Solicitação não encontrada'}), 404

        current_status = solicitacao[1]
        if current_status == 'Cancelada':
            print(f"Solicitação ID {id} já está cancelada")
            cur.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Solicitação já está cancelada'}), 400

        data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"Data atual: {data_atual}")

        cur.execute("SHOW COLUMNS FROM solicitacoes LIKE 'data_liberacao'")
        data_liberacao_exists = cur.fetchone() is not None
        print(f"Coluna data_liberacao existe: {data_liberacao_exists}")

        # Obter o nome do usuário logado da sessão
        user_session = session.get('user')
        if not user_session or 'nome' not in user_session:
            print("Nenhuma sessão de usuário encontrada ou nome ausente")
            usuario = 'Usuário Desconhecido'
        else:
            usuario = user_session['nome']
        print(f"Usuário logado: {usuario}")

        query = "UPDATE solicitacoes SET status = %s"
        params = ['Cancelada']
        if data_liberacao_exists:
            query += ", data_liberacao = %s"
            params.append(data_atual)
        query += ", usuario_aprovou = %s WHERE id = %s"
        params.extend([usuario, id])

        print(f"Executando query: {query} com parâmetros: {params}")
        cur.execute(query, params)
        conn.commit()
        print(
            f"Solicitação {id} cancelada com sucesso em {data_atual} por {usuario}")

        cur.execute("SELECT status FROM solicitacoes WHERE id = %s", (id,))
        updated_status = cur.fetchone()[0]
        print(f"Status atualizado verificado: {updated_status}")

        cur.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Solicitação cancelada com sucesso'})
    except mysql.connector.Error as sql_error:
        print(
            f"Erro de banco de dados ao cancelar solicitação: {str(sql_error)}")
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        return jsonify({'success': False, 'error': f'Erro de banco de dados: {str(sql_error)}'}), 500
    except Exception as e:
        print(f"Erro genérico ao cancelar solicitação: {str(e)}")
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        return jsonify({'success': False, 'error': f'Erro ao processar a solicitação: {str(e)}'}), 500


@app.route('/solicitacoes_loja', methods=['GET'])
@login_required
def solicitacoes_loja():
    print("Acessando rota /solicitacoes_loja")
    filial = request.args.get('filial', '')
    erro = None
    solicitacoes = []
    respostas = []

    try:
        conn = get_db_connection()
        if conn is None:
            print("Falha na conexão com o banco de dados")
            erro = "Erro ao conectar ao banco de dados"
            return render_template('solicitacoes_loja.html', solicitacoes=[], respostas=[], erro=erro, filial=filial)

        cur = conn.cursor(dictionary=True)
        # Buscar solicitações
        query_solicitacoes = '''
            SELECT s.id, s.numero_solicitacao, s.filial_id, f.filial_nome1 AS filial_nome, s.tipo_solicitacao, s.titulo, s.descricao, 
                   s.quantidade, s.data_hora, s.matricula, s.nome_usuario, s.status
            FROM solicitacoes s
            JOIN filiais f ON s.filial_id = f.filial_id1
            WHERE 1=1
        '''
        params = []

        if filial and filial.isdigit():
            query_solicitacoes += ' AND s.filial_id = %s'
            params.append(filial)

        query_solicitacoes += ' ORDER BY s.data_hora DESC'
        print(
            f"Executando consulta de solicitações: {query_solicitacoes} com parâmetros: {params}")
        cur.execute(query_solicitacoes, params)
        solicitacoes = cur.fetchall()
        print(f"Solicitações encontradas: {len(solicitacoes)}")
        print(f"Dados das solicitações: {solicitacoes}")

        # Buscar respostas usando solicitacao_id
        query_respostas = '''
            SELECT r.solicitacao_id, r.mensagem, r.data_hora, r.nome_usuario
            FROM respostas r
            WHERE 1=1
        '''
        if filial and filial.isdigit():
            query_respostas += ' AND r.solicitacao_id IN (SELECT id FROM solicitacoes WHERE filial_id = %s)'
            params = [filial]
        else:
            params = []

        query_respostas += ' ORDER BY r.data_hora ASC'
        print(
            f"Executando consulta de respostas: {query_respostas} com parâmetros: {params}")
        cur.execute(query_respostas, params)
        respostas = cur.fetchall()
        print(f"Respostas encontradas: {len(respostas)}")
        print(f"Dados das respostas: {respostas}")

        cur.close()
        conn.close()
        return render_template('solicitacoes_loja.html', solicitacoes=solicitacoes, respostas=respostas, erro=erro, filial=filial)
    except Exception as e:
        print(f"Erro ao buscar solicitações e respostas: {str(e)}")
        erro = "Ocorreu um erro ao carregar as solicitações e respostas"
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        return render_template('solicitacoes_loja.html', solicitacoes=[], respostas=[], erro=erro, filial=filial)


@app.route('/responder_solicitacao/<int:id>', methods=['POST'])
@login_required
def responder_solicitacao(id):
    print(f"Acessando rota /responder_solicitacao/{id}")
    try:
        data = request.get_json()
        # Ajustado para 'mensagem' para alinhar com o banco
        mensagem = data.get('mensagem')

        if not mensagem:
            print("Erro: Mensagem é obrigatória")
            return jsonify({'success': False, 'error': 'Mensagem é obrigatória'}), 400

        conn = get_db_connection()
        if conn is None:
            print("Erro: Falha ao conectar ao banco de dados")
            return jsonify({'success': False, 'error': 'Erro ao conectar ao banco'}), 500

        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id FROM solicitacoes WHERE id = %s", (id,))
        solicitacao = cur.fetchone()
        if not solicitacao:
            cur.close()
            conn.close()
            print(f"Erro: Solicitação ID {id} não encontrada")
            return jsonify({'success': False, 'error': 'Solicitação não encontrada'}), 404

        user_session = session.get('user', {})
        nome_usuario = user_session.get('nome', 'Depósito Desconhecido')
        print(f"Usuário da sessão: {nome_usuario}")

        query = '''
            INSERT INTO respostas (solicitacao_id, mensagem, data_hora, nome_usuario)
            VALUES (%s, %s, %s, %s)
        '''
        params = (id, mensagem, datetime.now().strftime(
            '%Y-%m-%d %H:%M:%S'), nome_usuario)
        print(f"Executando query: {query} com parâmetros: {params}")
        cur.execute(query, params)
        conn.commit()

        cur.close()
        conn.close()
        print("Resposta enviada com sucesso")
        return jsonify({'success': True, 'message': 'Resposta enviada com sucesso'})
    except Exception as e:
        print(f"Erro ao responder solicitação: {str(e)}")
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/atualizar_solicitacao/<int:id>', methods=['POST'])
@login_required
def atualizar_solicitacao(id):
    print(f"Acessando rota /atualizar_solicitacao/{id}")
    try:
        data = request.get_json()
        titulo = data.get('titulo')
        descricao = data.get('descricao')

        if not all([titulo, descricao]):
            return jsonify({'success': False, 'error': 'Título e descrição são obrigatórios'}), 400

        conn = get_db_connection()
        if conn is None:
            return jsonify({'success': False, 'error': 'Erro ao conectar ao banco'}), 500

        cur = conn.cursor()
        query = '''
            UPDATE solicitacoes SET titulo = %s, descricao = %s WHERE id = %s
        '''
        params = (titulo, descricao, id)
        print(f"Executando query: {query} com parâmetros: {params}")
        cur.execute(query, params)
        conn.commit()

        if cur.rowcount == 0:
            return jsonify({'success': False, 'error': 'Solicitação não encontrada'}), 404

        cur.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Solicitação atualizada com sucesso'})
    except Exception as e:
        print(f"Erro ao atualizar solicitação: {str(e)}")
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/criar_solicitacao', methods=['POST'])
@login_required
def criar_solicitacao():
    print("Acessando rota /criar_solicitacao")
    try:
        data = request.get_json()
        filial_id = data.get('filial_id')
        tipo_solicitacao = data.get('tipo_solicitacao')
        quantidade = data.get('quantidade')
        titulo = data.get('titulo')
        descricao = data.get('descricao')

        if not all([filial_id, tipo_solicitacao, quantidade, titulo, descricao]):
            return jsonify({'success': False, 'error': 'Todos os campos são obrigatórios'}), 400

        conn = get_db_connection()
        if conn is None:
            return jsonify({'success': False, 'error': 'Erro ao conectar ao banco'}), 500

        cur = conn.cursor()
        cur.execute("SELECT MAX(numero_solicitacao) FROM solicitacoes")
        max_numero = cur.fetchone()[0]
        numero_solicitacao = str(int(max_numero) + 1) if max_numero else '1'

        user_session = session.get('user', {})
        matricula = user_session.get('matricula', '12345')
        nome_usuario = user_session.get('nome', 'Usuário Teste')

        query = '''
            INSERT INTO solicitacoes (numero_solicitacao, filial_id, tipo_solicitacao, titulo, descricao, quantidade, data_hora, matricula, nome_usuario, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        params = (
            numero_solicitacao,
            filial_id,
            tipo_solicitacao,
            titulo,
            descricao,
            quantidade,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            matricula,
            nome_usuario,
            'Pendente'
        )
        print(f"Executando query: {query} com parâmetros: {params}")
        cur.execute(query, params)
        conn.commit()

        cur.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Solicitação criada com sucesso', 'numero_solicitacao': numero_solicitacao})
    except Exception as e:
        print(f"Erro ao criar solicitação: {str(e)}")
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/consultas_avancadas')
@login_required
def consultas_avancadas_page():
    print("Acessando rota /consultas_avancadas/page")
    return render_template('consultas_avancadas.html')


@app.route('/consultas_avancadas/dados')
@login_required
def consultas_avancadas_dados():
    grupo = request.args.get('grupo')
    fornecedor = request.args.get('fornecedor')
    codigoBarra = request.args.get('codigoBarra')
    comSaldo = request.args.get('comSaldo', 'false') == 'true'
    semSaldo = request.args.get('semSaldo', 'false') == 'true'

    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        query = 'SELECT * FROM produtos'
        params = []
        conditions = []

        if grupo:
            conditions.append('grupo = %s')
            params.append(grupo)
        if fornecedor:
            conditions.append('nu_fornecedor= %s')
            params.append(fornecedor)
        if codigoBarra:
            conditions.append('(codigo = %s OR barras = %s)')
            params.extend([codigoBarra, codigoBarra])
        if comSaldo and not semSaldo:
            conditions.append('saldo > 0')
        elif semSaldo and not comSaldo:
            conditions.append('saldo = 0')

        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)

        print(f"Executando consulta: {query} com parâmetros: {params}")
        cur.execute(query, params)
        data = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(data)
    except mysql.connector.Error as db_err:
        print(f"Erro no banco de dados: {db_err}")
        return jsonify({'error': 'Erro ao carregar consultas'}), 500

    return jsonify({'error': 'Erro ao carregar filtros'}), 500


@app.route('/consultas_avancadas/filtros')
@login_required
def consultas_avancadas_filtros():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        # Modifique esta query para ordenar por nome_fantasia
        query = """
        SELECT DISTINCT nu_fornecedor, nome_fantasia, grupo 
        FROM produtos 
        WHERE nome_fantasia IS NOT NULL 
        ORDER BY nome_fantasia ASC
        """

        cur.execute(query)
        data = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(data)
    except Exception as e:
        print(f"Erro: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/credito_debito')
@login_required
def credito_debito():
    print("Acessando rota /credito_debito")

    # Inicializa todas as variáveis com valores padrão para evitar erros no template
    usuarios_processados = []
    total_pedidos_geral, total_skus_geral, pedidos_com_div_geral, pedidos_sem_div_geral = 0, 0, 0, 0
    total_a_pagar = 0.0
    erro = None
    conn = None

    try:
        conn = get_db_connection()
        if not conn:
            raise Exception("Falha na conexão com o banco de dados.")

        cur = conn.cursor(dictionary=True)

        # 1. Buscar a lista de usuários (Conferentes e Separadores) que finalizaram pedidos
        query_usuarios = """
            (SELECT separador AS nome, 'Separador' AS tipo FROM conferencia WHERE separador IS NOT NULL AND status = 'CONFERIDO' GROUP BY separador)
            UNION
            (SELECT conferente AS nome, 'Conferente' AS tipo FROM conferencia WHERE conferente IS NOT NULL AND status = 'CONFERIDO' GROUP BY conferente)
        """
        cur.execute(query_usuarios)
        usuarios_brutos = cur.fetchall()

        # 2. Para cada usuário, calcular suas métricas com base nos dados CONSOLIDADOS
        for usuario in usuarios_brutos:
            nome_usuario = usuario['nome']
            tipo_usuario = usuario['tipo']
            coluna_filtro = 'separador' if tipo_usuario == 'Separador' else 'conferente'

            # Query para obter os dados já consolidados por produto para este usuário
            query_consolidada = f"""
                SELECT
                    numero_pedido,
                    quantidade_pedida,
                    SUM(CAST(quantidade_conferida AS SIGNED)) AS total_conferido
                FROM conferencia
                WHERE {coluna_filtro} = %s AND status = 'CONFERIDO'
                GROUP BY numero_pedido, codigo, quantidade_pedida
            """
            cur.execute(query_consolidada, (nome_usuario,))
            itens_consolidados = cur.fetchall()

            # Agora, calculamos as métricas em Python com os dados já agrupados
            pedidos_do_usuario = {}
            total_skus_usuario = 0

            for item in itens_consolidados:
                num_ped = item['numero_pedido']
                if num_ped not in pedidos_do_usuario:
                    # Inicializa o pedido com divergencia=False
                    pedidos_do_usuario[num_ped] = {'tem_divergencia': False}

                divergencia = float(
                    item['total_conferido']) - float(item['quantidade_pedida'])
                if divergencia != 0:
                    pedidos_do_usuario[num_ped]['tem_divergencia'] = True

                total_skus_usuario += float(item['quantidade_pedida'])

            pedidos_com_div = sum(
                1 for ped in pedidos_do_usuario.values() if ped['tem_divergencia'])
            pedidos_sem_div = len(pedidos_do_usuario) - pedidos_com_div

            usuario['total_pedidos'] = len(pedidos_do_usuario)
            usuario['total_skus'] = total_skus_usuario
            usuario['pedidos_com_divergencia'] = pedidos_com_div
            usuario['pedidos_sem_divergencia'] = pedidos_sem_div

            # Lógica de Remuneração sobre os dados consolidados
            if tipo_usuario == 'Separador':
                usuario['credito'] = float(pedidos_sem_div) * 10.0
                usuario['debito'] = float(pedidos_com_div) * 10.0
                usuario['percentual_acertos'] = (
                    pedidos_sem_div / len(pedidos_do_usuario)) * 100 if len(pedidos_do_usuario) > 0 else 0
            else:  # Conferente
                # O crédito é a SOMA das divergências FINAIS de cada produto
                credito_total = sum(abs(float(item['total_conferido']) - float(
                    item['quantidade_pedida'])) for item in itens_consolidados)
                usuario['credito'] = credito_total * 1.00
                usuario['debito'] = 0

                skus_ok = total_skus_usuario - credito_total
                usuario['percentual_acertos'] = (
                    skus_ok / total_skus_usuario) * 100 if total_skus_usuario > 0 else 0

            usuario['saldo'] = usuario.get(
                'credito', 0) - usuario.get('debito', 0)
            usuarios_processados.append(usuario)

        # 3. Calcular os totais gerais para os cards com uma consulta única e final
        if usuarios_processados:
            cur.execute("""
                SELECT
                    COUNT(DISTINCT numero_pedido) AS total_pedidos_geral,
                    COALESCE(SUM(CAST(quantidade_pedida AS SIGNED)), 0) AS total_skus_geral
                FROM conferencia WHERE status = 'CONFERIDO'
            """)
            globais = cur.fetchone()
            if globais:
                total_pedidos_geral = globais['total_pedidos_geral']
                total_skus_geral = globais['total_skus_geral']

            pedidos_com_divergencia_geral = sum(
                u.get('pedidos_com_divergencia', 0) for u in usuarios_processados)
            pedidos_sem_divergencia_geral = sum(
                u.get('pedidos_sem_divergencia', 0) for u in usuarios_processados)
            total_a_pagar = sum(u.get('saldo', 0)
                                for u in usuarios_processados if u.get('saldo', 0) > 0)

    except Exception as e:
        print(f"Erro ao processar dados de Crédito e Débito: {str(e)}")
        erro = f"Erro ao processar dados: {e}"
    finally:
        if conn and conn.is_connected():
            conn.close()

    # Retorna todas as variáveis para o template
    return render_template('credito_debito.html',
                           usuarios=usuarios_processados,
                           total_pedidos=int(total_pedidos_geral),
                           total_skus=int(total_skus_geral),
                           pedidos_com_divergencia=int(
                               pedidos_com_divergencia_geral),
                           pedidos_sem_divergencia=int(
                               pedidos_sem_divergencia_geral),
                           total_a_pagar=total_a_pagar,
                           erro=erro)


@app.route('/atualizar_dados')
@login_required
def atualizar_dados():
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"error": "Database connection failed"}), 500

        cur = conn.cursor(dictionary=True)

        # Busca apenas os dados necessários para atualização
        query = '''
            SELECT 
                conferente as nome, 
                'Conferente' as tipo,
                COUNT(DISTINCT numero_pedido) as total_pedidos
            FROM conferencia
            WHERE conferente IS NOT NULL AND status != 'EM CONFERENCIA'
            GROUP BY conferente
            UNION
            SELECT 
                separador as nome,
                'Separador' as tipo,
                COUNT(DISTINCT numero_pedido) as total_pedidos
            FROM conferencia
            WHERE separador IS NOT NULL AND status != 'EM CONFERENCIA'
            GROUP BY separador
        '''
        cur.execute(query)
        usuarios = cur.fetchall()

        cur.close()
        conn.close()

        return jsonify({"usuarios": usuarios})
    except Exception as e:
        print(f"Erro ao atualizar dados: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/separador')
@login_required
def separador():
    print("Acessando rota /separador")
    try:
        conn = get_db_connection()
        if conn is None:
            print(
                "Falha na conexão com o banco de dados - Verifique as credenciais e o servidor MySQL")
            return render_template('separador.html', pedidos=[])

        # Verificar a estrutura da tabela para depuração
        cur = conn.cursor()
        cur.execute("DESCRIBE conferencia")
        columns = [row[0] for row in cur.fetchall()]
        print("Colunas da tabela conferencia:", columns)

        # Verificar se há dados na tabela
        cur.execute("SELECT COUNT(*) FROM conferencia")
        row_count = cur.fetchone()[0]
        print("Número de registros na tabela conferencia:", row_count)

        cur = conn.cursor(dictionary=True)
        query = '''
            
            SELECT DISTINCT numero_pedido, status, separador, lojas_tag
FROM conferencia
ORDER BY numero_pedido ASC
        '''
        print("Executando consulta SQL:", query)
        cur.execute(query)
        pedidos = cur.fetchall()
        print("Número de registros retornados:", len(pedidos))
        print("Dados retornados:", pedidos)
        cur.close()
        conn.close()
        return render_template('separador.html', pedidos=pedidos)
    except Exception as e:
        print(f"Erro ao buscar dados: {e}")
        return render_template('separador.html', pedidos=[])


@app.route('/detalhe_pedidos', methods=['GET'])
@login_required
def detalhe_pedidos():
    numero_pedido = request.args.get('numero_pedido')
    print(f"Acessando rota /detalhe_pedidos com numero_pedido={numero_pedido}")
    if not numero_pedido:
        print("Número do pedido não fornecido")
        return render_template('detalhe_pedidos.html', numero_pedido=None, itens=[])

    try:
        conn = get_db_connection()
        if conn is None:
            print("Falha na conexão com o banco de dados")
            return render_template('detalhe_pedidos.html', numero_pedido=numero_pedido, itens=[])

        cur = conn.cursor(dictionary=True)
        query = '''
            SELECT id, numero_pedido, codigo, descricao, quantidade_pedida, quantidade_conferida, divergencia
            FROM conferencia
            WHERE numero_pedido = %s
        '''
        print("Executando consulta SQL:", query,
              "com número do pedido:", numero_pedido)
        cur.execute(query, (numero_pedido,))
        itens = cur.fetchall()
        print("Itens retornados:", itens)
        cur.close()
        conn.close()
        return render_template('detalhe_pedidos.html', numero_pedido=numero_pedido, itens=itens)
    except Exception as e:
        print(f"Erro ao buscar itens: {e}")
        return render_template('detalhe_pedidos.html', numero_pedido=numero_pedido, itens=[])


# @app.route('/separador')
# def separador():
#     return render_template('separador.html')

@app.route('/suporte_logistico')
def suporte_logistico():
    return render_template('suporte_logistico.html')

# Rota para a página de conferência


@app.route('/conferencia')
@login_required
def conferencia_page():
    print("Acessando rota /conferencia para visualização geral")
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return render_template('Conferencia.html', dados=[], erro="Falha na conexão com o banco de dados")

        cur = conn.cursor(dictionary=True)

        # --- NOVA QUERY SQL CONSOLIDADA ---
        # Esta query agrupa os itens por produto, soma as quantidades e calcula a divergência final
        query = """
            SELECT
                ANY_VALUE(id) as id,  -- Pega um ID qualquer apenas para referência da linha
                numero_pedido,
                codigo,
                descricao,
                quantidade_pedida,
                SUM(quantidade_conferida) AS quantidade_conferida,
                (SUM(quantidade_conferida) - quantidade_pedida) AS divergencia,
                ABS(SUM(quantidade_conferida) - quantidade_pedida) * 1.00 AS credito, -- Exemplo de cálculo de crédito
                GROUP_CONCAT(DISTINCT caixa ORDER BY caixa SEPARATOR ', ') AS caixa,
                status,
                conferente,
                separador
            FROM
                conferencia
            GROUP BY
                numero_pedido, codigo, descricao, quantidade_pedida, status, conferente, separador
            ORDER BY
                numero_pedido ASC, codigo ASC;
        """

        print("Executando consulta SQL consolidada:", query)
        cur.execute(query)
        dados = cur.fetchall()
        print(f"Dados consolidados retornados: {len(dados)} registros")

        return render_template('Conferencia.html', dados=dados)

    except Exception as e:
        print(f"Erro ao buscar dados de conferência: {e}")
        return render_template('Conferencia.html', dados=[], erro=f"Erro ao buscar dados: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()


@app.route('/conferencia/buscar', methods=['POST'])
@login_required
def buscar_conferencia():
    numero_pedido = request.form.get('numero_pedido')
    print(f"Buscando por número de pedido consolidado: {numero_pedido}")
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return render_template('Conferencia.html', dados=[], erro="Falha na conexão com o banco de dados")

        cur = conn.cursor(dictionary=True)

        # --- NOVA QUERY SQL CONSOLIDADA COM FILTRO ---
        query = """
            SELECT
                ANY_VALUE(id) as id,
                numero_pedido,
                codigo,
                descricao,
                quantidade_pedida,
                SUM(quantidade_conferida) AS quantidade_conferida,
                (SUM(quantidade_conferida) - quantidade_pedida) AS divergencia,
                ABS(SUM(quantidade_conferida) - quantidade_pedida) * 1.00 AS credito,
                GROUP_CONCAT(DISTINCT caixa ORDER BY caixa SEPARATOR ', ') AS caixa,
                status,
                conferente,
                separador
            FROM
                conferencia
            WHERE 
                numero_pedido = %s  -- Filtro por número do pedido
            GROUP BY
                numero_pedido, codigo, descricao, quantidade_pedida, status, conferente, separador
            ORDER BY
                codigo ASC;
        """
        cur.execute(query, (numero_pedido,))
        dados = cur.fetchall()
        print(f"Resultados da busca consolidada: {dados}")

        return render_template('Conferencia.html', dados=dados)
    except Exception as e:
        print(f"Erro ao buscar dados de conferência: {e}")
        return render_template('Conferencia.html', dados=[], erro=f"Erro ao buscar dados: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()



@app.route('/produto/<codigo>', methods=['GET'])
@login_required
def get_produto(codigo):
    print(f"Recebendo requisição GET para /produto/{codigo}")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        print(f"Buscando produto com código: {codigo}")

        like_pattern = f"%{codigo}%"

      
        query = """
            SELECT 
                codigo, descricao, saldo, barras, 
                localizacao1, localizacao2, grupo, 
                nome_fantasia, nu_fornecedor 
            FROM produtos 
            WHERE 
                codigo = %s OR 
                barras = %s OR
                multi_barras LIKE %s
        """
        
        # <<< MUDANÇA 3: Adicionar o novo padrão ao conjunto de parâmetros >>>
        cur.execute(query, (codigo, codigo, like_pattern))
        
        produto = cur.fetchone()
        
        # Esta lógica original é mantida: só executa se a busca nos 3 campos falhar.
        if not produto:
            print(
                f"Produto não encontrado em 'codigo', 'barras' ou 'multi_barras'. Inserindo novo produto com código: {codigo}")
            # ATENÇÃO: Esta lógica insere um produto de exemplo se nenhum for achado.
            cur.execute(
                'INSERT INTO produtos (codigo, barras, descricao, saldo, localizacao1, localizacao2, grupo, nome_fantasia, nu_fornecedor) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                (codigo, codigo, 'Produto Exemplo - Descrição Padrão', 10, 'N/A', 'N/A', '1', 'N/A', None) # Ajustei barras e nu_fornecedor
            )
            conn.commit()
            cur.execute(
                'SELECT codigo, descricao, saldo, barras, localizacao1, localizacao2, grupo, nome_fantasia, nu_fornecedor FROM produtos WHERE codigo = %s',
                (codigo,)
            )
            produto = cur.fetchone()
            
        print(f"Produto encontrado: {produto}")
        return jsonify(produto)

    except Exception as e:
        print(f"Erro ao buscar produto: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        # É uma boa prática garantir que a conexão seja fechada no bloco finally
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route('/ajustar-estoque-automatico', methods=['POST'])
@login_required
def ajustar_estoque_automatico():
    print("Recebendo requisição POST para /ajustar-estoque-automatico")

    if 'user' not in session:
        return jsonify({'error': 'Usuário não está logado'}), 401

    user = session['user']
    if 'matricula' not in user or 'nome' not in user:
        return jsonify({'error': 'Dados do usuário na sessão estão incompletos'}), 500

    matricula = user['matricula']
    nome_usuario = user['nome']

    data = request.get_json()
    numero_ajuste = data.get('numero_ajuste')
    codigo_produto = data.get('codigo_produto')
    quantidade = data.get('quantidade')
    ajuste_menos = data.get('ajuste_menos', False)

    if not codigo_produto:
        return jsonify({'error': 'Código do produto é obrigatório'}), 400

    if not numero_ajuste:
        return jsonify({'error': 'Número do ajuste é obrigatório'}), 400

    try:
        numero_ajuste = int(numero_ajuste)
    except (ValueError, TypeError):
        return jsonify({'error': 'Número do ajuste deve ser um número inteiro'}), 400

    try:
        quantidade = int(quantidade) if quantidade is not None else 0
    except (ValueError, TypeError):
        quantidade = 0

    if quantidade == 0:
        quantidade = -1 if ajuste_menos else 1

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Verificar a última atualização do ajuste pendente (para evitar duplicatas)
        cur.execute('''
            SELECT data FROM ajustes 
            WHERE numero_ajuste = %s AND codigo_produto = %s AND TRIM(UPPER(status)) = %s LIMIT 1
        ''', (numero_ajuste, codigo_produto, 'PENDENTE'))
        ajuste = cur.fetchone()

        if ajuste:
            ultima_atualizacao = ajuste[0]
            from datetime import datetime, timedelta
            if ultima_atualizacao and (datetime.now() - ultima_atualizacao) < timedelta(milliseconds=500):
                print(
                    f"Ajuste ignorado - atualização recente detectada para numero_ajuste={numero_ajuste}, codigo_produto={codigo_produto}")
                cur.close()
                conn.close()
                return jsonify({'message': 'Ajuste ignorado - atualização recente detectada'}), 200

        # Buscar o produto
        cur.execute('''
            SELECT saldo, descricao FROM produtos 
            WHERE codigo = %s OR barras = %s LIMIT 1
        ''', (codigo_produto, codigo_produto))
        produto = cur.fetchone()

        if not produto:
            cur.close()
            conn.close()
            return jsonify({'error': 'Produto não encontrado'}), 404

        saldo = produto[0]
        descricao = produto[1]

        novo_saldo = saldo + quantidade

        # Atualizar o saldo do produto
        cur.execute('''
            UPDATE produtos SET saldo = %s 
            WHERE codigo = %s OR barras = %s
        ''', (novo_saldo, codigo_produto, codigo_produto))

        # Verificar se o ajuste pendente existe
        cur.execute('''
            SELECT quantidade FROM ajustes 
            WHERE numero_ajuste = %s AND codigo_produto = %s AND TRIM(UPPER(status)) = %s LIMIT 1
        ''', (numero_ajuste, codigo_produto, 'PENDENTE'))
        ajuste = cur.fetchone()

        if not ajuste:
            cur.close()
            conn.close()
            return jsonify({'error': 'Ajuste pendente não encontrado para o número e código do produto fornecidos'}), 404

        nova_quantidade = ajuste[0] + quantidade
        cur.execute('''
            UPDATE ajustes 
            SET quantidade = %s, matricula = %s, nome_usuario = %s, data = NOW()
            WHERE numero_ajuste = %s AND codigo_produto = %s AND TRIM(UPPER(status)) = %s
        ''', (nova_quantidade, matricula, nome_usuario, numero_ajuste, codigo_produto, 'PENDENTE'))

        conn.commit()
        cur.close()
        conn.close()
        print(
            f"Ajuste atualizado com sucesso: numero_ajuste={numero_ajuste}, codigo_produto={codigo_produto}, nova_quantidade={nova_quantidade}")
        return jsonify({
            'message': 'Ajuste pendente atualizado com sucesso',
            'saldo': novo_saldo,
            'codigo_produto': codigo_produto,
            'descricao': descricao,
            'quantidade': nova_quantidade,
            'numero_ajuste': numero_ajuste
        }), 200
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        print(f"Erro ao ajustar estoque automaticamente: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/ajustar-estoque', methods=['POST'])
@login_required
def ajustar_estoque():
    try:
        data = request.get_json()
        ajustes = data.get('ajustes')

        if not ajustes:
            return jsonify({'error': 'Nenhum ajuste fornecido'}), 400

        if 'matricula' not in session['user'] or 'nome' not in session['user']:
            return jsonify({'error': 'Dados do usuário na sessão estão incompletos'}), 500

        matricula = session['user']['matricula']
        nome_usuario = session['user']['nome']

        conn = get_db_connection()
        cur = conn.cursor()
        resultados = []

        for ajuste in ajustes:
            numero_ajuste = ajuste.get('numero_ajuste')
            codigo = ajuste.get('codigo')
            quantidade = ajuste.get('quantidade')

            if (numero_ajuste is None or str(numero_ajuste).strip() == '' or
                codigo is None or str(codigo).strip() == '' or
                    quantidade is None):
                return jsonify({'error': 'Número do ajuste, código e quantidade são obrigatórios'}), 400

            try:
                quantidade = int(quantidade)
            except (ValueError, TypeError):
                return jsonify({'error': 'Quantidade deve ser um número inteiro'}), 400

            cur.execute(
                "SELECT saldo FROM produtos WHERE codigo = %s", (codigo,))
            produto = cur.fetchone()
            if not produto:
                return jsonify({'error': f'Produto com código {codigo} não encontrado'}), 404

            novo_saldo = produto[0] + quantidade
            cur.execute(
                "UPDATE produtos SET saldo = %s WHERE codigo = %s", (novo_saldo, codigo))
            cur.execute("""
                INSERT INTO ajustes (numero_ajuste, produto_codigo, descricao, ajuste, data_hora, matricula, nome_usuario)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (numero_ajuste, codigo, ajuste.get('descricao'), quantidade, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), matricula, nome_usuario))
            # cur.execute(
            #     "DELETE FROM ajustes_pendentes WHERE numero_ajuste = %s AND codigo_produto = %s", (numero_ajuste, codigo))
            # resultados.append({'codigo': codigo, 'saldo': novo_saldo})

        conn.commit()
        return jsonify({'success': True, 'numero_ajuste': numero_ajuste, 'resultados': resultados})
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Erro ao ajustar estoque: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

# :ok


@app.route('/adicionar-ajuste-pendente', methods=['POST'])
@login_required
def adicionar_ajuste_pendente():
    try:
        data = request.get_json()
        print("Dados recebidos:", data)  # Log para depuração

        numero_ajuste = data.get('numero_ajuste')
        codigo = data.get('codigo')
        descricao = data.get('descricao')
        quantidade = data.get('quantidade')

        if (numero_ajuste is None or str(numero_ajuste).strip() == '' or
            codigo is None or str(codigo).strip() == '' or
                quantidade is None):
            return jsonify({'error': 'Número do ajuste, código e quantidade são obrigatórios'}), 400

        try:
            numero_ajuste = int(numero_ajuste)
            quantidade = int(quantidade)
        except (ValueError, TypeError):
            return jsonify({'error': 'Número do ajuste e quantidade devem ser números inteiros'}), 400

        if quantidade == 0:
            return jsonify({'error': 'Quantidade deve ser diferente de zero'}), 400

        if 'matricula' not in session['user'] or 'nome' not in session['user']:
            return jsonify({'error': 'Dados do usuário na sessão estão incompletos'}), 500

        matricula = session['user']['matricula']
        nome_usuario = session['user']['nome']
        data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        # Verifica se já existe um ajuste pendente com o mesmo numero_ajuste e codigo_produto
        cur.execute("""
            SELECT id, quantidade FROM ajustes 
            WHERE numero_ajuste = %s AND codigo_produto = %s AND status = 'PENDENTE'
        """, (numero_ajuste, codigo))
        existing_ajuste = cur.fetchone()
        print("Ajuste existente:", existing_ajuste)

        if existing_ajuste:
            # Se existe, atualiza a quantidade somando
            nova_quantidade = existing_ajuste['quantidade'] + quantidade
            cur.execute("""
                UPDATE ajustes 
                SET quantidade = %s, data = %s, matricula = %s, nome_usuario = %s
                WHERE id = %s
            """, (nova_quantidade, data_atual, matricula, nome_usuario, existing_ajuste['id']))
            message = f"Quantidade atualizada! Nova quantidade: {nova_quantidade}"
        else:
            # Se não existe, insere um novo ajuste
            cur.execute("""
                INSERT INTO ajustes (numero_ajuste, codigo_produto, descricao, quantidade, matricula, nome_usuario, data, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDENTE')
            """, (numero_ajuste, codigo, descricao, quantidade, matricula, nome_usuario, data_atual))
            message = f"Ajuste criado com sucesso! Quantidade: {quantidade}"

        conn.commit()
        print("Ajuste gravado com sucesso")
        return jsonify({'success': True, 'message': message})

    except Exception as e:
        if conn:
            conn.rollback()
        app.logger.error(f"Erro ao adicionar ajuste pendente: {str(e)}")
        return jsonify({'error': str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

            # Rota para a página de monitoramento de fornecedores


@app.route('/monitoramento_fornecedores')
@login_required
def monitoramento_fornecedores():
    print("Acessando rota /monitoramento_fornecedores")
    return render_template('monitoramento_fornecedores.html')

# Rota para buscar dados do dashboard


@app.route('/dados_monitoramento_fornecedores', methods=['GET'])
@login_required
def dados_monitoramento_fornecedores():
    print("Acessando rota /dados_monitoramento_fornecedores")
    try:
        # Obtém o parâmetro de filtro
        filtro = request.args.get('filtro', '').strip()
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        # Condição de filtro para as consultas
        filtro_condition = ""
        filtro_param = None
        if filtro:
            if filtro.isdigit():  # Se for um número, busca por nu_fornecedor (número do fornecedor)
                filtro_condition = " WHERE p.nu_fornecedor = %s"
                filtro_param = filtro  # Mantém como string para compatibilidade com nu_fornecedor
            else:  # Se for texto, busca por nome_fantasia (nome do fornecedor)
                filtro_condition = " WHERE p.nome_fantasia COLLATE utf8mb4_0900_ai_ci LIKE %s COLLATE utf8mb4_0900_ai_ci"
                filtro_param = f"%{filtro}%"
            print(f"Filtro aplicado: {filtro_param}")  # Log para depuração

        # 1. Estoque total por fornecedor
        query_estoque = f'''
            SELECT p.nu_fornecedor AS fornecedor, SUM(p.saldo) as estoque_total
            FROM produtos p
            {filtro_condition}
            GROUP BY p.nu_fornecedor
            HAVING estoque_total > 0
            ORDER BY estoque_total DESC
        '''
        if filtro:
            cur.execute(query_estoque, (filtro_param,))
        else:
            cur.execute(query_estoque)
        estoque_fornecedores = cur.fetchall()
        # Log dos resultados
        print(f"Resultados estoque: {estoque_fornecedores}")

        # 2. Item que mais sai (baseado na tabela conferencia, considerando quantidade_pedida)
        query_item_mais_sai = f'''
            SELECT p.codigo, p.descricao, p.nu_fornecedor, SUM(c.quantidade_pedida) as total_saida
            FROM conferencia c
            JOIN produtos p ON c.codigo COLLATE utf8mb4_0900_ai_ci = p.codigo COLLATE utf8mb4_0900_ai_ci
            {filtro_condition}
            GROUP BY p.codigo, p.descricao, p.nu_fornecedor
            ORDER BY total_saida DESC
            LIMIT 1
        '''
        if filtro:
            cur.execute(query_item_mais_sai, (filtro_param,))
        else:
            cur.execute(query_item_mais_sai)
        item_mais_sai = cur.fetchone()
        # Log dos resultados
        print(f"Resultado item mais sai: {item_mais_sai}")

        # 3. Itens com saldo baixo (saldo < 11)
        saldo_baixo_condition = " p.saldo < 11 AND p.saldo > 0"
        where_clause = f" WHERE {saldo_baixo_condition}" if not filtro else f"{filtro_condition} AND {saldo_baixo_condition}"
        query_itens_saldo_baixo = f'''
            SELECT p.codigo, p.descricao, p.nu_fornecedor, p.saldo
            FROM produtos p
            {where_clause}
            ORDER BY p.saldo ASC
        '''
        if filtro:
            cur.execute(query_itens_saldo_baixo, (filtro_param,))
        else:
            cur.execute(query_itens_saldo_baixo)
        itens_saldo_baixo = cur.fetchall()
        # Log dos resultados
        print(f"Resultados saldo baixo: {itens_saldo_baixo}")

        cur.close()
        conn.close()

        return jsonify({
            'estoque_fornecedores': estoque_fornecedores,
            'item_mais_sai': item_mais_sai,
            'itens_saldo_baixo': itens_saldo_baixo
        })
    except Exception as e:
        print(f"Erro ao buscar dados de monitoramento: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Nova rota para sugestões de autocompletar


@app.route('/sugestoes_fornecedores', methods=['GET'])
@login_required
def sugestoes_fornecedores():
    try:
        termo = request.args.get('termo', '').strip()
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        query = '''
            SELECT DISTINCT nu_fornecedor, nome_fantasia
            FROM produtos 
            WHERE nu_fornecedor LIKE %s OR nome_fantasia LIKE %s
            LIMIT 10
        '''
        cur.execute(query, (f"%{termo}%", f"%{termo}%"))
        sugestoes = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify([{'nu_fornecedor': s['nu_fornecedor'], 'nome_fantasia': s['nome_fantasia']} for s in sugestoes])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/ultimo-ajuste-usuario', methods=['GET'])
@login_required
def get_ultimo_ajuste_usuario():
    try:
        matricula = session['user']['matricula']
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        query = '''
            SELECT numero_ajuste
            FROM ajustes
            WHERE matricula = %s AND TRIM(UPPER(status)) = %s
            ORDER BY numero_ajuste DESC
            LIMIT 1
        '''
        cur.execute(query, (matricula, 'PENDENTE'))
        ajuste = cur.fetchone()

        cur.close()
        conn.close()

        if ajuste:
            return jsonify({'ultimo_ajuste': ajuste['numero_ajuste']})
        else:
            return jsonify({'ultimo_ajuste': None})
    except Exception as e:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        print(f"Erro ao buscar último ajuste: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/proximo-numero-ajuste', methods=['GET'])
@login_required
def proximo_numero_ajuste():
    print("Recebendo requisição GET para /proximo-numero-ajuste")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # Obtém o próximo numero_ajuste
        print("Executando query para obter o próximo número de ajuste...")
        cur.execute(
            'SELECT COALESCE(MAX(numero_ajuste), 0) + 1 as next_numero_ajuste FROM ajustes')
        result = cur.fetchone()
        print(f"Resultado da query: {result}")

        if not result or 'next_numero_ajuste' not in result:
            print("Erro: Não foi possível obter o próximo número de ajuste.")
            return jsonify({'error': 'Não foi possível obter o próximo número de ajuste', 'success': False}), 500

        numero_ajuste = result['next_numero_ajuste']
        print(f"Número de ajuste gerado: {numero_ajuste}")

        # Obtém dados do usuário da sessão
        matricula = session['user']['matricula']
        nome_usuario = session['user']['nome']
        data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insere um registro inicial na tabela ajustes
        cur.execute("""
            INSERT INTO ajustes (numero_ajuste, matricula, nome_usuario, data, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (numero_ajuste, matricula, nome_usuario, data_atual, 'PENDENTE'))
        conn.commit()

        print(
            f"Registro inicial do ajuste {numero_ajuste} inserido com sucesso para matrícula {matricula}")

        cur.close()
        conn.close()
        return jsonify({'numero_ajuste': numero_ajuste, 'success': True})
    except mysql.connector.Error as db_err:
        conn.rollback()
        cur.close()
        conn.close()
        print(
            f"Erro no banco de dados ao obter próximo número de ajuste: {db_err}")
        return jsonify({'error': f'Erro no banco de dados: {str(db_err)}', 'success': False}), 500
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        print(f"Erro ao obter próximo número de ajuste: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/liberar-ajustes', methods=['GET'])
@login_required
def liberar_ajustes_page():
    print("Acessando rota /liberar-ajustes")
    return render_template('liberar_ajustes.html')


@app.route('/cancelar-ajuste/<int:numero_ajuste>', methods=['POST'])
@login_required
def cancelar_ajuste(numero_ajuste):
    print(f"Recebendo requisição POST para /cancelar-ajuste/{numero_ajuste}")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Verificar se o ajuste existe e está pendente
        cur.execute('''
            SELECT status FROM ajustes
            WHERE numero_ajuste = %s AND TRIM(UPPER(status)) = %s
            LIMIT 1
        ''', (numero_ajuste, 'PENDENTE'))
        ajuste = cur.fetchone()

        if not ajuste:
            cur.close()
            conn.close()
            return jsonify({'error': 'Ajuste não encontrado ou não está pendente'}), 404

        # Atualizar o status para "Cancelado"
        cur.execute('''
            UPDATE ajustes
            SET status = %s
            WHERE numero_ajuste = %s
        ''', ('CANCELADO', numero_ajuste))
        conn.commit()

        cur.close()
        conn.close()
        return jsonify({'message': 'Ajuste cancelado com sucesso'}), 200
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        print(f"Erro ao cancelar ajuste: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/ajustes-pendentes', methods=['GET'])
@login_required
def get_ajustes_pendentes():
    print("Recebendo requisição GET para /ajustes-pendentes")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute('''
            SELECT numero_ajuste, MAX(data) AS data,
                   (SELECT matricula FROM ajustes a2 
                    WHERE a2.numero_ajuste = a1.numero_ajuste 
                    AND TRIM(UPPER(a2.status)) = %s 
                    LIMIT 1) AS matricula,
                   (SELECT nome_usuario FROM ajustes a2 
                    WHERE a2.numero_ajuste = a1.numero_ajuste 
                    AND TRIM(UPPER(a2.status)) = %s 
                    LIMIT 1) AS nome_usuario
            FROM ajustes a1
            WHERE TRIM(UPPER(status)) = %s
            GROUP BY numero_ajuste
            ORDER BY numero_ajuste DESC
        ''', ('PENDENTE', 'PENDENTE', 'PENDENTE'))
        ajustes = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify([{
            'numero_ajuste': item['numero_ajuste'],
            'data_hora': item['data'].strftime('%d/%m/%Y - %H:%M') if item['data'] else 'N/A',
            'matricula': item['matricula'],
            'nome_usuario': item['nome_usuario']
        } for item in ajustes])
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/ajustes-pendentes/<numero_ajuste>', methods=['GET'])
@login_required
def get_ajustes_pendentes_by_numero(numero_ajuste):
    print(f"Recebendo requisição GET para /ajustes-pendentes/{numero_ajuste}")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute('''
            SELECT numero_ajuste, codigo_produto AS codigo, descricao, quantidade, status
            FROM ajustes
            WHERE numero_ajuste = %s AND TRIM(UPPER(status)) = %s
        ''', (numero_ajuste, 'PENDENTE'))
        ajustes = cur.fetchall()

        print(
            f"Ajustes encontrados para numero_ajuste {numero_ajuste}: {ajustes}")
        cur.close()
        conn.close()
        return jsonify(ajustes)
    except Exception as e:
        cur.close()
        conn.close()
        print(f"Erro ao buscar ajustes pendentes: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/liberar-ajuste/<numero_ajuste>', methods=['POST'])
@login_required
def liberar_ajuste(numero_ajuste):
    print(f"Recebendo requisição POST para /liberar-ajuste/{numero_ajuste}")
    if 'user' not in session or 'nome' not in session['user']:
        print("Erro: Usuário não autenticado na sessão.")
        return jsonify({'error': 'Usuário não autenticado. Faça login novamente.'}), 401

    usuario_liberou = session['user']['nome']
    print(f"Usuário que está liberando: {usuario_liberou}")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*) FROM ajustes WHERE numero_ajuste = %s AND status = 'PENDENTE'", (numero_ajuste,))
        count = cur.fetchone()[0]
        if count == 0:
            print(f"Ajuste {numero_ajuste} não encontrado ou já liberado")
            return jsonify({'error': 'Ajuste não encontrado ou já liberado'}), 404

        cur.execute(
            "UPDATE ajustes SET status = 'LIBERADO', usuario_liberou = %s WHERE numero_ajuste = %s",
            (usuario_liberou, numero_ajuste)
        )
        conn.commit()
        print(f"Ajuste {numero_ajuste} liberado por {usuario_liberou}")
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        print(f"Erro ao liberar ajuste {numero_ajuste}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/historico', methods=['GET'])
@login_required
@login_required
def get_historico():
    print("Recebendo requisição GET para /historico")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        print("Buscando histórico de ajustes...")
        cur.execute('SELECT * FROM ajustes ORDER BY data DESC')
        historico = cur.fetchall()
        print(f"Histórico encontrado: {historico}")
        cur.close()
        conn.close()
        return jsonify([
            {
                'id': item['numero_ajuste'],
                'produto_codigo': item['codigo_produto'],
                'ajuste': item['quantidade'],
                'data_hora': item['data'].strftime('%d/%m/%Y - %H:%M'),
                'matricula': item['matricula'],
                'nome_usuario': item['nome_usuario'],
                'descricao': item['descricao']
            } for item in historico
        ])
    except Exception as e:
        cur.close()
        conn.close()
        print(f"Erro ao carregar histórico: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/ajustes_realizados', methods=['GET'])
@login_required
def ajustes_realizados():
    return render_template('ajustes_realizados.html')


@app.route('/ajustes-realizados-dados', methods=['GET'])
@login_required
def get_ajustes_realizados():
    print("Recebendo requisição GET para /ajustes-realizados-dados")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute('''
            SELECT numero_ajuste, MAX(data) AS data, matricula, nome_usuario, usuario_liberou
            FROM ajustes
            WHERE TRIM(UPPER(status)) = %s
            GROUP BY numero_ajuste, matricula, nome_usuario, usuario_liberou
            ORDER BY numero_ajuste DESC
        ''', ('LIBERADO',))
        ajustes = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify([{
            'numero_ajuste': ajuste['numero_ajuste'],
            'data_hora': ajuste['data'].strftime('%d/%m/%Y - %H:%M') if ajuste['data'] else 'N/A',
            'matricula': ajuste['matricula'],
            'nome_usuario': ajuste['nome_usuario'],
            'usuario_liberou': ajuste['usuario_liberou']
        } for ajuste in ajustes])
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/detalhes-ajuste/<numero_ajuste>', methods=['GET'])
@login_required
def get_detalhes_ajuste(numero_ajuste):
    print(f"Recebendo requisição GET para /detalhes-ajuste/{numero_ajuste}")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute('''
            SELECT a.*, p.custo
            FROM ajustes a
            LEFT JOIN produtos p ON a.codigo_produto = p.codigo
            WHERE a.numero_ajuste = %s
        ''', (numero_ajuste,))
        ajustes = cur.fetchall()
        print(f"Dados brutos do banco para ajuste {numero_ajuste}: {ajustes}")
        if not ajustes:
            return jsonify({'error': 'Ajuste não encontrado'}), 404

        ajustes_formatados = [{
            'numero_ajuste': ajuste['numero_ajuste'],
            'produto_codigo': ajuste['codigo_produto'],
            'descricao': ajuste['descricao'],
            'quantidade': ajuste['quantidade'],
            'custo': float(str(ajuste['custo']).replace(',', '.')) if ajuste['custo'] is not None else 0.0,
            'data_hora': ajuste['data'].strftime('%d/%m/%Y - %H:%M'),
            'matricula': ajuste['matricula'],
            'nome_usuario': ajuste['nome_usuario'],
            'usuario_liberou': ajuste['usuario_liberou'],
            'status': ajuste['status']
        } for ajuste in ajustes]
        print(
            f"Dados formatados para ajuste {numero_ajuste}: {ajustes_formatados}")

        cur.close()
        conn.close()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(ajustes_formatados)
        else:
            return render_template('detalhes_ajuste.html', numero_ajuste=numero_ajuste)
    except Exception as e:
        cur.close()
        conn.close()
        print(f"Erro ao buscar detalhes do ajuste {numero_ajuste}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/relatorio-dados', methods=['GET'])
@login_required
def get_relatorio_dados():
    print("Recebendo requisição GET para /relatorio-dados")
    print(f"Sessão atual: {session}")
    if 'user' not in session:
        print("Usuário não autenticado na rota /relatorio-dados.")
        return jsonify({'error': 'Usuário não autenticado. Faça login novamente.'}), 401

    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    matricula = request.args.get('matricula')
    numero_ajuste = request.args.get('numero_ajuste')

    print(
        f"Parâmetros recebidos - data_inicio: {data_inicio}, data_fim: {data_fim}, matricula: {matricula}, numero_ajuste: {numero_ajuste}")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        query = '''
            SELECT a.*, p.custo AS custo
            FROM ajustes a
            LEFT JOIN produtos p ON a.codigo_produto = p.codigo
            WHERE 1=1
        '''
        params = []

        if data_inicio:
            query += ' AND data >= %s'
            # Ajustado para YYYY-MM-DD
            params.append(datetime.strptime(data_inicio, '%Y-%m-%d'))
        if data_fim:
            query += ' AND data <= %s'
            data_fim_dt = datetime.strptime(
                # Final do dia: 23:59:59
                data_fim, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            params.append(data_fim_dt)
        if matricula:
            query += ' AND matricula = %s'
            params.append(matricula)
        if numero_ajuste:
            query += ' AND numero_ajuste = %s'
            params.append(numero_ajuste)

        query += ' ORDER BY numero_ajuste, data DESC'
        print(f"Executando consulta: {query} com parâmetros: {params}")
        cur.execute(query, params)
        ajustes = cur.fetchall()
        print(f"Ajustes encontrados: {ajustes}")

        cur.close()
        conn.close()
        return jsonify([{
            'numero_ajuste': item['numero_ajuste'],
            'produto_codigo': item['codigo_produto'],
            'descricao': item['descricao'],
            'quantidade': item['quantidade'],
            'custo': float(str(item['custo']).replace(',', '.')) if item['custo'] is not None else 0.0,
            'data_hora': item['data'].strftime('%d/%m/%Y - %H:%M'),
            'matricula': item['matricula'],
            'nome_usuario': item['nome_usuario']
        } for item in ajustes])
    except Exception as e:
        cur.close()
        conn.close()
        print(f"Erro ao carregar dados do relatório: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/exportar-relatorio-excel', methods=['GET'])
@login_required
# @login_required
def exportar_relatorio_excel():
    print("Recebendo requisição GET para /exportar-relatorio-excel")
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    matricula = request.args.get('matricula')
    numero_ajuste = request.args.get('numero_ajuste')

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        query = '''
            SELECT a.*, p.custo AS custo
            FROM ajustes a
            LEFT JOIN produtos p ON a.codigo_produto = p.codigo
            WHERE 1=1
        '''
        params = []

        if data_inicio:
            query += ' AND data >= %s'
            params.append(data_inicio)
        if data_fim:
            query += ' AND data <= %s'
            params.append(data_fim)
        if matricula:
            query += ' AND matricula = %s'
            params.append(matricula)
        if numero_ajuste:
            query += ' AND numero_ajuste = %s'
            params.append(numero_ajuste)

        query += ' ORDER BY numero_ajuste, data DESC'
        print(f"Executando consulta: {query} com parâmetros: {params}")
        cur.execute(query, params)
        ajustes = cur.fetchall()
        print(f"Ajustes encontrados: {ajustes}")

        data = [{
            'Número do Ajuste': item['numero_ajuste'],
            'Código do Produto': item['codigo_produto'],
            'Descrição': item['descricao'],
            # Trata None como 0
            'Quantidade': item['quantidade'] if item['quantidade'] is not None else 0,
            'Custo Unitário (R$)': float(str(item['custo']).replace(',', '.')) if item['custo'] is not None else 0.0,
            'Data/Hora': item['data'].strftime('%d/%m/%Y - %H:%M'),
            'Matrícula': item['matricula'],
            'Nome do Usuário': item['nome_usuario']
        } for item in ajustes]

        df = pd.DataFrame(data)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Relatório de Ajustes')
        output.seek(0)

        cur.close()
        conn.close()
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'relatorio_ajustes_{datetime.now().strftime("%Y%m%d")}.xlsx'
        )
    except Exception as e:
        cur.close()
        conn.close()
        print(f"Erro ao exportar relatório para Excel: {e}")
        return jsonify({'error': str(e)}), 500

# Módulo CV-Análise


@app.route('/cv_analise')
@login_required
def cv_analise():
    print("Acessando rota /cv_analise")
    return render_template('cv_analise.html')


@app.route('/buscar_curriculos', methods=['GET'])
@login_required
def buscar_curriculos():
    print("Recebendo requisição GET para /buscar_curriculos")
    nome = request.args.get('nome', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT id, nome FROM curriculos WHERE nome LIKE %s LIMIT 10"
    cursor.execute(query, ('%' + nome + '%',))
    curriculos = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(curriculos)


@app.route('/curriculo_detalhes/<candidato_id>', methods=['GET'])
@login_required
def curriculo_detalhes(candidato_id):
    print(
        f"[DEBUG] Recebendo requisição GET para /curriculo_detalhes/{candidato_id}")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM curriculos WHERE id = %s",
                       (candidato_id,))
        curriculo = cursor.fetchone()
        if not curriculo:
            cursor.close()
            conn.close()
            print(f"[DEBUG] Currículo ID {candidato_id} não encontrado")
            return "Currículo não encontrado", 404

        cursor.close()
        conn.close()
        print(f"[DEBUG] Currículo encontrado: {curriculo}")
        print(f"[DEBUG] Renderizando template curriculo_detalhes.html")
        return render_template('curriculo_detalhes.html', curriculo=curriculo)
    except Exception as e:
        cursor.close()
        conn.close()
        print(
            f"[DEBUG] Erro ao buscar detalhes do currículo {candidato_id}: {str(e)}")
        return f"Erro ao buscar currículo: {str(e)}", 500


@app.route('/vagas', methods=['GET'])
@login_required
def get_vagas():
    try:
        print("Acessando rota /vagas")  # Log para depuração
        conn = get_db_connection()
        print("Conexão com o banco de dados estabelecida")  # Log para depuração
        cursor = conn.cursor()
        cursor.execute("SELECT id, titulo, requisitos FROM vagas")
        vagas = cursor.fetchall()
        print(f"Vagas encontradas: {vagas}")  # Log para depuração
        cursor.close()
        conn.close()

        vagas_list = [{'id': vaga[0], 'titulo': vaga[1],
                       'requisitos': vaga[2]} for vaga in vagas]
        return jsonify(vagas_list)
    except Exception as e:
        print(f"Erro ao carregar vagas: {str(e)}")  # Log para depuração
        return jsonify({'error': f'Erro ao carregar vagas: {str(e)}'}), 500


@app.route('/buscar-candidatos', methods=['GET'])
@login_required
def buscar_candidatos():
    nome = request.args.get('nome', '').strip()
    vaga_id = request.args.get('vaga_id', '')

    if not vaga_id:
        return jsonify({'error': 'ID da vaga é obrigatório'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        query = "SELECT * FROM curriculos WHERE vaga_id = %s AND (status IS NULL OR status != 'aprovado')"
        params = [vaga_id]
        if nome:
            query += " AND nome LIKE %s"
            params.append(f"%{nome}%")
        cursor.execute(query, params)
        curriculos = cursor.fetchall()
        cursor.close()
        conn.close()

        print(f"Candidatos encontrados: {curriculos}")
        return jsonify(curriculos)
    except Exception as e:
        cursor.close()
        conn.close()
        print(f"Erro ao buscar candidatos: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/aprovar-candidatos', methods=['POST'])
@login_required
def aprovar_candidatos():
    print("[DEBUG] Recebendo requisição POST para /aprovar-candidatos")
    data = request.get_json()
    candidatos = data.get('candidatos', [])

    if not candidatos:
        return jsonify({'error': 'Nenhum candidato selecionado'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for candidato_id in candidatos:
            cursor.execute(
                "UPDATE curriculos SET status = 'Aprovado', etapa = 1 WHERE id = %s", (candidato_id,))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[DEBUG] Candidatos aprovados: {candidatos}")
        return jsonify({'success': True})
    except Exception as e:
        cursor.close()
        conn.close()
        print(f"[DEBUG] Erro ao aprovar candidatos: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/reprovar_candidato/<int:candidato_id>', methods=['POST'])
@login_required
def reprovar_candidato(candidato_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verificar se o candidato existe
        cursor.execute(
            "SELECT id FROM curriculos WHERE id = %s", (candidato_id,))
        candidato = cursor.fetchone()
        if not candidato:
            return jsonify({'error': 'Candidato não encontrado'}), 404

        # Atualizar o status para "reprovado"
        cursor.execute(
            "UPDATE curriculos SET status = 'Reprovado' WHERE id = %s", (candidato_id,))
        conn.commit()

        cursor.close()
        conn.close()
        return jsonify({'message': 'Candidato reprovado com sucesso'})
    except Exception as e:
        cursor.close()
        conn.close()
        print(f"[DEBUG] Erro ao reprovar candidato: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/avancar_etapa/<int:candidato_id>', methods=['POST'])
@login_required
def avancar_etapa(candidato_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verificar se o candidato existe e obter a etapa atual
        cursor.execute(
            "SELECT etapa FROM curriculos WHERE id = %s", (candidato_id,))
        candidato = cursor.fetchone()
        if not candidato:
            return jsonify({'error': 'Candidato não encontrado'}), 404

        # Incrementar a etapa (máximo 6)
        etapa_atual = candidato[0]
        nova_etapa = etapa_atual + 1 if etapa_atual < 6 else 6

        # Atualizar a etapa no banco de dados
        cursor.execute(
            "UPDATE curriculos SET etapa = %s WHERE id = %s", (nova_etapa, candidato_id))
        conn.commit()

        cursor.close()
        conn.close()
        return jsonify({'message': 'Etapa avançada com sucesso'})
    except Exception as e:
        cursor.close()
        conn.close()
        print(f"[DEBUG] Erro ao avançar etapa: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/gerar_questionario/<int:candidato_id>')
@login_required
def gerar_questionario(candidato_id):
    return render_template('gerar_questionario.html', candidato_id=candidato_id)


@app.route('/get_candidate_name/<int:candidato_id>')
@login_required
def get_candidate_name(candidato_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT nome FROM curriculos WHERE id = %s", (candidato_id,))
        candidato = cursor.fetchone()
        if not candidato:
            return jsonify({'error': 'Candidato não encontrado'}), 404
        return jsonify({'nome': candidato[0]})
    finally:
        cursor.close()
        conn.close()


@app.route('/gerar_perguntas/<int:candidato_id>', methods=['GET'])
@login_required
def gerar_perguntas(candidato_id):
    print(
        f"[DEBUG] Iniciando geração de perguntas para candidato_id: {candidato_id}")
    if 'user' not in session:
        print(
            f"[DEBUG] Usuário não autenticado ao acessar /gerar_perguntas/{candidato_id}")
        return jsonify({'error': 'Usuário não autenticado'}), 401

    # Perguntas padrão (fallback) ajustadas para diferentes níveis de senioridade
    fallback_perguntas_junior = [
        {"pergunta": "Qual é a sua experiência na área da vaga?", "alternativas": [
            "a) Nenhuma", "b) 1-2 anos", "c) Mais de 2 anos"], "correta": "b"},
        {"pergunta": "Você tem conhecimento nos requisitos da vaga?", "alternativas": [
            "a) Sim", "b) Não", "c) Parcialmente"], "correta": "a"},
        {"pergunta": "O que é uma variável em programação?", "alternativas": [
            "a) Um valor fixo", "b) Um espaço para armazenar dados", "c) Um tipo de função"], "correta": "b"},
        {"pergunta": "Qual é a função do print() em Python?", "alternativas": [
            "a) Ler um arquivo", "b) Exibir uma mensagem", "c) Criar uma variável"], "correta": "b"},
        {"pergunta": "O que significa um erro de sintaxe?", "alternativas": [
            "a) Erro de lógica", "b) Erro na escrita do código", "c) Erro de execução"], "correta": "b"},
        {"pergunta": "Qual é o operador para igualdade em Python?",
            "alternativas": ["a) =", "b) ==", "c) :="], "correta": "b"},
        {"pergunta": "O que é uma lista em Python?", "alternativas": [
            "a) Um tipo de loop", "b) Uma coleção ordenada", "c) Uma função"], "correta": "b"},
        {"pergunta": "Como você inicia um loop for em Python?", "alternativas": [
            "a) for i in range()", "b) while i in range()", "c) loop i in range()"], "correta": "a"},
        {"pergunta": "Qual é o propósito de um if em programação?", "alternativas": [
            "a) Repetir um código", "b) Tomar decisões", "c) Definir uma função"], "correta": "b"},
        {"pergunta": "O que faz o método append() em uma lista?", "alternativas": [
            "a) Remove um item", "b) Adiciona um item", "c) Altera um item"], "correta": "b"}
    ]

    fallback_perguntas_pleno = [
        {"pergunta": "Como você gerencia dependências em Python?", "alternativas": [
            "a) Usando pip", "b) Editando o código", "c) Usando print()"], "correta": "a"},
        {"pergunta": "O que é uma rota em Flask?", "alternativas": [
            "a) Um banco de dados", "b) Um endpoint URL", "c) Um tipo de variável"], "correta": "b"},
        {"pergunta": "Qual é a diferença entre list e tuple?", "alternativas": [
            "a) List é imutável", "b) Tuple é mutável", "c) List é mutável, tuple é imutável"], "correta": "c"},
        {"pergunta": "Como você lida com exceções em Python?", "alternativas": [
            "a) Usando if", "b) Usando try/except", "c) Usando for"], "correta": "b"},
        {"pergunta": "O que é o método GET em Flask?", "alternativas": [
            "a) Salva dados", "b) Busca dados", "c) Deleta dados"], "correta": "b"},
        {"pergunta": "O que é um decorador em Python?", "alternativas": [
            "a) Uma função que modifica outra", "b) Um loop", "c) Um tipo de variável"], "correta": "a"},
        {"pergunta": "Como você cria uma API REST com Flask?", "alternativas": [
            "a) Definindo rotas", "b) Usando loops", "c) Criando variáveis"], "correta": "a"},
        {"pergunta": "O que é o Flask Blueprint?", "alternativas": [
            "a) Um template", "b) Um módulo para organizar rotas", "c) Um banco de dados"], "correta": "b"},
        {"pergunta": "Qual é a função do jsonify no Flask?", "alternativas": [
            "a) Converte para JSON", "b) Cria uma página HTML", "c) Salva no banco"], "correta": "a"},
        {"pergunta": "O que é um ORM em Python?", "alternativas": [
            "a) Um gerenciador de rotas", "b) Um mapeador objeto-relacional", "c) Um tipo de loop"], "correta": "b"}
    ]

    fallback_perguntas_senior = [
        {"pergunta": "Como você otimiza o desempenho de uma app Flask?", "alternativas": [
            "a) Usando loops", "b) Cache e async", "c) Aumentando variáveis"], "correta": "b"},
        {"pergunta": "O que é uma arquitetura de microsserviços?", "alternativas": [
            "a) Um único servidor", "b) Serviços independentes", "c) Um banco de dados"], "correta": "b"},
        {"pergunta": "Como você implementa autenticação em Flask?", "alternativas": [
            "a) Usando JWT", "b) Usando print()", "c) Usando loops"], "correta": "a"},
        {"pergunta": "O que é o GIL em Python?", "alternativas": [
            "a) Um gerenciador de rotas", "b) Um lock global", "c) Um tipo de lista"], "correta": "b"},
        {"pergunta": "Como você lida com concorrência em Flask?", "alternativas": [
            "a) Usando Gunicorn", "b) Usando if", "c) Usando variáveis"], "correta": "a"},
        {"pergunta": "O que é o conceito de SOLID em programação?", "alternativas": [
            "a) Um tipo de loop", "b) Princípios de design", "c) Um banco de dados"], "correta": "b"},
        {"pergunta": "Como você testa uma API Flask?", "alternativas": [
            "a) Usando unittest", "b) Usando print()", "c) Usando variáveis"], "correta": "a"},
        {"pergunta": "O que é o design pattern MVC?", "alternativas": [
            "a) Um loop", "b) Modelo-Visão-Controlador", "c) Um tipo de variável"], "correta": "b"},
        {"pergunta": "Como você gerencia migrations em Flask?", "alternativas": [
            "a) Usando Flask-Migrate", "b) Usando loops", "c) Usando print()"], "correta": "a"},
        {"pergunta": "O que é o conceito de CI/CD?", "alternativas": [
            "a) Um tipo de variável", "b) Integração e entrega contínua", "c) Um banco de dados"], "correta": "b"}
    ]

    conn = None
    cursor = None
    try:
        print(
            f"[DEBUG] Tentando conectar ao banco de dados para candidato_id: {candidato_id}")
        conn = get_db_connection()
        if conn is None:
            print(
                f"[DEBUG] Falha ao conectar ao banco de dados para candidato_id: {candidato_id}")
            return jsonify({'error': 'Erro ao conectar ao banco de dados'}), 500

        cursor = conn.cursor()
        print(
            f"[DEBUG] Executando consulta SQL para candidato_id: {candidato_id}")
        cursor.execute("""
            SELECT v.titulo, v.requisitos, v.senioridade
            FROM curriculos c
            JOIN vagas v ON c.vaga_id = v.id
            WHERE c.id = %s
        """, (candidato_id,))
        vaga = cursor.fetchone()
        if not vaga:
            print(
                f"[DEBUG] Candidato ou vaga não encontrado para candidato_id: {candidato_id}")
            return jsonify({'error': 'Candidato ou vaga não encontrado'}), 404

        titulo_vaga, requisitos, senioridade = vaga
        print(
            f"[DEBUG] Vaga encontrada para candidato_id {candidato_id}: título={titulo_vaga}, requisitos={requisitos}, senioridade={senioridade}")

        if not titulo_vaga or not requisitos or not senioridade:
            print(
                f"[DEBUG] Título, requisitos ou senioridade da vaga não encontrados para candidato_id: {candidato_id}")
            return jsonify({'error': 'Título, requisitos ou senioridade da vaga não encontrados'}), 400

        # Escolher o conjunto de perguntas padrão baseado na senioridade
        if senioridade.lower() == "júnior":
            fallback_perguntas = fallback_perguntas_junior
        elif senioridade.lower() == "pleno":
            fallback_perguntas = fallback_perguntas_pleno
        else:  # Sênior ou qualquer outro valor
            fallback_perguntas = fallback_perguntas_senior

        print(
            f"[DEBUG] Gerando perguntas com a IA para candidato_id: {candidato_id}")
        print(
            f"[DEBUG] Dados de entrada para a IA: titulo_vaga={titulo_vaga}, requisitos={requisitos}, senioridade={senioridade}")
        try:
            perguntas_geradas = perguntas_chain.invoke({
                "titulo_vaga": titulo_vaga,
                "requisitos": requisitos,
                "senioridade": senioridade
            })
            print(
                f"[DEBUG] Perguntas geradas para candidato_id {candidato_id}: {perguntas_geradas}")
        except Exception as e:
            print(
                f"[DEBUG] Erro ao gerar perguntas com a IA para candidato_id {candidato_id}: {str(e)}")
            print("[DEBUG] Usando perguntas padrão (fallback) devido ao erro na IA.")
            perguntas_geradas = fallback_perguntas

        # Verificar se a saída é uma lista de perguntas no formato correto
        if not isinstance(perguntas_geradas, list):
            print(
                f"[DEBUG] Saída da IA não é uma lista para candidato_id {candidato_id}: {perguntas_geradas}")
            print(
                "[DEBUG] Usando perguntas padrão (fallback) devido ao formato inválido.")
            perguntas_geradas = fallback_perguntas

        # Validar cada pergunta
        perguntas_validadas = []
        for pergunta in perguntas_geradas:
            if not isinstance(pergunta, dict) or not all(
                key in pergunta for key in ['pergunta', 'alternativas', 'correta']
            ):
                print(
                    f"[DEBUG] Formato inválido de pergunta para candidato_id {candidato_id}: {pergunta}")
                continue
            if not isinstance(pergunta['alternativas'], list) or len(pergunta['alternativas']) != 3:
                print(
                    f"[DEBUG] Alternativas inválidas para candidato_id {candidato_id}: {pergunta['alternativas']}")
                continue
            if pergunta['correta'] not in ['a', 'b', 'c']:
                print(
                    f"[DEBUG] Alternativa correta inválida para candidato_id {candidato_id}: {pergunta['correta']}")
                continue
            perguntas_validadas.append(pergunta)

        # Se menos de 10 perguntas válidas foram geradas, completar com o fallback
        if len(perguntas_validadas) < 10:
            print(
                f"[DEBUG] Apenas {len(perguntas_validadas)} perguntas válidas geradas para candidato_id {candidato_id}. Completando com perguntas padrão.")
            perguntas_validadas.extend(
                fallback_perguntas[:10 - len(perguntas_validadas)])

        # Garantir que haja exatamente 10 perguntas
        perguntas_validadas = perguntas_validadas[:10]

        print(
            f"[DEBUG] Retornando perguntas para candidato_id: {candidato_id}")
        return jsonify({'perguntas': perguntas_validadas})
    except Exception as e:
        print(
            f"[DEBUG] Erro ao gerar perguntas para candidato_id {candidato_id}: {str(e)}")
        print("[DEBUG] Usando perguntas padrão (fallback) devido a erro geral.")
        return jsonify({'perguntas': fallback_perguntas[:10]})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/salvar_questionario/<int:candidato_id>', methods=['POST'])
@login_required
def salvar_questionario(candidato_id):
    print(f"[DEBUG] Acessando rota /salvar_questionario/{candidato_id}")
    try:
        data = request.get_json()
        perguntas = data.get('perguntas', [])
        if not perguntas:
            print(
                f"[DEBUG] Nenhuma pergunta fornecida para candidato_id: {candidato_id}")
            return jsonify({'error': 'Nenhuma pergunta fornecida'}), 400

        conn = get_db_connection()
        if conn is None:
            print(
                f"[DEBUG] Falha ao conectar ao banco de dados para salvar questionário do candidato_id: {candidato_id}")
            return jsonify({'error': 'Erro ao conectar ao banco de dados'}), 500

        cursor = conn.cursor()
        try:
            # Inserir ou atualizar o questionário no banco
            cursor.execute("""
                INSERT INTO questionarios (candidato_id, perguntas)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE perguntas = %s, criado_em = NOW()
            """, (candidato_id, json.dumps(perguntas), json.dumps(perguntas)))
            conn.commit()
            print(
                f"[DEBUG] Questionário salvo com sucesso para candidato_id: {candidato_id}")
            return jsonify({'message': 'Questionário salvo com sucesso'})
        except Exception as e:
            print(
                f"[DEBUG] Erro ao executar query para salvar questionário do candidato_id {candidato_id}: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(
            f"[DEBUG] Erro ao salvar questionário para candidato_id {candidato_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/analisar-candidatos', methods=['POST'])
@login_required
def analisar_candidatos():
    try:
        print("Acessando rota /analisar-candidatos")  # Log para depuração
        data = request.get_json()
        candidatos_ids = data.get('candidatos', [])
        vaga_id = data.get('vaga_id')

        # Log para depuração
        print(
            f"Dados recebidos: candidatos_ids={candidatos_ids}, vaga_id={vaga_id}")

        if not candidatos_ids or not vaga_id:
            print("Erro: Candidatos ou vaga não fornecidos")
            return jsonify({'error': 'Candidatos e vaga são obrigatórios'}), 400

        # Garantir que candidatos_ids seja uma lista de inteiros
        try:
            candidatos_ids = [int(candidato_id)
                              for candidato_id in candidatos_ids]
        except ValueError as e:
            print(f"Erro: IDs de candidatos inválidos - {str(e)}")
            return jsonify({'error': 'IDs de candidatos inválidos'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Buscar a vaga
        cursor.execute(
            "SELECT id, titulo, requisitos FROM vagas WHERE id = %s", (vaga_id,))
        vaga = cursor.fetchone()
        if not vaga:
            cursor.close()
            conn.close()
            print("Erro: Vaga não encontrada")
            return jsonify({'error': 'Vaga não encontrada'}), 404

        requisitos_vaga = vaga['requisitos'].split(
            ', ') if vaga['requisitos'] else []
        print(f"Requisitos da vaga: {requisitos_vaga}")  # Log para depuração

        # Buscar os candidatos selecionados na tabela curriculos
        placeholders = ','.join(['%s'] * len(candidatos_ids))
        query = f"SELECT id, nome, conteudo FROM curriculos WHERE id IN ({placeholders})"
        print(f"Query a ser executada: {query}")  # Log para depuração
        print(f"Parâmetros: {candidatos_ids}")  # Log para depuração

        cursor.execute(query, tuple(candidatos_ids))
        candidatos = cursor.fetchall()

        print(f"Candidatos encontrados: {candidatos}")  # Log para depuração

        cursor.close()
        conn.close()

        if not candidatos:
            print("Erro: Nenhum candidato encontrado")
            return jsonify({'error': 'Nenhum candidato encontrado'}), 404

        # Lógica de análise (comparar habilidades, calcular pontuação e gerar observações)
        resultados = []
        for candidato in candidatos:
            candidato_id = candidato['id']
            nome = candidato['nome']
            conteudo = candidato['conteudo']
            habilidades_candidato = conteudo.split(', ') if conteudo else []
            # Log para depuração
            print(f"Habilidades do candidato {nome}: {habilidades_candidato}")

            # Calcular a compatibilidade com a vaga
            compatibilidade = 0
            requisitos_atendidos = []
            requisitos_faltantes = []

            for req in requisitos_vaga:
                encontrado = False
                for habilidade in habilidades_candidato:
                    if req.lower() in habilidade.lower():
                        compatibilidade += 1
                        requisitos_atendidos.append(req)
                        encontrado = True
                        break
                if not encontrado:
                    requisitos_faltantes.append(req)

            compatibilidade_percentual = (
                compatibilidade / len(requisitos_vaga)) * 100 if requisitos_vaga else 0
            # Log para depuração
            print(
                f"Compatibilidade de {nome}: {compatibilidade}/{len(requisitos_vaga)} = {compatibilidade_percentual}%")

            # Gerar observações
            observacoes = []
            if compatibilidade_percentual == 100:
                observacoes.append(
                    "Candidato atende a todos os requisitos da vaga, sendo uma excelente escolha.")
            else:
                if requisitos_atendidos:
                    observacoes.append(
                        f"Possui habilidades relevantes: {', '.join(requisitos_atendidos)}.")
                if requisitos_faltantes:
                    observacoes.append(
                        f"Faltam os seguintes requisitos: {', '.join(requisitos_faltantes)}.")
                else:
                    observacoes.append(
                        "Não possui nenhuma das habilidades requeridas pela vaga.")

            # Considerar experiência (se aplicável)
            experiencia_requerida = None
            for req in requisitos_vaga:
                if "anos de experiência" in req.lower():
                    try:
                        # Ex.: "2" em "2 anos de experiência"
                        experiencia_requerida = int(req.split()[0])
                        break
                    except (ValueError, IndexError):
                        continue

            if experiencia_requerida:
                experiencia_encontrada = False
                for habilidade in habilidades_candidato:
                    if "anos de" in habilidade.lower():
                        try:
                            # Ex.: "3" em "3 anos de desenvolvimento"
                            anos_candidato = int(habilidade.split()[0])
                            if anos_candidato >= experiencia_requerida:
                                observacoes.append(
                                    f"Possui experiência suficiente ({anos_candidato} anos), atendendo ao requisito de {experiencia_requerida} anos.")
                            else:
                                observacoes.append(
                                    f"Possui {anos_candidato} anos de experiência, mas o requisito é de {experiencia_requerida} anos.")
                            experiencia_encontrada = True
                            break
                        except (ValueError, IndexError):
                            continue
                if not experiencia_encontrada:
                    observacoes.append(
                        f"Não foi possível verificar a experiência do candidato em relação ao requisito de {experiencia_requerida} anos.")

            # Log para depuração
            print(f"Observações geradas para {nome}: {observacoes}")

            # Pontuação final (baseada na compatibilidade)
            pontuacao_final = compatibilidade_percentual

            resultados.append({
                'id': candidato_id,
                'nome': nome,
                'habilidades': conteudo if conteudo else 'N/A',
                'compatibilidade': round(compatibilidade_percentual, 2),
                'pontuacao_final': round(pontuacao_final, 2),
                'observacoes': observacoes  # Certificar que observações estão sendo incluídas
            })

        # Ordenar por pontuação final (maior para menor)
        resultados.sort(key=lambda x: x['pontuacao_final'], reverse=True)

        # Determinar o melhor candidato
        melhor_candidato = resultados[0] if resultados else None

        print(f"Resultados da análise: {resultados}")  # Log para depuração
        print(f"Melhor candidato: {melhor_candidato}")  # Log para depuração

        return jsonify({
            'resultados': resultados,
            'melhor_candidato': melhor_candidato
        }), 200
    except mysql.connector.Error as e:
        # Log para depuração
        print(f"Erro ao analisar candidatos (MySQL): {str(e)}")
        return jsonify({'error': f'Erro ao analisar candidatos: {str(e)}'}), 500
    except Exception as e:
        # Log para depuração
        print(f"Erro inesperado ao analisar candidatos: {str(e)}")
        return jsonify({'error': f'Erro inesperado ao analisar candidatos: {str(e)}'}), 500


@app.route('/selecionar_candidatos', methods=['GET'])
@login_required
def selecionar_candidatos():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Buscar todas as vagas
        cursor.execute("SELECT id, titulo FROM vagas")
        vagas = cursor.fetchall()

        # Para cada vaga, buscar os candidatos aprovados
        for vaga in vagas:
            cursor.execute(
                """
                SELECT id, nome, etapa, status
                FROM curriculos
                WHERE vaga_id = %s AND status = 'aprovado' AND etapa IS NOT NULL
                ORDER BY etapa
                """,
                (vaga['id'],)
            )
            vaga['candidatos'] = cursor.fetchall()

        cursor.close()
        conn.close()

        # Determinar a etapa atual (baseado no candidato mais avançado)
        etapa_atual = 1
        for vaga in vagas:
            for candidato in vaga['candidatos']:
                if candidato['etapa'] and candidato['etapa'] > etapa_atual:
                    etapa_atual = candidato['etapa']

        print(
            f"[DEBUG] Dados para selecionar_candidatos: {vagas}, Etapa atual: {etapa_atual}")
        return render_template('selecionar_candidatos.html', vagas=vagas, etapa_atual=etapa_atual)
    except Exception as e:
        cursor.close()
        conn.close()
        print(f"[DEBUG] Erro ao buscar candidatos para seleção: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/sugerir_detalhes_vaga', methods=['POST'])
@login_required
def sugerir_detalhes_vaga():
    try:
        data = request.get_json()
        titulo = data.get('titulo', '').lower().strip()

        if not titulo:
            return jsonify({'error': 'Título da vaga é obrigatório'}), 400

        print(f"Gerando sugestões para o título: {titulo}")

        # Gerar sugestões diretamente com o Grok
        suggestion_result = suggestion_chain.run(titulo=titulo)

        # Parsear o resultado do Grok
        sugestoes = {
            'beneficios': '',
            'descricao': '',
            'requisitos': ''
        }

        for line in suggestion_result.split('\n'):
            if line.startswith('Benefícios:'):
                sugestoes['beneficios'] = line.replace(
                    'Benefícios:', '').strip()
            elif line.startswith('Descrição:'):
                sugestoes['descricao'] = line.replace('Descrição:', '').strip()
            elif line.startswith('Requisitos:'):
                sugestoes['requisitos'] = line.replace(
                    'Requisitos:', '').strip()

        # Valores padrão caso o Grok não retorne informações completas
        if not sugestoes['beneficios']:
            sugestoes['beneficios'] = "Vale-refeição, Plano de saúde, Horário flexível"
        if not sugestoes['descricao']:
            sugestoes['descricao'] = "Atuar no desenvolvimento de projetos relacionados à área, colaborando com a equipe."
        if not sugestoes['requisitos']:
            sugestoes['requisitos'] = "Conhecimentos técnicos relevantes, Experiência na área, Boa comunicação"

        print(f"Sugestões geradas: {sugestoes}")

        return jsonify(sugestoes), 200
    except Exception as e:
        print(f"Erro ao sugerir detalhes da vaga: {str(e)}")
        return jsonify({'error': f'Erro ao sugerir detalhes da vaga: {str(e)}'}), 500


@app.route('/cadastro_vagas')
@login_required
def cadastro_vagas():
    print("Acessando a rota /cadastro_vagas")  # Log para depuração
    return render_template('cadastro_vagas.html')


@app.route('/cadastrar_vaga', methods=['POST'])
@login_required
def cadastrar_vaga():
    try:
        data = request.get_json()
        print(f"Dados recebidos para cadastro de vaga: {data}")

        # Extrair os dados do formulário
        titulo = data.get('titulo')
        senioridade = data.get('senioridade')
        tipo_contrato = data.get('tipo_contrato')
        localizacao = data.get('localizacao')
        modalidade = data.get('modalidade')
        faixa_salarial = data.get('faixa_salarial')
        beneficios = data.get('beneficios')
        descricao = data.get('descricao')
        requisitos = data.get('requisitos')  # String separada por vírgulas
        status = data.get('status', 'Aberta')
        categoria = data.get('categoria')
        prioridade = data.get('prioridade', 'Média')

        if not titulo:
            return jsonify({'error': 'O título da vaga é obrigatório'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Inserir a nova vaga
        query = """
            INSERT INTO vagas (titulo, senioridade, tipo_contrato, localizacao, modalidade, faixa_salarial, beneficios, descricao, requisitos, status, categoria, prioridade, data_criacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        params = (titulo, senioridade, tipo_contrato, localizacao, modalidade,
                  faixa_salarial, beneficios, descricao, requisitos, status, categoria, prioridade)
        cursor.execute(query, params)
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'message': 'Vaga cadastrada com sucesso!'}), 201
    except mysql.connector.Error as e:
        print(f"Erro ao cadastrar vaga (MySQL): {str(e)}")
        return jsonify({'error': f'Erro ao cadastrar vaga: {str(e)}'}), 500
    except Exception as e:
        print(f"Erro inesperado ao cadastrar vaga: {str(e)}")
        return jsonify({'error': f'Erro inesperado ao cadastrar vaga: {str(e)}'}), 500


@app.route('/vagas', methods=['GET'])
@login_required
def listar_vagas():
    print("[DEBUG] Recebendo requisição GET para /vagas")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM vagas")
        vagas = cursor.fetchall()
        cursor.close()
        conn.close()
        print(f"[DEBUG] Vagas encontradas: {vagas}")
        return jsonify(vagas)
    except Exception as e:
        cursor.close()
        conn.close()
        print(f"[DEBUG] Erro ao buscar vagas: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/analisar_curriculos', methods=['POST'])
@login_required
def analisar_curriculos():
    print("Recebendo requisição POST para /analisar_curriculos")
    data = request.get_json()
    print(f"Dados recebidos: {data}")
    vaga_id = data.get('vaga_id')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Busca requisitos da vaga
    cursor.execute("SELECT requisitos FROM vagas WHERE id = %s", (vaga_id,))
    vaga = cursor.fetchone()
    if not vaga:
        cursor.close()
        conn.close()
        print(f"Vaga ID {vaga_id} não encontrada")
        return jsonify({'error': 'Vaga não encontrada'}), 404

    requisitos = vaga['requisitos']
    print(f"Requisitos da vaga: {requisitos}")

    # Busca todos os currículos
    cursor.execute("SELECT id, nome, conteudo FROM curriculos")
    curriculos = cursor.fetchall()
    print(f"Currículos encontrados: {len(curriculos)}")

    # Inicializa o modelo Groq (usando Grok)
    llm = ChatGroq(
        model="grok",
        temperature=0.2,
        max_retries=2
    )

    # Define o parser para garantir saída JSON
    parser = JsonOutputParser()

    # Prompt para análise
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Você é um especialista em RH. Analise o currículo fornecido e calcule uma pontuação de compatibilidade (0 a 100) com base nos requisitos da vaga. Retorne apenas um JSON com a estrutura: {{ "id": id_curriculo, "nome": nome_curriculo, "pontuacao": pontuacao }}.
        Currículo: {curriculo}
        Requisitos da vaga: {requisitos}"""),
        ("human", "Analise o currículo e retorne a pontuação.")
    ])

    # Cria a cadeia LangChain
    chain = prompt | llm | parser

    resultados = []
    for curriculo in curriculos:
        try:
            resultado = chain.invoke({
                "curriculo": curriculo['conteudo'],
                "requisitos": requisitos
            })
            resultados.append({
                "id": curriculo['id'],
                "nome": curriculo['nome'],
                "pontuacao": resultado.get('pontuacao', 0)
            })
            print(f"Análise do currículo {curriculo['nome']}: {resultado}")
        except Exception as e:
            print(f"Erro ao analisar currículo {curriculo['nome']}: {e}")

    # Ordena por pontuação e limita a 10
    resultados = sorted(
        resultados, key=lambda x: x['pontuacao'], reverse=True)[:10]
    print(f"Resultados finais: {resultados}")

    cursor.close()
    conn.close()
    return jsonify(resultados)



# ===================================================================
# INÍCIO DAS NOVAS ROTAS PARA CADASTRO E VISUALIZAÇÃO DE PROMOTORES
# ===================================================================



# Database connection function
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

# Configure uma pasta para uploads
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Crie a pasta se ela não existir
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Rota para renderizar a página de cadastro de promotores
@app.route('/cadastro_promotores')
@login_required
def cadastro_promotores():
    return render_template('cadastro_promotores.html')

# Rota para renderizar a página de visualização de rotas
@app.route('/visualizacao_rotas.html') # Consider making this just '/visualizacao_rotas' for cleaner URLs
@login_required
def visualizacao_rotas():
    return render_template('visualizacao_rotas.html')

# Endpoint da API para salvar um novo promotor e suas rotas


@app.route('/api/promotores', methods=['POST'])
@login_required
def add_promoter_api():
    # Lógica de upload de foto (continua a mesma)
    photo_url = None
    if 'promoter_photo' in request.files:
        photo_file = request.files['promoter_photo']
        if photo_file.filename != '':
            filename = secure_filename(photo_file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo_file.save(save_path)
            photo_url = f'/static/uploads/{filename}'

    # Dicionário sem a matrícula
    promoter_info = {
        'nome': request.form.get('promoter_name'),
        'email': request.form.get('promoter_email'),
        'telefone': request.form.get('promoter_phone'),
        'foto_url': photo_url,
        'responsavel_gestor': request.form.get('manager_name'),
        'email_gestor': request.form.get('manager_email'),
        'contato_gestor': request.form.get('manager_contact')
    }

    suppliers_str = request.form.get('suppliers', '[]')
    routes_str = request.form.get('routes', '[]')
    try:
        suppliers_list = json.loads(suppliers_str)
        routes_info = json.loads(routes_str)
    except json.JSONDecodeError:
        return jsonify({'error': 'Formato de dados inválido'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Falha na conexão com o banco de dados'}), 500

    cursor = conn.cursor()

    try:
        # Query de INSERT sem a matrícula
        promoter_query = """
            INSERT INTO promotores (nome, email, telefone, foto_url, responsavel_gestor, email_gestor, contato_gestor)
            VALUES (%(nome)s, %(email)s, %(telefone)s, %(foto_url)s, %(responsavel_gestor)s, %(email_gestor)s, %(contato_gestor)s)
        """
        cursor.execute(promoter_query, promoter_info)
        id_promotor = cursor.lastrowid

        # Inserir múltiplos fornecedores (esta parte continua)
        if suppliers_list and id_promotor:
            supplier_query = "INSERT INTO promotor_fornecedores (id_promotor, id_fornecedor) VALUES (%s, %s)"
            supplier_values = [(id_promotor, supplier['id']) for supplier in suppliers_list]
            if supplier_values:
                cursor.executemany(supplier_query, supplier_values)

        # Inserir rotas (esta parte continua)
        if routes_info and id_promotor:
            route_query = "INSERT INTO rotas (id_promotor, loja, dia_semana, hora_entrada, hora_saida) VALUES (%s, %s, %s, %s, %s)"
            route_values = [
                (id_promotor, r.get('store'), r.get('day'), r.get('start_time') or None, r.get('end_time') or None)
                for r in routes_info if r.get('store') and r.get('day')
            ]
            if route_values:
                cursor.executemany(route_query, route_values)

        conn.commit()
        return jsonify({'message': 'Promotor e rotas cadastrados com sucesso!', 'id_promotor': id_promotor}), 201

    except mysql.connector.Error as err:
        conn.rollback();
        print(f"Erro de SQL: {err}")
        return jsonify({'error': f'Erro ao salvar no banco de dados: {err}'}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@app.route('/api/fornecedores', methods=['GET'])
@login_required
def get_fornecedores_api():
    search_term = request.args.get('term', '')
    if len(search_term) < 2:
        return jsonify([])
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Falha na conexão com o banco de dados'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        # Esta query é a versão corrigida que busca tanto no nome quanto no código corretamente
        query = """
            SELECT id, codigo, nome_fantasia 
            FROM fornecedores 
            WHERE nome_fantasia LIKE %s OR CAST(codigo AS CHAR) LIKE %s
            LIMIT 10; 
        """
        like_pattern = f"%{search_term}%"
        
        cursor.execute(query, (like_pattern, like_pattern))
        fornecedores = cursor.fetchall()
        
        return jsonify(fornecedores), 200
        
    except mysql.connector.Error as err:
        print(f"Erro de SQL ao buscar fornecedores: {err}")
        return jsonify({'error': f'Erro ao buscar dados: {err}'}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()



@app.route('/api/rotas', methods=['GET'])
@login_required
def get_all_routes_api():
    # Pega o parâmetro de status da URL, o padrão é 'ativo'
    status_filter = request.args.get('status', 'ativo')

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Falha na conexão com o banco de dados'}), 500
    cursor = conn.cursor(dictionary=True)

    # A query agora é dinâmica
    query = """
        SELECT
            r.id,
            p.id AS promoterId,
            p.nome AS promoterName,
            p.foto_url AS promoterPhoto,
            p.status AS promoterStatus, -- ADICIONADO PARA O FRONTEND SABER O STATUS
            (
                SELECT GROUP_CONCAT(f.nome_fantasia SEPARATOR ', ')
                FROM promotor_fornecedores pf
                JOIN fornecedores f ON pf.id_fornecedor = f.id
                WHERE pf.id_promotor = p.id
            ) AS brand,
            r.loja AS store,
            r.dia_semana AS day,
            TIME_FORMAT(r.hora_entrada, '%H:%i') AS startTime,
            TIME_FORMAT(r.hora_saida, '%H:%i') AS endTime
        FROM rotas r
        JOIN promotores p ON r.id_promotor = p.id
    """
    
    # Adiciona o filtro de status dinamicamente
    params = []
    if status_filter == 'ativo':
        query += " WHERE p.status = %s"
        params.append('ativo')

    query += """
        ORDER BY 
            p.nome,
            CASE r.dia_semana
                WHEN 'domingo' THEN 1 WHEN 'segunda' THEN 2 WHEN 'terca' THEN 3
                WHEN 'quarta' THEN 4 WHEN 'quinta' THEN 5 WHEN 'sexta' THEN 6
                WHEN 'sabado' THEN 7
            END;
    """
    
    try:
        cursor.execute(query, tuple(params))
        routes = cursor.fetchall()
        return jsonify(routes), 200
    except mysql.connector.Error as err:
        print(f"Erro de SQL: {err}")
        return jsonify({'error': f'Erro ao buscar dados: {err}'}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# Adicione esta nova rota em qualquer lugar do seu app.py

@app.route('/api/promotores/search', methods=['GET'])
@login_required
def search_promoters_api():
    search_term = request.args.get('term', '')
    if len(search_term) < 2:
        return jsonify([])

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Falha na conexão com o banco de dados'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Busca todos os promotores (ativos e suspensos) e retorna o status
        query = """
            SELECT id, nome, status FROM promotores
            WHERE nome LIKE %s
            LIMIT 5
        """
        like_pattern = f"%{search_term}%"
        cursor.execute(query, (like_pattern,))
        promoters = cursor.fetchall()
        return jsonify(promoters)
    except mysql.connector.Error as err:
        print(f"Erro de SQL na busca de promotores: {err}")
        return jsonify({'error': str(err)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


            # ROTA PARA BUSCAR OS DADOS DE UM PROMOTOR ESPECÍFICO





# ROTA PARA BUSCAR E ATUALIZAR OS DADOS DE UM PROMOTOR ESPECÍFICO
@app.route('/api/promotores/<int:promoter_id>', methods=['GET', 'POST'])
@login_required
def update_promoter(promoter_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Falha na conexão com o banco de dados'}), 500

    try:
        # SE A REQUISIÇÃO FOR GET, APENAS BUSCA OS DADOS
        if request.method == 'GET':
            cursor = conn.cursor(dictionary=True)
            promoter_data = {}
            
            cursor.execute("SELECT * FROM promotores WHERE id = %s", (promoter_id,))
            promoter = cursor.fetchone()
            if not promoter:
                return jsonify({'error': 'Promotor não encontrado'}), 404
            promoter_data['details'] = promoter

            cursor.execute("""
                SELECT f.id, f.codigo, f.nome_fantasia 
                FROM promotor_fornecedores pf
                JOIN fornecedores f ON pf.id_fornecedor = f.id
                WHERE pf.id_promotor = %s
            """, (promoter_id,))
            promoter_data['suppliers'] = cursor.fetchall()

            cursor.execute("SELECT * FROM rotas WHERE id_promotor = %s", (promoter_id,))
            routes = cursor.fetchall()
            for route in routes:
                if route.get('hora_entrada'):
                    route['hora_entrada'] = str(route['hora_entrada'])[:5]
                if route.get('hora_saida'):
                    route['hora_saida'] = str(route['hora_saida'])[:5]
            promoter_data['routes'] = routes
            
            cursor.close()
            conn.close()
            return jsonify(promoter_data)

        # SE A REQUISIÇÃO FOR POST, ATUALIZA OS DADOS NO BANCO
        elif request.method == 'POST':
            cursor = conn.cursor()

            photo_url = request.form.get('existing_photo_url') # Pega a URL da foto existente
            if 'promoter_photo' in request.files:
                photo_file = request.files['promoter_photo']
                if photo_file.filename != '':
                    filename = secure_filename(photo_file.filename)
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    photo_file.save(save_path)
                    photo_url = f'/static/uploads/{filename}'

            # --- CORREÇÃO AQUI: Usando os nomes corretos do formulário HTML ---
            promoter_info = {
                'id': promoter_id,
                'nome': request.form.get('promoter_name'),
                'email': request.form.get('promoter_email'),
                'telefone': request.form.get('promoter_phone'),
                'foto_url': photo_url,
                'responsavel_gestor': request.form.get('manager_name'),
                'email_gestor': request.form.get('manager_email'),
                'contato_gestor': request.form.get('manager_contact')
            }

            update_query = """
                UPDATE promotores SET
                    nome = %(nome)s, email = %(email)s, telefone = %(telefone)s, foto_url = %(foto_url)s,
                    responsavel_gestor = %(responsavel_gestor)s, email_gestor = %(email_gestor)s, contato_gestor = %(contato_gestor)s
                WHERE id = %(id)s
            """
            cursor.execute(update_query, promoter_info)

            suppliers_list = json.loads(request.form.get('suppliers', '[]'))
            cursor.execute("DELETE FROM promotor_fornecedores WHERE id_promotor = %s", (promoter_id,))
            if suppliers_list:
                supplier_values = [(promoter_id, s['id']) for s in suppliers_list]
                if supplier_values:
                    cursor.executemany("INSERT INTO promotor_fornecedores (id_promotor, id_fornecedor) VALUES (%s, %s)", supplier_values)

            routes_info = json.loads(request.form.get('routes', '[]'))
            cursor.execute("DELETE FROM rotas WHERE id_promotor = %s", (promoter_id,))
            if routes_info:
                # Filtra rotas incompletas ANTES de inserir
                valid_routes = [r for r in routes_info if r.get('store') and r.get('day')]
                if valid_routes:
                    route_values = [(promoter_id, r.get('store'), r.get('day'), r.get('start_time') or None, r.get('end_time') or None) for r in valid_routes]
                    if route_values:
                        cursor.executemany("INSERT INTO rotas (id_promotor, loja, dia_semana, hora_entrada, hora_saida) VALUES (%s, %s, %s, %s, %s)", route_values)

            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'message': 'Promotor atualizado com sucesso!'}), 200

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        print(f"Erro ao processar promotor: {e}")
        return jsonify({'error': f'Erro inesperado no servidor: {str(e)}'}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()
# ROTA PARA ATUALIZAR UM PROMOTOR EXISTENTE


@app.route('/api/promotores/<int:promoter_id>/status', methods=['POST'])
@login_required
def update_promoter_status(promoter_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Requisição inválida, corpo JSON ausente'}), 400
        
    new_status = data.get('status')

    if not new_status in ['ativo', 'suspenso']:
        return jsonify({'error': 'Status inválido. Deve ser "ativo" ou "suspenso"'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Falha na conexão com o banco de dados'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE promotores SET status = %s WHERE id = %s", (new_status, promoter_id))
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Nenhum promotor encontrado com este ID'}), 404
            
        return jsonify({'message': f'Promotor definido como {new_status} com sucesso!'})
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Erro de SQL ao atualizar status: {err}")
        return jsonify({'error': str(err)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
# ===================================================================
# FIM DAS NOVAS ROTAS
# ===================================================================



# ===================================================================
# INÍCIO DAS NOVAS ROTAS PARA CADASTRO DE CAMPANHAS
# ===================================================================


campanhas_cadastradas = [
    {
        "id": 1,
        "nome": "Campanha Vizzela - Jul/Set",
        "data_inicio": "11/07/2025",
        "data_fim": "11/09/2025",
        "status": "Ativa"
    },
    {
        "id": 2,
        "nome": "Campanha Dia dos Pais",
        "data_inicio": "01/08/2025",
        "data_fim": "15/08/2025",
        "status": "Futura"
    },
    {
        "id": 3,
        "nome": "Campanha de Inverno",
        "data_inicio": "01/06/2025",
        "data_fim": "30/06/2025",
        "status": "Encerrada"
    }
]

# Rota para a PÁGINA PRINCIPAL, que lista as campanhas
# Ex: http://127.0.0.1:5000/
@app.route('/painel_campanha')
def painel_campanha():
    return render_template('painel_campanha.html', campanhas=campanhas_cadastradas)

# Rota para a TELA DE CADASTRO de novas campanhas
# Ex: http://127.0.0.1:5000/nova-campanha
@app.route('/nova-campanha')
def nova_campanha():
    return render_template('nova_campanha.html')


@app.route('/painel-performance')
def painel_principal():
    return render_template('painel_performance.html')

@app.route('/painel_diagnostico')
def painel_diagnostico():
    return render_template('painel_diagnostico.html')

# ===================================================================
# FIM DAS NOVAS ROTAS
# ===================================================================



if __name__ == '__main__':
    print("Iniciando o servidor Flask...")
    app.run(debug=True, host='0.0.0.0', port=5000)