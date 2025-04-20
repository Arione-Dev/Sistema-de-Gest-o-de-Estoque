
# from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
# import mysql.connector
# from langchain_groq import ChatGroq
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import JsonOutputParser
# import os
# from dotenv import load_dotenv
# from datetime import datetime
# import pandas as pd
# from io import BytesIO

# # Carrega variáveis do arquivo .env
# load_dotenv()

# app = Flask(__name__)
# app.secret_key = os.getenv('SECRET_KEY')

# db_config = {
#     'host': os.getenv('DB_HOST'),
#     'user': os.getenv('DB_USER'),
#     'password': os.getenv('DB_PASSWORD'),
#     'database': os.getenv('DB_NAME')
# }

# # Configura a chave da API do Groq
# os.environ["GROQ_API_KEY"] = os.getenv('GROQ_API_KEY')

# # Função para conectar ao banco


# def get_db_connection():
#     return mysql.connector.connect(**db_config)

# # Decorador para proteger rotas


# def login_required(f):
#     def wrap(*args, **kwargs):
#         print(f"Verificando sessão: {session}")
#         if 'user' not in session:
#             print("Usuário não autenticado. Redirecionando para login.")
#             return redirect(url_for('login_page'))
#         print(f"Usuário autenticado: {session['user']}")
#         return f(*args, **kwargs)
#     wrap.__name__ = f.__name__
#     return wrap

# # Rotas do sistema


# @app.route('/login', methods=['GET'])
# def login_page():
#     print(f"Verificando sessão na rota /login (GET): {session}")
#     if 'user' in session:
#         print("Usuário já autenticado. Redirecionando para index.")
#         return redirect(url_for('index'))
#     print("Renderizando página de login.")
#     return render_template('login.html')


# @app.route('/login', methods=['POST'])
# def login():
#     print("Recebendo requisição POST para /login")
#     data = request.get_json()
#     print(f"Dados recebidos: {data}")
#     matricula = data.get('matricula')
#     senha = data.get('senha')

#     if not matricula or not senha:
#         print("Matrícula ou senha não fornecidos.")
#         return jsonify({'success': False, 'message': 'Matrícula e senha são obrigatórios'}), 400

#     try:
#         conn = get_db_connection()
#         cur = conn.cursor(dictionary=True)
#         print(f"Buscando usuário com matrícula: {matricula}")
#         cur.execute('SELECT * FROM usuarios WHERE matricula = %s', (matricula,))
#         user = cur.fetchone()
#         print(f"Usuário encontrado: {user}")
#         if not user:
#             print(f"Usuário com matrícula {matricula} não encontrado.")
#             return jsonify({'success': False, 'message': 'Matrícula ou senha inválidos'}), 401

#         stored_password = user['senha']
#         print(f"Senha armazenada: {stored_password}")
#         print(f"Verificando senha para matrícula {matricula}")
#         if senha == stored_password:
#             print(f"Login bem-sucedido para matrícula {matricula}.")
#             session['user'] = {
#                 'matricula': user['matricula'], 'nome': user['nome']}
#             print(f"Sessão atualizada: {session}")
#             return jsonify({'success': True, 'redirect': url_for('index')})
#         else:
#             print(f"Senha incorreta para matrícula {matricula}.")
#             return jsonify({'success': False, 'message': 'Matrícula ou senha inválidos'}), 401
#     except mysql.connector.Error as db_err:
#         print(f"Erro no banco de dados: {db_err}")
#         return jsonify({'success': False, 'message': f'Erro no banco de dados: {str(db_err)}'}), 500
#     except Exception as e:
#         print(f"Erro ao fazer login: {e}")
#         return jsonify({'success': False, 'message': f'Erro ao fazer login: {str(e)}'}), 500
#     finally:
#         if 'cur' in locals():
#             cur.close()
#         if 'conn' in locals():
#             conn.close()


# @app.route('/logout', methods=['GET'])
# @login_required
# def logout():
#     print("Executando logout")
#     session.pop('user', None)
#     print("Usuário deslogado. Redirecionando para login.")
#     return redirect(url_for('login_page'))


# @app.route('/')
# @login_required
# def index():
#     print("Acessando rota / (index)")
#     return render_template('index.html')


# @app.route('/relatorio', methods=['GET'])
# @login_required
# def relatorio_page():
#     print("Acessando rota /relatorio")
#     return render_template('relatorio.html')


# @app.route('/produto/<codigo>', methods=['GET'])
# @login_required
# def get_produto(codigo):
#     print(f"Recebendo requisição GET para /produto/{codigo}")
#     conn = get_db_connection()
#     cur = conn.cursor(dictionary=True)
#     try:
#         print(f"Buscando produto com código: {codigo}")
#         cur.execute(
#             'SELECT * FROM produtos WHERE codigo = %s OR barras = %s',
#             (codigo, codigo)
#         )
#         produto = cur.fetchone()
#         if not produto:
#             print(
#                 f"Produto não encontrado. Inserindo novo produto com código: {codigo}")
#             cur.execute(
#                 'INSERT INTO produtos (codigo, barras, descricao, saldo_atual) VALUES (%s, %s, %s, %s)',
#                 (codigo, None, 'Produto Exemplo - Descrição Padrão', 10)
#             )
#             conn.commit()
#             cur.execute(
#                 'SELECT * FROM produtos WHERE codigo = %s',
#                 (codigo,)
#             )
#             produto = cur.fetchone()
#         print(f"Produto encontrado: {produto}")
#         print(
#             f"Descrição do produto: {produto.get('descricao', 'Descrição não encontrada')}")
#         cur.close()
#         conn.close()
#         return jsonify(produto)
#     except Exception as e:
#         cur.close()
#         conn.close()
#         print(f"Erro ao buscar produto: {e}")
#         return jsonify({'error': str(e)}), 500


# @app.route('/ajustar-estoque', methods=['POST'])
# @login_required
# def ajustar_estoque():
#     print("Recebendo requisição POST para /ajustar-estoque")
#     data = request.get_json()
#     print(f"Dados recebidos do frontend: {data}")

#     if not data or 'ajustes' not in data:
#         print("Erro: Lista de ajustes não fornecida.")
#         return jsonify({'error': 'Lista de ajustes é obrigatória'}), 400

#     ajustes = data['ajustes']
#     if not isinstance(ajustes, list) or not ajustes:
#         print("Erro: Lista de ajustes inválida ou vazia.")
#         return jsonify({'error': 'A lista de ajustes deve ser uma lista não vazia'}), 400

#     conn = get_db_connection()
#     cur = conn.cursor(dictionary=True)
#     try:
#         # Verifica a sessão
#         print(f"Sessão atual: {session}")
#         if 'user' not in session or 'matricula' not in session['user'] or 'nome' not in session['user']:
#             print("Erro: Sessão inválida. Usuário não autenticado.")
#             return jsonify({'error': 'Sessão inválida. Faça login novamente.'}), 401

#         matricula = session['user']['matricula']
#         nome_usuario = session['user']['nome']
#         print(f"Matricula: {matricula}, Nome do usuário: {nome_usuario}")

#         # Inicia uma transação
#         conn.start_transaction()
#         print("Transação iniciada.")

#         # Obtém o próximo numero_ajuste
#         cur.execute(
#             'SELECT COALESCE(MAX(numero_ajuste), 0) + 1 as next_numero_ajuste FROM ajustes')
#         numero_ajuste = cur.fetchone()['next_numero_ajuste']
#         print(f"Número do ajuste gerado: {numero_ajuste}")

#         resultados = []
#         for ajuste in ajustes:
#             codigo = ajuste.get('codigo')
#             if not codigo:
#                 print(
#                     f"Erro: Código do produto não fornecido no ajuste: {ajuste}")
#                 return jsonify({'error': 'Código do produto é obrigatório para todos os ajustes'}), 400

#             try:
#                 quantidade = int(ajuste['quantidade'])
#                 print(f"Ajuste para código {codigo}, quantidade: {quantidade}")
#             except (ValueError, KeyError) as ve:
#                 print(
#                     f"Erro: Valor de ajuste inválido para código {codigo}: {ajuste.get('quantidade')}")
#                 return jsonify({'error': f'O valor de ajuste para o código {codigo} deve ser um número inteiro'}), 400

#             # Busca o produto
#             print(f"Buscando produto com código: {codigo}")
#             cur.execute(
#                 'SELECT * FROM produtos WHERE codigo = %s OR barras = %s',
#                 (codigo, codigo)
#             )
#             produto = cur.fetchone()
#             if not produto:
#                 print(f"Produto não encontrado para o código: {codigo}")
#                 return jsonify({'error': f'Produto com código {codigo} não encontrado'}), 404

#             codigo_produto = produto['codigo']
#             descricao = ajuste.get(
#                 'descricao', produto['descricao'] if produto['descricao'] is not None else "Descrição não disponível")
#             print(
#                 f"Código do produto: {codigo_produto}, Descrição: {descricao}")

#             # Atualiza o saldo_atual na tabela produtos
#             print(
#                 f"Executando UPDATE: saldo_atual = saldo_atual + {quantidade} WHERE codigo = {codigo_produto}")
#             cur.execute(
#                 'UPDATE produtos SET saldo_atual = saldo_atual + %s WHERE codigo = %s',
#                 (quantidade, codigo_produto)
#             )
#             print(f"Linhas afetadas pelo UPDATE: {cur.rowcount}")
#             if cur.rowcount == 0:
#                 print("Nenhuma linha afetada pelo UPDATE. Produto não encontrado.")
#                 return jsonify({'error': f'Produto com código {codigo} não encontrado'}), 404

#             # Insere o registro na tabela ajustes com o mesmo numero_ajuste
#             print(
#                 f"Inserindo no ajustes: numero_ajuste = {numero_ajuste}, codigo_produto = {codigo_produto}, quantidade = {quantidade}, matricula = {matricula}, nome_usuario = {nome_usuario}, descricao = {descricao}")
#             cur.execute(
#                 'INSERT INTO ajustes (numero_ajuste, codigo_produto, quantidade, data, matricula, nome_usuario, descricao, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
#                 (numero_ajuste, codigo_produto, quantidade, datetime.now(),
#                  matricula, nome_usuario, descricao, 'PENDENTE')
#             )
#             print(f"Linhas afetadas pelo INSERT: {cur.rowcount}")

#             resultados.append({
#                 'codigo': codigo_produto,
#                 'saldo_atual': produto['saldo_atual'] + quantidade
#             })

#         # Confirma a transação
#         conn.commit()
#         print("Transação commitूकada com sucesso.")

#         # Verifica se os dados foram realmente inseridos
#         cur.execute(
#             'SELECT * FROM ajustes WHERE numero_ajuste = %s', (numero_ajuste,))
#         ajustes_inseridos = cur.fetchall()
#         print(f"Ajustes inseridos no banco: {ajustes_inseridos}")

#         cur.close()
#         conn.close()
#         return jsonify({'success': True, 'numero_ajuste': numero_ajuste, 'resultados': resultados})
#     except mysql.connector.Error as db_err:
#         conn.rollback()
#         print(f"Erro no banco de dados ao ajustar estoque: {db_err}")
#         return jsonify({'error': f'Erro no banco de dados: {str(db_err)}'}), 500
#     except Exception as e:
#         conn.rollback()
#         print(f"Erro ao ajustar estoque: {e}")
#         return jsonify({'error': f'Erro ao ajustar estoque: {str(e)}'}), 500
#     finally:
#         if 'cur' in locals():
#             cur.close()
#         if 'conn' in locals():
#             conn.close()


# @app.route('/liberar-ajustes', methods=['GET'])
# @login_required
# def liberar_ajustes_page():
#     print("Acessando rota /liberar-ajustes")
#     return render_template('liberar_ajustes.html')


# @app.route('/ajustes-pendentes', methods=['GET'])
# @login_required
# def get_ajustes_pendentes():
#     print("Recebendo requisição GET para /ajustes-pendentes")
#     conn = get_db_connection()
#     cur = conn.cursor(dictionary=True)
#     try:
#         cur.execute('''
#             SELECT DISTINCT numero_ajuste, data, matricula, nome_usuario
#             FROM ajustes
#             WHERE status = 'PENDENTE'
#             ORDER BY numero_ajuste DESC
#         ''')
#         ajustes = cur.fetchall()
#         cur.close()
#         conn.close()
#         return jsonify([{
#             'numero_ajuste': item['numero_ajuste'],
#             'data_hora': item['data'].strftime('%d/%m/%Y - %H:%M'),
#             'matricula': item['matricula'],
#             'nome_usuario': item['nome_usuario']
#         } for item in ajustes])
#     except Exception as e:
#         cur.close()
#         conn.close()
#         return jsonify({'error': str(e)}), 500


# @app.route('/liberar-ajuste/<numero_ajuste>', methods=['POST'])
# @login_required
# def liberar_ajuste(numero_ajuste):
#     print(f"Recebendo requisição POST para /liberar-ajuste/{numero_ajuste}")
#     if 'user' not in session or 'nome' not in session['user']:
#         print("Erro: Usuário não autenticado na sessão.")
#         return jsonify({'error': 'Usuário não autenticado. Faça login novamente.'}), 401

#     usuario_liberou = session['user']['nome']
#     print(f"Usuário que está liberando: {usuario_liberou}")
#     conn = get_db_connection()
#     cur = conn.cursor()
#     try:
#         cur.execute(
#             "SELECT COUNT(*) FROM ajustes WHERE numero_ajuste = %s AND status = 'PENDENTE'", (numero_ajuste,))
#         count = cur.fetchone()[0]
#         if count == 0:
#             print(f"Ajuste {numero_ajuste} não encontrado ou já liberado")
#             return jsonify({'error': 'Ajuste não encontrado ou já liberado'}), 404

#         cur.execute(
#             "UPDATE ajustes SET status = 'LIBERADO', usuario_liberou = %s WHERE numero_ajuste = %s",
#             (usuario_liberou, numero_ajuste)
#         )
#         conn.commit()
#         print(f"Ajuste {numero_ajuste} liberado por {usuario_liberou}")
#         cur.close()
#         conn.close()
#         return jsonify({'success': True})
#     except Exception as e:
#         conn.rollback()
#         cur.close()
#         conn.close()
#         print(f"Erro ao liberar ajuste {numero_ajuste}: {str(e)}")
#         return jsonify({'error': str(e)}), 500


# @app.route('/historico', methods=['GET'])
# @login_required
# def get_historico():
#     print("Recebendo requisição GET para /historico")
#     conn = get_db_connection()
#     cur = conn.cursor(dictionary=True)
#     try:
#         print("Buscando histórico de ajustes...")
#         cur.execute('SELECT * FROM ajustes ORDER BY data DESC')
#         historico = cur.fetchall()
#         print(f"Histórico encontrado: {historico}")
#         cur.close()
#         conn.close()
#         return jsonify([
#             {
#                 'id': item['numero_ajuste'],
#                 'produto_codigo': item['codigo_produto'],
#                 'ajuste': item['quantidade'],
#                 'data_hora': item['data'].strftime('%d/%m/%Y - %H:%M'),
#                 'matricula': item['matricula'],
#                 'nome_usuario': item['nome_usuario'],
#                 'descricao': item['descricao']
#             } for item in historico
#         ])
#     except Exception as e:
#         cur.close()
#         conn.close()
#         print(f"Erro ao carregar histórico: {e}")
#         return jsonify({'error': str(e)}), 500


# @app.route('/ajustes_realizados', methods=['GET'])
# @login_required
# def ajustes_realizados():
#     return render_template('ajustes_realizados.html')


# @app.route('/ajustes-realizados-dados', methods=['GET'])
# @login_required
# def get_ajustes_realizados():
#     print("Recebendo requisição GET para /ajustes-realizados-dados")
#     conn = get_db_connection()
#     cur = conn.cursor(dictionary=True)
#     try:
#         cur.execute('''
#             SELECT DISTINCT numero_ajuste, data, matricula, nome_usuario, usuario_liberou
#             FROM ajustes
#             WHERE status = 'LIBERADO'
#             ORDER BY numero_ajuste DESC
#         ''')
#         ajustes = cur.fetchall()
#         cur.close()
#         conn.close()
#         return jsonify([{
#             'numero_ajuste': ajuste['numero_ajuste'],
#             'data_hora': ajuste['data'].strftime('%d/%m/%Y - %H:%M'),
#             'matricula': ajuste['matricula'],
#             'nome_usuario': ajuste['nome_usuario'],
#             'usuario_liberou': ajuste['usuario_liberou']
#         } for ajuste in ajustes])
#     except Exception as e:
#         cur.close()
#         conn.close()
#         return jsonify({'error': str(e)}), 500


# @app.route('/detalhes-ajuste/<numero_ajuste>', methods=['GET'])
# @login_required
# def get_detalhes_ajuste(numero_ajuste):
#     print(f"Recebendo requisição GET para /detalhes-ajuste/{numero_ajuste}")
#     conn = get_db_connection()
#     cur = conn.cursor(dictionary=True)
#     try:
#         cur.execute('''
#             SELECT a.*, p.custo
#             FROM ajustes a
#             LEFT JOIN produtos p ON a.codigo_produto = p.codigo
#             WHERE a.numero_ajuste = %s
#         ''', (numero_ajuste,))
#         ajustes = cur.fetchall()
#         print(f"Dados brutos do banco para ajuste {numero_ajuste}: {ajustes}")
#         if not ajustes:
#             return jsonify({'error': 'Ajuste não encontrado'}), 404

#         ajustes_formatados = [{
#             'numero_ajuste': ajuste['numero_ajuste'],
#             'produto_codigo': ajuste['codigo_produto'],
#             'descricao': ajuste['descricao'],
#             'quantidade': ajuste['quantidade'],
#             'custo': float(str(ajuste['custo']).replace(',', '.')) if ajuste['custo'] is not None else 0.0,
#             'data_hora': ajuste['data'].strftime('%d/%m/%Y - %H:%M'),
#             'matricula': ajuste['matricula'],
#             'nome_usuario': ajuste['nome_usuario'],
#             'usuario_liberou': ajuste['usuario_liberou'],
#             'status': ajuste['status']
#         } for ajuste in ajustes]
#         print(
#             f"Dados formatados para ajuste {numero_ajuste}: {ajustes_formatados}")

#         cur.close()
#         conn.close()

#         if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#             return jsonify(ajustes_formatados)
#         else:
#             return render_template('detalhes_ajuste.html', numero_ajuste=numero_ajuste)
#     except Exception as e:
#         cur.close()
#         conn.close()
#         print(f"Erro ao buscar detalhes do ajuste {numero_ajuste}: {str(e)}")
#         return jsonify({'error': str(e)}), 500


# @app.route('/relatorio-dados', methods=['GET'])
# @login_required
# def get_relatorio_dados():
#     print("Recebendo requisição GET para /relatorio-dados")
#     print(f"Sessão atual: {session}")
#     if 'user' not in session:
#         print("Usuário não autenticado na rota /relatorio-dados.")
#         return jsonify({'error': 'Usuário não autenticado. Faça login novamente.'}), 401

#     data_inicio = request.args.get('data_inicio')
#     data_fim = request.args.get('data_fim')
#     matricula = request.args.get('matricula')
#     numero_ajuste = request.args.get('numero_ajuste')

#     print(
#         f"Parâmetros recebidos - data_inicio: {data_inicio}, data_fim: {data_fim}, matricula: {matricula}, numero_ajuste: {numero_ajuste}")

#     conn = get_db_connection()
#     cur = conn.cursor(dictionary=True)
#     try:
#         query = '''
#             SELECT a.*, p.custo AS custo
#             FROM ajustes a
#             LEFT JOIN produtos p ON a.codigo_produto = p.codigo
#             WHERE 1=1
#         '''
#         params = []

#         if data_inicio:
#             query += ' AND data >= %s'
#             params.append(data_inicio)
#         if data_fim:
#             query += ' AND data <= %s'
#             params.append(data_fim)
#         if matricula:
#             query += ' AND matricula = %s'
#             params.append(matricula)
#         if numero_ajuste:
#             query += ' AND numero_ajuste = %s'
#             params.append(numero_ajuste)

#         query += ' ORDER BY numero_ajuste, data DESC'
#         print(f"Executando consulta: {query} com parâmetros: {params}")
#         cur.execute(query, params)
#         ajustes = cur.fetchall()
#         print(f"Ajustes encontrados: {ajustes}")

#         cur.close()
#         conn.close()
#         return jsonify([{
#             'numero_ajuste': item['numero_ajuste'],
#             'produto_codigo': item['codigo_produto'],
#             'descricao': item['descricao'],
#             'quantidade': item['quantidade'],
#             'custo': float(str(item['custo']).replace(',', '.')) if item['custo'] is not None else 0.0,
#             'data_hora': item['data'].strftime('%d/%m/%Y - %H:%M'),
#             'matricula': item['matricula'],
#             'nome_usuario': item['nome_usuario']
#         } for item in ajustes])
#     except Exception as e:
#         cur.close()
#         conn.close()
#         print(f"Erro ao carregar dados do relatório: {e}")
#         return jsonify({'error': str(e)}), 500


# @app.route('/exportar-relatorio-excel', methods=['GET'])
# @login_required
# def exportar_relatorio_excel():
#     print("Recebendo requisição GET para /exportar-relatorio-excel")
#     data_inicio = request.args.get('data_inicio')
#     data_fim = request.args.get('data_fim')
#     matricula = request.args.get('matricula')
#     numero_ajuste = request.args.get('numero_ajuste')

#     conn = get_db_connection()
#     cur = conn.cursor(dictionary=True)
#     try:
#         query = '''
#             SELECT a.*, p.custo AS custo
#             FROM ajustes a
#             LEFT JOIN produtos p ON a.codigo_produto = p.codigo
#             WHERE 1=1
#         '''
#         params = []

#         if data_inicio:
#             query += ' AND data >= %s'
#             params.append(data_inicio)
#         if data_fim:
#             query += ' AND data <= %s'
#             params.append(data_fim)
#         if matricula:
#             query += ' AND matricula = %s'
#             params.append(matricula)
#         if numero_ajuste:
#             query += ' AND numero_ajuste = %s'
#             params.append(numero_ajuste)

#         query += ' ORDER BY numero_ajuste, data DESC'
#         print(f"Executando consulta: {query} com parâmetros: {params}")
#         cur.execute(query, params)
#         ajustes = cur.fetchall()
#         print(f"Ajustes encontrados: {ajustes}")

#         data = [{
#             'Número do Ajuste': item['numero_ajuste'],
#             'Código do Produto': item['codigo_produto'],
#             'Descrição': item['descricao'],
#             'Quantidade': item['quantidade'],
#             'Custo Unitário (R$)': float(str(item['custo']).replace(',', '.')) if item['custo'] is not None else 0.0,
#             'Custo Total (R$)': (float(str(item['custo']).replace(',', '.')) if item['custo'] is not None else 0.0) * abs(item['quantidade']),
#             'Data/Hora': item['data'].strftime('%d/%m/%Y - %H:%M'),
#             'Matrícula': item['matricula'],
#             'Nome do Usuário': item['nome_usuario']
#         } for item in ajustes]

#         total_custo = sum(item['Custo Total (R$)'] for item in data)
#         data.append({
#             'Número do Ajuste': '',
#             'Código do Produto': '',
#             'Descrição': 'Total Custo',
#             'Quantidade': '',
#             'Custo Unitário (R$)': '',
#             'Custo Total (R$)': total_custo,
#             'Data/Hora': '',
#             'Matrícula': '',
#             'Nome do Usuário': ''
#         })

#         df = pd.DataFrame(data)

#         output = BytesIO()
#         with pd.ExcelWriter(output, engine='openpyxl') as writer:
#             df.to_excel(writer, index=False, sheet_name='Relatório de Ajustes')
#         output.seek(0)

#         cur.close()
#         conn.close()
#         return send_file(
#             output,
#             mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
#             as_attachment=True,
#             download_name=f'relatorio_ajustes_{datetime.now().strftime("%Y%m%d")}.xlsx'
#         )
#     except Exception as e:
#         cur.close()
#         conn.close()
#         print(f"Erro ao exportar relatório para Excel: {e}")
#         return jsonify({'error': str(e)}), 500

# # Módulo CV-Análise


# @app.route('/cv_analise')
# @login_required
# def cv_analise():
#     print("Acessando rota /cv_analise")
#     return render_template('cv_analise.html')


# @app.route('/buscar_curriculos', methods=['GET'])
# @login_required
# def buscar_curriculos():
#     print("Recebendo requisição GET para /buscar_curriculos")
#     nome = request.args.get('nome', '')
#     conn = get_db_connection()
#     cursor = conn.cursor(dictionary=True)
#     query = "SELECT id, nome FROM curriculos WHERE nome LIKE %s LIMIT 10"
#     cursor.execute(query, ('%' + nome + '%',))
#     curriculos = cursor.fetchall()
#     cursor.close()
#     conn.close()
#     return jsonify(curriculos)


# @app.route('/vagas', methods=['GET'])
# @login_required
# def get_vagas():
#     try:
#         print("Acessando rota /vagas")  # Log para depuração
#         conn = get_db_connection()
#         print("Conexão com o banco de dados estabelecida")  # Log para depuração
#         cursor = conn.cursor()
#         cursor.execute("SELECT id, titulo, requisitos FROM vagas")
#         vagas = cursor.fetchall()
#         print(f"Vagas encontradas: {vagas}")  # Log para depuração
#         cursor.close()
#         conn.close()

#         vagas_list = [{'id': vaga[0], 'titulo': vaga[1],
#                        'requisitos': vaga[2]} for vaga in vagas]
#         return jsonify(vagas_list)
#     except Exception as e:
#         print(f"Erro ao carregar vagas: {str(e)}")  # Log para depuração
#         return jsonify({'error': f'Erro ao carregar vagas: {str(e)}'}), 500


# @app.route('/buscar-candidatos', methods=['GET'])
# # @login_required  # Comente temporariamente se ainda estiver testando sem autenticação
# def buscar_candidatos():
#     try:
#         print("Acessando rota /buscar-candidatos")  # Log para depuração
#         nome = request.args.get('nome', '').strip()
#         vaga_id = request.args.get('vaga_id', '')

#         # Log para depuração
#         print(f"Parâmetros recebidos: nome={nome}, vaga_id={vaga_id}")

#         if not vaga_id:
#             print("Erro: Vaga não fornecida")
#             return jsonify({'error': 'Vaga é obrigatória'}), 400

#         conn = get_db_connection()
#         cursor = conn.cursor(dictionary=True)

#         # Buscar os requisitos da vaga (apenas para uso futuro na análise)
#         cursor.execute(
#             "SELECT requisitos FROM vagas WHERE id = %s", (vaga_id,))
#         vaga = cursor.fetchone()
#         if not vaga:
#             cursor.close()
#             conn.close()
#             print("Erro: Vaga não encontrada")
#             return jsonify({'error': 'Vaga não encontrada'}), 404

#         requisitos = vaga['requisitos'].split(
#             ', ') if vaga['requisitos'] else []
#         print(f"Requisitos da vaga: {requisitos}")  # Log para depuração

#         # Buscar todos os candidatos
#         query = "SELECT id, nome, conteudo FROM curriculos"
#         params = []

#         if nome:
#             query += " WHERE nome LIKE %s"
#             params.append(f'%{nome}%')

#         print(f"Query a ser executada: {query}")  # Log para depuração
#         print(f"Parâmetros: {params}")  # Log para depuração

#         cursor.execute(query, params)
#         candidatos = cursor.fetchall()
#         print(f"Candidatos encontrados: {candidatos}")  # Log para depuração

#         # Não filtrar por requisitos na busca, apenas listar todos os candidatos
#         candidatos_filtrados = []
#         for candidato in candidatos:
#             candidatos_filtrados.append({
#                 'id': candidato['id'],
#                 'nome': candidato['nome'],
#                 'habilidades': candidato['conteudo'] if candidato['conteudo'] else 'N/A'
#             })

#         # Log para depuração
#         print(f"Candidatos filtrados: {candidatos_filtrados}")

#         cursor.close()
#         conn.close()

#         return jsonify(candidatos_filtrados), 200
#     except mysql.connector.Error as e:
#         # Log para depuração
#         print(f"Erro ao buscar candidatos (MySQL): {str(e)}")
#         return jsonify({'error': f'Erro ao buscar candidatos: {str(e)}'}), 500
#     except Exception as e:
#         # Log para depuração
#         print(f"Erro inesperado ao buscar candidatos: {str(e)}")
#         return jsonify({'error': f'Erro inesperado ao buscar candidatos: {str(e)}'}), 500


# @app.route('/analisar-candidatos', methods=['POST'])
# # @login_required  # Comente temporariamente se ainda estiver testando sem autenticação
# def analisar_candidatos():
#     try:
#         print("Acessando rota /analisar-candidatos")  # Log para depuração
#         data = request.get_json()
#         candidatos_ids = data.get('candidatos', [])
#         vaga_id = data.get('vaga_id')

#         # Log para depuração
#         print(
#             f"Dados recebidos: candidatos_ids={candidatos_ids}, vaga_id={vaga_id}")

#         if not candidatos_ids or not vaga_id:
#             print("Erro: Candidatos ou vaga não fornecidos")
#             return jsonify({'error': 'Candidatos e vaga são obrigatórios'}), 400

#         # Garantir que candidatos_ids seja uma lista de inteiros
#         try:
#             candidatos_ids = [int(candidato_id)
#                               for candidato_id in candidatos_ids]
#         except ValueError as e:
#             print(f"Erro: IDs de candidatos inválidos - {str(e)}")
#             return jsonify({'error': 'IDs de candidatos inválidos'}), 400

#         conn = get_db_connection()
#         cursor = conn.cursor(dictionary=True)

#         # Buscar a vaga
#         cursor.execute(
#             "SELECT id, titulo, requisitos FROM vagas WHERE id = %s", (vaga_id,))
#         vaga = cursor.fetchone()
#         if not vaga:
#             cursor.close()
#             conn.close()
#             print("Erro: Vaga não encontrada")
#             return jsonify({'error': 'Vaga não encontrada'}), 404

#         requisitos_vaga = vaga['requisitos'].split(
#             ', ') if vaga['requisitos'] else []
#         print(f"Requisitos da vaga: {requisitos_vaga}")  # Log para depuração

#         # Buscar os candidatos selecionados na tabela curriculos
#         placeholders = ','.join(['%s'] * len(candidatos_ids))
#         query = f"SELECT id, nome, conteudo FROM curriculos WHERE id IN ({placeholders})"
#         print(f"Query a ser executada: {query}")  # Log para depuração
#         print(f"Parâmetros: {candidatos_ids}")  # Log para depuração

#         cursor.execute(query, tuple(candidatos_ids))
#         candidatos = cursor.fetchall()

#         print(f"Candidatos encontrados: {candidatos}")  # Log para depuração

#         cursor.close()
#         conn.close()

#         if not candidatos:
#             print("Erro: Nenhum candidato encontrado")
#             return jsonify({'error': 'Nenhum candidato encontrado'}), 404

#         # Lógica de análise (comparar habilidades, calcular pontuação e gerar observações)
#         resultados = []
#         for candidato in candidatos:
#             candidato_id = candidato['id']
#             nome = candidato['nome']
#             conteudo = candidato['conteudo']
#             habilidades_candidato = conteudo.split(', ') if conteudo else []
#             # Log para depuração
#             print(f"Habilidades do candidato {nome}: {habilidades_candidato}")

#             # Calcular a compatibilidade com a vaga
#             compatibilidade = 0
#             requisitos_atendidos = []
#             requisitos_faltantes = []

#             for req in requisitos_vaga:
#                 encontrado = False
#                 for habilidade in habilidades_candidato:
#                     if req.lower() in habilidade.lower():
#                         compatibilidade += 1
#                         requisitos_atendidos.append(req)
#                         encontrado = True
#                         break
#                 if not encontrado:
#                     requisitos_faltantes.append(req)

#             compatibilidade_percentual = (
#                 compatibilidade / len(requisitos_vaga)) * 100 if requisitos_vaga else 0
#             # Log para depuração
#             print(
#                 f"Compatibilidade de {nome}: {compatibilidade}/{len(requisitos_vaga)} = {compatibilidade_percentual}%")

#             # Gerar observações
#             observacoes = []
#             if compatibilidade_percentual == 100:
#                 observacoes.append(
#                     "Candidato atende a todos os requisitos da vaga, sendo uma excelente escolha.")
#             else:
#                 if requisitos_atendidos:
#                     observacoes.append(
#                         f"Possui habilidades relevantes: {', '.join(requisitos_atendidos)}.")
#                 if requisitos_faltantes:
#                     observacoes.append(
#                         f"Faltam os seguintes requisitos: {', '.join(requisitos_faltantes)}.")
#                 else:
#                     observacoes.append(
#                         "Não possui nenhuma das habilidades requeridas pela vaga.")

#             # Considerar experiência (se aplicável)
#             experiencia_requerida = None
#             for req in requisitos_vaga:
#                 if "anos de experiência" in req.lower():
#                     try:
#                         # Ex.: "2" em "2 anos de experiência"
#                         experiencia_requerida = int(req.split()[0])
#                         break
#                     except (ValueError, IndexError):
#                         continue

#             if experiencia_requerida:
#                 experiencia_encontrada = False
#                 for habilidade in habilidades_candidato:
#                     if "anos de" in habilidade.lower():
#                         try:
#                             # Ex.: "3" em "3 anos de desenvolvimento"
#                             anos_candidato = int(habilidade.split()[0])
#                             if anos_candidato >= experiencia_requerida:
#                                 observacoes.append(
#                                     f"Possui experiência suficiente ({anos_candidato} anos), atendendo ao requisito de {experiencia_requerida} anos.")
#                             else:
#                                 observacoes.append(
#                                     f"Possui {anos_candidato} anos de experiência, mas o requisito é de {experiencia_requerida} anos.")
#                             experiencia_encontrada = True
#                             break
#                         except (ValueError, IndexError):
#                             continue
#                 if not experiencia_encontrada:
#                     observacoes.append(
#                         f"Não foi possível verificar a experiência do candidato em relação ao requisito de {experiencia_requerida} anos.")

#             # Log para depuração
#             print(f"Observações geradas para {nome}: {observacoes}")

#             # Pontuação final (baseada na compatibilidade)
#             pontuacao_final = compatibilidade_percentual

#             resultados.append({
#                 'id': candidato_id,
#                 'nome': nome,
#                 'habilidades': conteudo if conteudo else 'N/A',
#                 'compatibilidade': round(compatibilidade_percentual, 2),
#                 'pontuacao_final': round(pontuacao_final, 2),
#                 'observacoes': observacoes  # Certificar que observações estão sendo incluídas
#             })

#         # Ordenar por pontuação final (maior para menor)
#         resultados.sort(key=lambda x: x['pontuacao_final'], reverse=True)

#         # Determinar o melhor candidato
#         melhor_candidato = resultados[0] if resultados else None

#         print(f"Resultados da análise: {resultados}")  # Log para depuração
#         print(f"Melhor candidato: {melhor_candidato}")  # Log para depuração

#         return jsonify({
#             'resultados': resultados,
#             'melhor_candidato': melhor_candidato
#         }), 200
#     except mysql.connector.Error as e:
#         # Log para depuração
#         print(f"Erro ao analisar candidatos (MySQL): {str(e)}")
#         return jsonify({'error': f'Erro ao analisar candidatos: {str(e)}'}), 500
#     except Exception as e:
#         # Log para depuração
#         print(f"Erro inesperado ao analisar candidatos: {str(e)}")
#         return jsonify({'error': f'Erro inesperado ao analisar candidatos: {str(e)}'}), 500


# @app.route('/sugerir_requisitos', methods=['POST'])
# # @login_required
# def sugerir_requisitos():
#     try:
#         data = request.get_json()
#         titulo = data.get('titulo', '').lower().strip()

#         if not titulo:
#             return jsonify({'error': 'Título da vaga é obrigatório'}), 400

#         print(f"Gerando sugestões de requisitos para o título: {titulo}")

#         # Mapeamento de palavras-chave para categorias de cargos
#         # Isso ajuda a IA a entender o contexto do título
#         categorias = {
#             'desenvolvedor': 'Desenvolvimento de Software',
#             'analista de dados': 'Análise de Dados',
#             'gerente de projetos': 'Gestão de Projetos',
#             'front-end': 'Desenvolvimento Front-End',
#             'back-end': 'Desenvolvimento Back-End',
#             'full stack': 'Desenvolvimento Full Stack',
#             'designer': 'Design',
#             'engenheiro de software': 'Engenharia de Software',
#             'devops': 'DevOps',
#             'qa': 'Qualidade de Software',
#             'marketing': 'Marketing',
#             'vendas': 'Vendas'
#         }

#         # Identificar a categoria com base no título
#         categoria = None
#         for chave in categorias.keys():
#             if chave in titulo:
#                 categoria = categorias[chave]
#                 break

#         if not categoria:
#             categoria = 'Geral'
#             print(f"Categoria não identificada, usando padrão: {categoria}")
#         else:
#             print(f"Categoria identificada: {categoria}")

#         # Buscar informações na web sobre requisitos para a categoria ou título
#         query = f"requisitos para {titulo} vaga de emprego"
#         print(f"Query para busca: {query}")

#         # Simulando uma busca na web (aqui eu usaria minha capacidade de busca)
#         # Vou gerar sugestões com base em conhecimento típico de vagas
#         # Para fins de demonstração, vou criar uma lógica que imita uma busca real
#         requisitos_sugeridos = []

#         # Lógica de geração de requisitos com base no título/categoria
#         if 'desenvolvedor' in titulo or 'engenheiro de software' in titulo:
#             if 'python' in titulo:
#                 requisitos_sugeridos.extend(
#                     ['Python', 'Flask ou Django', 'Conhecimento em banco de dados (MySQL, PostgreSQL)', 'Experiência com Git', '2-3 anos de experiência'])
#             elif 'java' in titulo:
#                 requisitos_sugeridos.extend(
#                     ['Java', 'Spring Framework', 'Conhecimento em banco de dados (MySQL, Oracle)', 'Experiência com APIs REST', '3-5 anos de experiência'])
#             elif 'front-end' in titulo:
#                 requisitos_sugeridos.extend(
#                     ['HTML', 'CSS', 'JavaScript', 'React ou Vue.js', 'Conhecimento em UI/UX', '1-2 anos de experiência'])
#             elif 'back-end' in titulo:
#                 requisitos_sugeridos.extend(['Node.js ou Java', 'APIs REST', 'Banco de dados (SQL ou NoSQL)',
#                                             'Conhecimento em arquitetura de software', '3-4 anos de experiência'])
#             elif 'full stack' in titulo:
#                 requisitos_sugeridos.extend(['HTML, CSS, JavaScript', 'React ou Angular',
#                                             'Node.js ou Java', 'Banco de dados (SQL ou NoSQL)', '3-5 anos de experiência'])
#             else:
#                 requisitos_sugeridos.extend(['Linguagem de programação (ex.: Java, Python)',
#                                             'Conhecimento em banco de dados', 'Experiência com Git', '2-3 anos de experiência'])

#         elif 'analista de dados' in titulo:
#             requisitos_sugeridos.extend(['SQL', 'Python ou R', 'Conhecimento em estatística',
#                                         'Ferramentas de visualização (Power BI, Tableau)', '1-2 anos de experiência'])

#         elif 'gerente de projetos' in titulo:
#             requisitos_sugeridos.extend(['Gestão de projetos', 'Metodologias ágeis (Scrum, Kanban)',
#                                         'Habilidades de liderança', 'Conhecimento em ferramentas como Jira', '3-5 anos de experiência'])

#         elif 'designer' in titulo:
#             requisitos_sugeridos.extend(['Figma ou Adobe XD', 'Conhecimento em UI/UX',
#                                         'Design gráfico', 'Prototipagem', '1-2 anos de experiência'])

#         elif 'devops' in titulo:
#             requisitos_sugeridos.extend(['Conhecimento em CI/CD', 'Docker', 'Kubernetes',
#                                         'AWS ou Azure', 'Scripting (Bash, Python)', '3-5 anos de experiência'])

#         elif 'qa' in titulo:
#             requisitos_sugeridos.extend(['Testes manuais e automatizados', 'Selenium ou Cypress',
#                                         'Conhecimento em metodologias ágeis', '1-3 anos de experiência'])

#         elif 'marketing' in titulo:
#             requisitos_sugeridos.extend(
#                 ['Marketing digital', 'SEO e SEM', 'Redes sociais', 'Google Analytics', '1-2 anos de experiência'])

#         elif 'vendas' in titulo:
#             requisitos_sugeridos.extend(['Técnicas de negociação', 'CRM (ex.: Salesforce)',
#                                         'Habilidades de comunicação', 'Experiência em vendas B2B ou B2C', '2-3 anos de experiência'])

#         else:
#             # Caso genérico
#             requisitos_sugeridos.extend(
#                 ['Conhecimentos técnicos relevantes', 'Experiência na área', 'Trabalho em equipe', 'Proatividade'])

#         # Adicionar habilidades interpessoais comuns
#         requisitos_sugeridos.extend(
#             ['Boa comunicação', 'Resolução de problemas'])

#         # Remover duplicatas e formatar
#         requisitos_sugeridos = list(dict.fromkeys(
#             requisitos_sugeridos))  # Remove duplicatas
#         requisitos_string = ', '.join(requisitos_sugeridos)

#         print(f"Requisitos sugeridos: {requisitos_string}")

#         return jsonify({'requisitos': requisitos_string}), 200
#     except Exception as e:
#         print(f"Erro ao sugerir requisitos: {str(e)}")
#         return jsonify({'error': f'Erro ao sugerir requisitos: {str(e)}'}), 500


# @app.route('/cadastro_vagas')
# def cadastro_vagas():
#     print("Acessando a rota /cadastro_vagas")  # Log para depuração
#     return render_template('cadastro_vagas.html')


# @app.route('/cadastrar_vaga', methods=['POST'])
# def cadastrar_vaga():
#     try:
#         data = request.get_json()
#         print(f"Dados recebidos para cadastro de vaga: {data}")

#         # Extrair os dados do formulário
#         titulo = data.get('titulo')
#         senioridade = data.get('senioridade')
#         tipo_contrato = data.get('tipo_contrato')
#         localizacao = data.get('localizacao')
#         modalidade = data.get('modalidade')
#         faixa_salarial = data.get('faixa_salarial')
#         beneficios = data.get('beneficios')
#         descricao = data.get('descricao')
#         requisitos = data.get('requisitos')  # String separada por vírgulas
#         status = data.get('status', 'Aberta')
#         categoria = data.get('categoria')
#         prioridade = data.get('prioridade', 'Média')

#         if not titulo:
#             return jsonify({'error': 'O título da vaga é obrigatório'}), 400

#         conn = get_db_connection()
#         cursor = conn.cursor()

#         # Inserir a nova vaga
#         query = """
#             INSERT INTO vagas (titulo, senioridade, tipo_contrato, localizacao, modalidade, faixa_salarial, beneficios, descricao, requisitos, status, categoria, prioridade, data_criacao)
#             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
#         """
#         params = (titulo, senioridade, tipo_contrato, localizacao, modalidade,
#                   faixa_salarial, beneficios, descricao, requisitos, status, categoria, prioridade)
#         cursor.execute(query, params)
#         conn.commit()

#         cursor.close()
#         conn.close()

#         return jsonify({'message': 'Vaga cadastrada com sucesso!'}), 201
#     except mysql.connector.Error as e:
#         print(f"Erro ao cadastrar vaga (MySQL): {str(e)}")
#         return jsonify({'error': f'Erro ao cadastrar vaga: {str(e)}'}), 500
#     except Exception as e:
#         print(f"Erro inesperado ao cadastrar vaga: {str(e)}")
#         return jsonify({'error': f'Erro inesperado ao cadastrar vaga: {str(e)}'}), 500


# @app.route('/analisar_curriculos', methods=['POST'])
# @login_required
# def analisar_curriculos():
#     print("Recebendo requisição POST para /analisar_curriculos")
#     data = request.get_json()
#     print(f"Dados recebidos: {data}")
#     vaga_id = data.get('vaga_id')
#     conn = get_db_connection()
#     cursor = conn.cursor(dictionary=True)

#     # Busca requisitos da vaga
#     cursor.execute("SELECT requisitos FROM vagas WHERE id = %s", (vaga_id,))
#     vaga = cursor.fetchone()
#     if not vaga:
#         cursor.close()
#         conn.close()
#         print(f"Vaga ID {vaga_id} não encontrada")
#         return jsonify({'error': 'Vaga não encontrada'}), 404

#     requisitos = vaga['requisitos']
#     print(f"Requisitos da vaga: {requisitos}")

#     # Busca todos os currículos
#     cursor.execute("SELECT id, nome, conteudo FROM curriculos")
#     curriculos = cursor.fetchall()
#     print(f"Currículos encontrados: {len(curriculos)}")

#     # Inicializa o modelo Groq
#     llm = ChatGroq(
#         model="llama3-70b-8192",
#         temperature=0.2,
#         max_retries=2
#     )

#     # Define o parser para garantir saída JSON
#     parser = JsonOutputParser()

#     # Prompt para análise
#     prompt = ChatPromptTemplate.from_messages([
#         ("system", """Você é um especialista em RH. Analise o currículo fornecido e calcule uma pontuação de compatibilidade (0 a 100) com base nos requisitos da vaga. Retorne apenas um JSON com a estrutura: {{ "id": id_curriculo, "nome": nome_curriculo, "pontuacao": pontuacao }}.
#         Currículo: {curriculo}
#         Requisitos da vaga: {requisitos}"""),
#         ("human", "Analise o currículo e retorne a pontuação.")
#     ])

#     # Cria a cadeia LangChain
#     chain = prompt | llm | parser

#     resultados = []
#     for curriculo in curriculos:
#         try:
#             resultado = chain.invoke({
#                 "curriculo": curriculo['conteudo'],
#                 "requisitos": requisitos
#             })
#             resultados.append({
#                 "id": curriculo['id'],
#                 "nome": curriculo['nome'],
#                 "pontuacao": resultado.get('pontuacao', 0)
#             })
#             print(f"Análise do currículo {curriculo['nome']}: {resultado}")
#         except Exception as e:
#             print(f"Erro ao analisar currículo {curriculo['nome']}: {e}")

#     # Ordena por pontuação e limita a 10
#     resultados = sorted(
#         resultados, key=lambda x: x['pontuacao'], reverse=True)[:10]
#     print(f"Resultados finais: {resultados}")

#     cursor.close()
#     conn.close()
#     return jsonify(resultados)


# if __name__ == '__main__':
#     print("Iniciando o servidor Flask...")
#     app.run(debug=True, host='0.0.0.0', port=5000)

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
import mysql.connector
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import os
from dotenv import load_dotenv
from datetime import datetime
import pandas as pd
from io import BytesIO

# Carrega variáveis do arquivo .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

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
# Substituído por LLaMA3-70b-8192
llm = ChatGroq(model="llama3-70b-8192", api_key=groq_api_key)

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

# Decorador para proteger rotas


def login_required(f):
    def wrap(*args, **kwargs):
        print(f"Verificando sessão: {session}")
        if 'user' not in session:
            print("Usuário não autenticado. Redirecionando para login.")
            return redirect(url_for('login_page'))
        print(f"Usuário autenticado: {session['user']}")
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

# Rotas do sistema


@app.route('/login', methods=['GET'])
def login_page():
    print(f"Verificando sessão na rota /login (GET): {session}")
    if 'user' in session:
        print("Usuário já autenticado. Redirecionando para index.")
        return redirect(url_for('index'))
    print("Renderizando página de login.")
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    print("Recebendo requisição POST para /login")
    data = request.get_json()
    print(f"Dados recebidos: {data}")
    matricula = data.get('matricula')
    senha = data.get('senha')

    if not matricula or not senha:
        print("Matrícula ou senha não fornecidos.")
        return jsonify({'success': False, 'message': 'Matrícula e senha são obrigatórios'}), 400

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
            print(f"Login bem-sucedido para matrícula {matricula}.")
            session['user'] = {
                'matricula': user['matricula'], 'nome': user['nome']}
            print(f"Sessão atualizada: {session}")
            return jsonify({'success': True, 'redirect': url_for('index')})
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


@app.route('/logout', methods=['GET'])
@login_required
def logout():
    print("Executando logout")
    session.pop('user', None)
    print("Usuário deslogado. Redirecionando para login.")
    return redirect(url_for('login_page'))


@app.route('/')
@login_required
def index():
    print("Acessando rota / (index)")
    return render_template('index.html')


@app.route('/relatorio', methods=['GET'])
@login_required
def relatorio_page():
    print("Acessando rota /relatorio")
    return render_template('relatorio.html')


@app.route('/produto/<codigo>', methods=['GET'])
@login_required
def get_produto(codigo):
    print(f"Recebendo requisição GET para /produto/{codigo}")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        print(f"Buscando produto com código: {codigo}")
        cur.execute(
            'SELECT * FROM produtos WHERE codigo = %s OR barras = %s',
            (codigo, codigo)
        )
        produto = cur.fetchone()
        if not produto:
            print(
                f"Produto não encontrado. Inserindo novo produto com código: {codigo}")
            cur.execute(
                'INSERT INTO produtos (codigo, barras, descricao, saldo_atual) VALUES (%s, %s, %s, %s)',
                (codigo, None, 'Produto Exemplo - Descrição Padrão', 10)
            )
            conn.commit()
            cur.execute(
                'SELECT * FROM produtos WHERE codigo = %s',
                (codigo,)
            )
            produto = cur.fetchone()
        print(f"Produto encontrado: {produto}")
        print(
            f"Descrição do produto: {produto.get('descricao', 'Descrição não encontrada')}")
        cur.close()
        conn.close()
        return jsonify(produto)
    except Exception as e:
        cur.close()
        conn.close()
        print(f"Erro ao buscar produto: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/ajustar-estoque', methods=['POST'])
@login_required
def ajustar_estoque():
    print("Recebendo requisição POST para /ajustar-estoque")
    data = request.get_json()
    print(f"Dados recebidos do frontend: {data}")

    if not data or 'ajustes' not in data:
        print("Erro: Lista de ajustes não fornecida.")
        return jsonify({'error': 'Lista de ajustes é obrigatória'}), 400

    ajustes = data['ajustes']
    if not isinstance(ajustes, list) or not ajustes:
        print("Erro: Lista de ajustes inválida ou vazia.")
        return jsonify({'error': 'A lista de ajustes deve ser uma lista não vazia'}), 400

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # Verifica a sessão
        print(f"Sessão atual: {session}")
        if 'user' not in session or 'matricula' not in session['user'] or 'nome' not in session['user']:
            print("Erro: Sessão inválida. Usuário não autenticado.")
            return jsonify({'error': 'Sessão inválida. Faça login novamente.'}), 401

        matricula = session['user']['matricula']
        nome_usuario = session['user']['nome']
        print(f"Matricula: {matricula}, Nome do usuário: {nome_usuario}")

        # Inicia uma transação
        conn.start_transaction()
        print("Transação iniciada.")

        # Obtém o próximo numero_ajuste
        cur.execute(
            'SELECT COALESCE(MAX(numero_ajuste), 0) + 1 as next_numero_ajuste FROM ajustes')
        numero_ajuste = cur.fetchone()['next_numero_ajuste']
        print(f"Número do ajuste gerado: {numero_ajuste}")

        resultados = []
        for ajuste in ajustes:
            codigo = ajuste.get('codigo')
            if not codigo:
                print(
                    f"Erro: Código do produto não fornecido no ajuste: {ajuste}")
                return jsonify({'error': 'Código do produto é obrigatório para todos os ajustes'}), 400

            try:
                quantidade = int(ajuste['quantidade'])
                print(f"Ajuste para código {codigo}, quantidade: {quantidade}")
            except (ValueError, KeyError) as ve:
                print(
                    f"Erro: Valor de ajuste inválido para código {codigo}: {ajuste.get('quantidade')}")
                return jsonify({'error': f'O valor de ajuste para o código {codigo} deve ser um número inteiro'}), 400

            # Busca o produto
            print(f"Buscando produto com código: {codigo}")
            cur.execute(
                'SELECT * FROM produtos WHERE codigo = %s OR barras = %s',
                (codigo, codigo)
            )
            produto = cur.fetchone()
            if not produto:
                print(f"Produto não encontrado para o código: {codigo}")
                return jsonify({'error': f'Produto com código {codigo} não encontrado'}), 404

            codigo_produto = produto['codigo']
            descricao = ajuste.get(
                'descricao', produto['descricao'] if produto['descricao'] is not None else "Descrição não disponível")
            print(
                f"Código do produto: {codigo_produto}, Descrição: {descricao}")

            # Atualiza o saldo_atual na tabela produtos
            print(
                f"Executando UPDATE: saldo_atual = saldo_atual + {quantidade} WHERE codigo = {codigo_produto}")
            cur.execute(
                'UPDATE produtos SET saldo_atual = saldo_atual + %s WHERE codigo = %s',
                (quantidade, codigo_produto)
            )
            print(f"Linhas afetadas pelo UPDATE: {cur.rowcount}")
            if cur.rowcount == 0:
                print("Nenhuma linha afetada pelo UPDATE. Produto não encontrado.")
                return jsonify({'error': f'Produto com código {codigo} não encontrado'}), 404

            # Insere o registro na tabela ajustes com o mesmo numero_ajuste
            print(
                f"Inserindo no ajustes: numero_ajuste = {numero_ajuste}, codigo_produto = {codigo_produto}, quantidade = {quantidade}, matricula = {matricula}, nome_usuario = {nome_usuario}, descricao = {descricao}")
            cur.execute(
                'INSERT INTO ajustes (numero_ajuste, codigo_produto, quantidade, data, matricula, nome_usuario, descricao, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                (numero_ajuste, codigo_produto, quantidade, datetime.now(),
                 matricula, nome_usuario, descricao, 'PENDENTE')
            )
            print(f"Linhas afetadas pelo INSERT: {cur.rowcount}")

            resultados.append({
                'codigo': codigo_produto,
                'saldo_atual': produto['saldo_atual'] + quantidade
            })

        # Confirma a transação
        conn.commit()
        print("Transação commitada com sucesso.")

        # Verifica se os dados foram realmente inseridos
        cur.execute(
            'SELECT * FROM ajustes WHERE numero_ajuste = %s', (numero_ajuste,))
        ajustes_inseridos = cur.fetchall()
        print(f"Ajustes inseridos no banco: {ajustes_inseridos}")

        cur.close()
        conn.close()
        return jsonify({'success': True, 'numero_ajuste': numero_ajuste, 'resultados': resultados})
    except mysql.connector.Error as db_err:
        conn.rollback()
        print(f"Erro no banco de dados ao ajustar estoque: {db_err}")
        return jsonify({'error': f'Erro no banco de dados: {str(db_err)}'}), 500
    except Exception as e:
        conn.rollback()
        print(f"Erro ao ajustar estoque: {e}")
        return jsonify({'error': f'Erro ao ajustar estoque: {str(e)}'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


@app.route('/liberar-ajustes', methods=['GET'])
@login_required
def liberar_ajustes_page():
    print("Acessando rota /liberar-ajustes")
    return render_template('liberar_ajustes.html')


@app.route('/ajustes-pendentes', methods=['GET'])
@login_required
def get_ajustes_pendentes():
    print("Recebendo requisição GET para /ajustes-pendentes")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute('''
            SELECT DISTINCT numero_ajuste, data, matricula, nome_usuario
            FROM ajustes
            WHERE status = 'PENDENTE'
            ORDER BY numero_ajuste DESC
        ''')
        ajustes = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify([{
            'numero_ajuste': item['numero_ajuste'],
            'data_hora': item['data'].strftime('%d/%m/%Y - %H:%M'),
            'matricula': item['matricula'],
            'nome_usuario': item['nome_usuario']
        } for item in ajustes])
    except Exception as e:
        cur.close()
        conn.close()
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
            SELECT DISTINCT numero_ajuste, data, matricula, nome_usuario, usuario_liberou
            FROM ajustes
            WHERE status = 'LIBERADO'
            ORDER BY numero_ajuste DESC
        ''')
        ajustes = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify([{
            'numero_ajuste': ajuste['numero_ajuste'],
            'data_hora': ajuste['data'].strftime('%d/%m/%Y - %H:%M'),
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
            'Quantidade': item['quantidade'],
            'Custo Unitário (R$)': float(str(item['custo']).replace(',', '.')) if item['custo'] is not None else 0.0,
            'Custo Total (R$)': (float(str(item['custo']).replace(',', '.')) if item['custo'] is not None else 0.0) * abs(item['quantidade']),
            'Data/Hora': item['data'].strftime('%d/%m/%Y - %H:%M'),
            'Matrícula': item['matricula'],
            'Nome do Usuário': item['nome_usuario']
        } for item in ajustes]

        total_custo = sum(item['Custo Total (R$)'] for item in data)
        data.append({
            'Número do Ajuste': '',
            'Código do Produto': '',
            'Descrição': 'Total Custo',
            'Quantidade': '',
            'Custo Unitário (R$)': '',
            'Custo Total (R$)': total_custo,
            'Data/Hora': '',
            'Matrícula': '',
            'Nome do Usuário': ''
        })

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
    try:
        print("Acessando rota /buscar-candidatos")  # Log para depuração
        nome = request.args.get('nome', '').strip()
        vaga_id = request.args.get('vaga_id', '')

        # Log para depuração
        print(f"Parâmetros recebidos: nome={nome}, vaga_id={vaga_id}")

        if not vaga_id:
            print("Erro: Vaga não fornecida")
            return jsonify({'error': 'Vaga é obrigatória'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Buscar os requisitos da vaga (apenas para uso futuro na análise)
        cursor.execute(
            "SELECT requisitos FROM vagas WHERE id = %s", (vaga_id,))
        vaga = cursor.fetchone()
        if not vaga:
            cursor.close()
            conn.close()
            print("Erro: Vaga não encontrada")
            return jsonify({'error': 'Vaga não encontrada'}), 404

        requisitos = vaga['requisitos'].split(
            ', ') if vaga['requisitos'] else []
        print(f"Requisitos da vaga: {requisitos}")  # Log para depuração

        # Buscar todos os candidatos
        query = "SELECT id, nome, conteudo FROM curriculos"
        params = []

        if nome:
            query += " WHERE nome LIKE %s"
            params.append(f'%{nome}%')

        print(f"Query a ser executada: {query}")  # Log para depuração
        print(f"Parâmetros: {params}")  # Log para depuração

        cursor.execute(query, params)
        candidatos = cursor.fetchall()
        print(f"Candidatos encontrados: {candidatos}")  # Log para depuração

        # Não filtrar por requisitos na busca, apenas listar todos os candidatos
        candidatos_filtrados = []
        for candidato in candidatos:
            candidatos_filtrados.append({
                'id': candidato['id'],
                'nome': candidato['nome'],
                'habilidades': candidato['conteudo'] if candidato['conteudo'] else 'N/A'
            })

        # Log para depuração
        print(f"Candidatos filtrados: {candidatos_filtrados}")

        cursor.close()
        conn.close()

        return jsonify(candidatos_filtrados), 200
    except mysql.connector.Error as e:
        # Log para depuração
        print(f"Erro ao buscar candidatos (MySQL): {str(e)}")
        return jsonify({'error': f'Erro ao buscar candidatos: {str(e)}'}), 500
    except Exception as e:
        # Log para depuração
        print(f"Erro inesperado ao buscar candidatos: {str(e)}")
        return jsonify({'error': f'Erro inesperado ao buscar candidatos: {str(e)}'}), 500


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

# Rota para sugerir detalhes da vaga (usando apenas Grok)


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


if __name__ == '__main__':
    print("Iniciando o servidor Flask...")
    app.run(debug=True, host='0.0.0.0', port=5000)
