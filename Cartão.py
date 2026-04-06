import streamlit as st
import pandas as pd
from io import BytesIO
import datetime
import re
import locale

try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    locale.setlocale(locale.LC_ALL, '')
import json
import os
import gspread
from google.oauth2.service_account import Credentials

# NOVO: Isso força o app a usar as margens laterais da tela inteira!
st.set_page_config(page_title="Conciliação de Cartão", layout="wide")

# --- TRADUÇÃO FORÇADA DOS BOTÕES DO STREAMLIT ---
st.markdown("""
    <style>
        /* 1. Esconde o "Drag and drop..." e escreve em português */
        [data-testid="stFileUploadDropzone"] > div > div > span {
            display: none !important;
        }
        [data-testid="stFileUploadDropzone"] > div > div::before {
            content: "Arraste e solte o arquivo aqui";
            font-size: 16px;
            color: rgba(49, 51, 63, 0.8);
            display: block;
            margin-bottom: 5px;
        }
        
        /* 2. Esconde o limite de tamanho e escreve em português */
        [data-testid="stFileUploadDropzone"] > div > div > small {
            display: none !important;
        }
        [data-testid="stFileUploadDropzone"] > div > div::after {
            content: "Limite de 200MB por arquivo • Excel ou CSV";
            font-size: 13px;
            color: rgba(49, 51, 63, 0.5);
            display: block;
        }
        
        /* 3. Hack para o botão "Browse files" */
        [data-testid="stFileUploadDropzone"] button {
            color: transparent !important;
        }
        [data-testid="stFileUploadDropzone"] button::after {
            content: "Procurar arquivos";
            color: #31333F;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 14px;
            font-weight: 500;
        }
    </style>
""", unsafe_allow_html=True)
# ------------------------------------------------

# --- CONEXÃO COM O GOOGLE SHEETS ---
# Coloque o arquivo JSON do Google na mesma pasta e renomeie exatamente para: credenciais.json
NOME_PLANILHA = "Banco_Conciliacao"

def conectar_google_sheets():
    try:
        escopos = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credenciais = Credentials.from_service_account_file("credenciais.json", scopes=escopos)
        cliente = gspread.authorize(credenciais)
        return cliente.open(NOME_PLANILHA)
    except FileNotFoundError:
        st.error("🚨 Arquivo 'credenciais.json' não encontrado! Coloque-o na mesma pasta do seu aplicativo.")
        st.stop()
    except Exception as e:
        st.error(f"🚨 Erro ao conectar no Google Sheets: {e}")
        st.stop()

def salvar_dados_permanentes():
    planilha = conectar_google_sheets()
    
    # Salva Fornecedores
    aba_forn = planilha.worksheet("Fornecedores")
    aba_forn.clear()
    if st.session_state.lista_forn:
        aba_forn.update(values=[[i] for i in st.session_state.lista_forn], range_name="A1")
        
    # Salva CC
    aba_cc = planilha.worksheet("Centros_Custo")
    aba_cc.clear()
    if st.session_state.lista_cc:
        aba_cc.update(values=[[i] for i in st.session_state.lista_cc], range_name="A1")
        
    # Salva Contas
    aba_contas = planilha.worksheet("Contas_Financeiras")
    aba_contas.clear()
    if st.session_state.lista_contas:
        aba_contas.update(values=[[i] for i in st.session_state.lista_contas], range_name="A1")

def salvar_fatura_no_disco():
    # Agora salva na NUVEM!
    planilha = conectar_google_sheets()
    aba_fatura = planilha.worksheet("Fatura")
    aba_fatura.clear()
    
    if not st.session_state.df_conciliacao.empty:
        df_para_salvar = st.session_state.df_conciliacao.copy()
        # Transforma tudo em texto puro para o Google não bugar
        df_para_salvar = df_para_salvar.astype(str) 
        dados = [df_para_salvar.columns.values.tolist()] + df_para_salvar.values.tolist()
        aba_fatura.update(values=dados, range_name="A1")

def carregar_tudo():
    try:
        planilha = conectar_google_sheets()
        
        # Carrega listas (ignora linhas vazias)
        st.session_state.lista_forn = [col[0] for col in planilha.worksheet("Fornecedores").get_all_values() if col]
        st.session_state.lista_cc = [col[0] for col in planilha.worksheet("Centros_Custo").get_all_values() if col]
        st.session_state.lista_contas = [col[0] for col in planilha.worksheet("Contas_Financeiras").get_all_values() if col]
        
        # Carrega a fatura
        dados_fatura = planilha.worksheet("Fatura").get_all_values()
        if len(dados_fatura) > 1: # Se tiver dados além do cabeçalho
            st.session_state.df_conciliacao = pd.DataFrame(dados_fatura[1:], columns=dados_fatura[0])
            # Converte o valor de volta para número para não quebrar a soma dos totais
            if 'Valor' in st.session_state.df_conciliacao.columns:
                st.session_state.df_conciliacao['Valor'] = pd.to_numeric(st.session_state.df_conciliacao['Valor'], errors='coerce').fillna(0.0)
        else:
            st.session_state.df_conciliacao = pd.DataFrame()
            
    except Exception as e:
        st.error(f"⚠️ Não foi possível carregar os dados. Erro: {e}")

# --- INICIALIZAÇÃO DA MEMÓRIA ---
if 'lista_forn' not in st.session_state: st.session_state.lista_forn = []
if 'lista_cc' not in st.session_state: st.session_state.lista_cc = []
if 'lista_contas' not in st.session_state: st.session_state.lista_contas = []
if 'df_conciliacao' not in st.session_state: st.session_state.df_conciliacao = pd.DataFrame()
if 'fornecedor_global' not in st.session_state: st.session_state.fornecedor_global = ""

carregar_tudo()

# --- SISTEMA DE LOGIN NA BARRA LATERAL ---
SENHAS_VALIDAS = {
    "Admin": "admin123",
    "Gleider": "gleider123",
    "Lilian": "lilian123"
}

with st.sidebar:
    st.title("🔐 Login de Acesso")
    perfil = st.selectbox("Quem está acessando?", ["Admin", "Gleider", "Lilian"])
    senha = st.text_input("Senha", type="password")
    
    # Trava de Segurança
    if senha != SENHAS_VALIDAS[perfil]:
        if senha != "": st.error("❌ Senha incorreta!")
        st.warning("⚠️ Digite a senha para liberar o sistema.")
        st.stop() # Para o aplicativo aqui
    else:
        st.success(f"✅ Bem-vindo(a), {perfil}!")

# --- ABAS DE NAVEGAÇÃO ---
if perfil == "Admin":
    aba1, aba2, aba3 = st.tabs(["📂 1. Importar Arquivos", "⚙️ 2. Mesa de Conciliação", "💾 3. Exportar Dados"])
else:
    aba2, = st.tabs(["⚙️ Mesa de Conciliação"])
    aba1 = st.empty() # Aba fantasma invisível
    aba3 = st.empty() # Aba fantasma invisível

# ==========================================
# ABA 1: IMPORTAÇÃO
# ==========================================
with aba1:
    if perfil == "Admin":
        st.subheader("Upload de Arquivos")
        
        # NOVO: Botão de Resetar o Sistema
        if st.button("🗑️ Limpar Todos os Dados (Iniciar Novo Mês)"):
            st.session_state.df_conciliacao = pd.DataFrame()
            st.session_state.fornecedor_global = ""
            
            # Limpa tudo no Google Sheets também
            try:
                planilha = conectar_google_sheets()
                planilha.worksheet("Fatura").clear()
            except: pass # Ignora erro se a aba já estiver vazia
            
            st.success("✅ Sistema e Nuvem zerados com sucesso! Pode subir a fatura nova.")
            st.rerun()
            
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📑 Cadastros Base (Opcionais)")
            st.info("Suba os arquivos de cadastro separadamente (Excel ou CSV).")
            file_forn = st.file_uploader("1. Fornecedores", type=['xlsx', 'csv'])
            file_cc = st.file_uploader("2. Centros de Custo", type=['xlsx', 'csv'])
            file_conta = st.file_uploader("3. Contas Financeiras", type=['xlsx', 'csv'])

        with col2:
            st.markdown("#### 💳 Fatura do Cartão")
            venc_global = st.date_input("📅 Vencimento desta Fatura", datetime.date.today(), format="DD/MM/YYYY")
            
            # NOVO: Dados para o ERP
        cod_empresa = st.text_input("🏢 Código da Empresa (Ex: 2 para Romulo)")
        cod_fornecedor = st.text_input("🏦 Código do Fornecedor (Ex: 50)")
            
        file_fatura = st.file_uploader("Upload Extrato Bradesco", type=['csv', 'xlsx', 'xls'])

        if file_fatura:
            try:
                if file_fatura.name.endswith(('.xlsx', '.xls')):
                    df_bruto = pd.read_excel(file_fatura, header=None).astype(str).values.tolist()
                else:
                    try: conteudo = file_fatura.getvalue().decode('utf-8').splitlines()
                    except: conteudo = file_fatura.getvalue().decode('latin1').splitlines()
                    sep = ',' if any(',' in l for l in conteudo[:20]) else ';'
                    df_bruto = [l.split(sep) for l in conteudo]

                if st.button("🚀 Processar Lançamentos"):
                    if not cod_empresa or not cod_fornecedor:
                        st.error("⚠️ Por favor, preencha o Código da Empresa e do Fornecedor antes de processar.")
                        st.stop()
                        
                    linhas = []
                    portador = "Desconhecido"
                    
                    for partes in df_bruto:
                        if len(partes) < 2: continue
                        p0, p1 = str(partes[0]).strip(), str(partes[1]).strip()

                        if " - " in p0 and (p1 == "" or p1 == "nan"):
                            portador = p0
                            continue
                        
                        if re.match(r'^\d{2}/\d{2}$', p0):
                            if any(x in p1.upper() for x in ["SALDO ANTERIOR", "PAGTO", "PAGAMENTO", "TOTAL PARA"]):
                                continue
                            try:
                                val_raw = partes[4].replace('"', '').strip() if len(partes) > 4 else partes[-1].replace('"', '').strip()
                                v = float(val_raw.replace('.', '').replace(',', '.'))
                                if v != 0:
                                    linhas.append({'Portador': portador, 'Hist': p1, 'Val': v})
                            except: continue

                    if not linhas:
                        st.error("Nenhum lançamento válido encontrado.")
                    else:
                        df_f = pd.DataFrame(linhas)
                        df_c = pd.DataFrame()
                        df_c['Empresa'] = cod_empresa
                        df_c['Fornecedor'] = cod_fornecedor
                        df_c['Portador'] = df_f['Portador']
                        df_c['Histórico Banco'] = df_f['Hist']
                        df_c['Estabelecimento'] = ""
                        df_c['Detalhes (Obs)'] = ""
                        
                        nomes_curtos = df_f['Portador'].apply(lambda x: str(x).split()[0][:4].upper())
                        sequencia = [f"{i:03d}" for i in range(1, len(df_f) + 1)]
                        df_c['Titulo'] = nomes_curtos + sequencia
                        
                        df_c['Conta Financeira'] = ""
                        df_c['C.Custo'] = ""
                        df_c['Valor'] = df_f['Val']
                        df_c['Vencimento'] = venc_global
                        df_c['Status'] = "Pendente ⏳" 
                                
                        # NOVO: Adiciona os novos lançamentos ao histórico existente (não apaga os antigos)
                        if not st.session_state.df_conciliacao.empty:
                            st.session_state.df_conciliacao = pd.concat([st.session_state.df_conciliacao, df_c], ignore_index=True)
                        else:
                            st.session_state.df_conciliacao = df_c
                            
                        salvar_fatura_no_disco() 
                        st.success("✅ Lançamentos adicionados à base de dados com sucesso!")
                
                def ler_arquivo_cadastro(arquivo):
                    if arquivo.name.endswith('.csv'):
                        try: df = pd.read_csv(arquivo, sep=None, engine='python', encoding='utf-8', header=None)
                        except:
                            arquivo.seek(0)
                            df = pd.read_csv(arquivo, sep=None, engine='python', encoding='latin1', header=None)
                    else:
                        df = pd.read_excel(arquivo, header=None)
                        
                    if len(df.columns) >= 2:
                        return (df.iloc[:, 0].astype(str) + " - " + df.iloc[:, 1].astype(str)).tolist()
                    return []

                if file_forn: 
                    st.session_state.lista_forn = ler_arquivo_cadastro(file_forn)
                    salvar_dados_permanentes()

                if file_cc: 
                    st.session_state.lista_cc = ler_arquivo_cadastro(file_cc)
                    salvar_dados_permanentes()

                if file_conta: 
                    st.session_state.lista_contas = ler_arquivo_cadastro(file_conta)
                    salvar_dados_permanentes()

                if not st.session_state.df_conciliacao.empty:
                    st.success("✅ Lançamentos processados com sucesso! Siga para a aba '2. Mesa de Conciliação'.")
                else:
                    st.info("👆 Arquivo carregado! Agora clique em '🚀 Processar Lançamentos' para extrair os dados.")

            except Exception as e:
                st.error(f"❌ Ocorreu um erro ao processar os arquivos. Erro: {e}")

# ==========================================
# ABA 2: MESA DE CONCILIAÇÃO
# ==========================================
with aba2:
    st.subheader("Mesa de Conciliação")
    
    if st.session_state.df_conciliacao.empty:
        if perfil == "Admin": st.info("⚠️ Aguardando você importar e processar os Lançamentos na Aba 1.")
        else: st.info("⚠️ Nenhuma fatura foi liberada pelo Admin ainda.")
    else:
        df_completo = st.session_state.df_conciliacao.copy()
        
        # --- CORREÇÃO DE ARQUIVOS ANTIGOS ---
        if 'Status' not in df_completo.columns: df_completo['Status'] = "Pendente ⏳"
        if 'Empresa' not in df_completo.columns: df_completo['Empresa'] = ""
        if 'Fornecedor' not in df_completo.columns: df_completo['Fornecedor'] = ""
        if 'Titulo' not in df_completo.columns: df_completo['Titulo'] = ""

        # >>> NOVO: ATUALIZA O STATUS AUTOMATICAMENTE (Sem exigir Estabelecimento) <<<
        mask_concluido = (df_completo['Conta Financeira'].astype(str).str.strip() != "") & \
                         (df_completo['C.Custo'].astype(str).str.strip() != "")
        df_completo.loc[mask_concluido, 'Status'] = "Concluído ✅"
        df_completo.loc[~mask_concluido, 'Status'] = "Pendente ⏳"
        
        # Filtros de Pesquisa (Histórico)
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_status = st.selectbox("📌 Filtrar por Status:", ["Pendente ⏳", "Concluído ✅", "Mostrar Todos"])
        with col_f2:
            datas_unicas = df_completo['Vencimento'].astype(str).unique().tolist()
            filtro_data = st.selectbox("📅 Filtrar por Vencimento:", ["Todas as Datas"] + datas_unicas)
            
        # Aplica os filtros escolhidos
        df_visao = df_completo.copy()
        if filtro_status != "Mostrar Todos":
            df_visao = df_visao[df_visao['Status'] == filtro_status]
        if filtro_data != "Todas as Datas":
            df_visao = df_visao[df_visao['Vencimento'].astype(str) == filtro_data]

        # Filtra pela visão do usuário logado
        if perfil == "Gleider":
            df_visao = df_visao[df_visao['Portador'].str.contains("GLEIDER", case=False, na=False)]
        elif perfil == "Lilian":
            df_visao = df_visao[df_visao['Portador'].str.contains("LILIAN", case=False, na=False)]

        st.markdown(f"**Visão Atual:** `{perfil}`")

        # NOVO: Barra de progresso interativa e aviso de salvamento
        total_linhas = len(df_visao)
        if total_linhas > 0:
            # Conta quantas linhas ainda têm algum campo em branco (Ajustado para ignorar o Estabelecimento e evitar erros de texto vazio)
            linhas_incompletas = df_visao[
                (df_visao['Conta Financeira'].astype(str).str.strip() == "") | 
                (df_visao['C.Custo'].astype(str).str.strip() == "")
            ]
            linhas_preenchidas = total_linhas - len(linhas_incompletas)
            
            # Calcula a porcentagem para a barra (de 0.0 a 1.0)
            percentual = linhas_preenchidas / total_linhas
            
            # Mostra a barra na tela
            st.progress(percentual, text=f"📊 Progresso: {linhas_preenchidas} de {total_linhas} lançamentos preenchidos.")
            
        st.markdown("<br>", unsafe_allow_html=True)
        # >>> TRUQUE: RESERVA UM ESPAÇO AQUI NO TOPO PARA O BOTÃO SALVAR <<<
        area_botao_salvar = st.empty()
        st.markdown("<br>", unsafe_allow_html=True)

        # Configura as colunas (TRAVANDO TUDO QUE VEM DO CARTÃO)
        config_colunas = {
            "Portador": st.column_config.TextColumn("Portador (Cartão)", disabled=True),
            "Histórico Banco": st.column_config.TextColumn("Histórico Original", disabled=True),
            "Valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f", disabled=True),
            "Vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY", disabled=True),
            "Status": st.column_config.TextColumn("Status", disabled=True),
            "Titulo": st.column_config.TextColumn("Título", disabled=True), # <<< AGORA ESTÁ 100% VISÍVEL E TRAVADO
            "Detalhes (Obs)": st.column_config.TextColumn("Descrição (Detalhes)"),
            
            # Colunas ocultas (Ninguém vê)
            "Estabelecimento": None,
            "Empresa": None,
            "Fornecedor": None
        }
        
        # >>> NOVO: ADICIONANDO [""] PARA PERMITIR DELETAR A SELEÇÃO <<<
        if st.session_state.lista_contas: 
            config_colunas["Conta Financeira"] = st.column_config.SelectboxColumn("Conta Financeira", options=[""] + st.session_state.lista_contas)
        else: 
            config_colunas["Conta Financeira"] = st.column_config.TextColumn("Conta Financeira")

        if st.session_state.lista_cc: 
            config_colunas["C.Custo"] = st.column_config.SelectboxColumn("C.Custo", options=[""] + st.session_state.lista_cc)
        else: 
            config_colunas["C.Custo"] = st.column_config.TextColumn("C.Custo")

        # Exibe a tabela filtrada
        df_editado = st.data_editor(
            df_visao,
            column_config=config_colunas,
            num_rows="fixed", # Impede adicionar linhas
            hide_index=True,  # Impede selecionar a linha inteira para deletar
            use_container_width=True,
            height=500,
            key="tabela_oficial_conciliacao" # CHAVE ESTÁTICA PARA NÃO PERDER O FOCO
        )
        
        # >>> BOTÃO RENDERIZADO NO TOPO (Usando o espaço vazio criado no Passo 1) <<<
        
        # --- FUNÇÃO DE SALVAR EXTRAÍDA PARA REUSO E PREVENÇÃO DE BUGS ---
        def processar_salvamento(encerrar_fatura=False):
            # 1. Limpeza Pesada: Pega a edição da tela e joga pro banco oficial
            for col in ['Conta Financeira', 'C.Custo', 'Detalhes (Obs)']:
                valores_limpos = df_editado[col].fillna("").astype(str).str.strip()
                valores_limpos = valores_limpos.replace(["None", "nan", "<NA>", "NaN"], "")
                df_completo.loc[df_editado.index, col] = valores_limpos
            
            # 2. Recalcula o Status
            col_conta = df_completo['Conta Financeira'].astype(str).str.strip().replace(["None", "nan"], "")
            col_ccusto = df_completo['C.Custo'].astype(str).str.strip().replace(["None", "nan"], "")
            mask_concluido = (col_conta != "") & (col_ccusto != "")
            
            df_completo.loc[mask_concluido, 'Status'] = "Concluído ✅"
            df_completo.loc[~mask_concluido, 'Status'] = "Pendente ⏳"

            if encerrar_fatura:
                df_completo.loc[df_editado.index, 'Status'] = "Concluído ✅"

            # 3. Salva no disco
            st.session_state.df_conciliacao = df_completo
            salvar_fatura_no_disco()

        if area_botao_salvar.button("💾 SALVAR ALTERAÇÕES DA TABELA (Aperte Enter nas células antes)", type="primary", use_container_width=True):
            processar_salvamento()
            st.rerun()
        
        st.markdown("---")
        col_tot1, col_tot2 = st.columns([2, 1])
        with col_tot1:
            resumo_portador = df_editado.groupby('Portador')['Valor'].sum().reset_index()
            resumo_portador.columns = ['Cartão Adicional', 'Total Gasto (R$)']
            st.dataframe(resumo_portador, hide_index=True, width="stretch")
        with col_tot2:
            total_geral = df_editado['Valor'].sum()
            st.metric(label="💰 TOTAL DA VISÃO ATUAL", value=f"R$ {total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        st.markdown("---")
        # Botão para o usuário encerrar a fatura dele e fazer o Download
        if perfil != "Admin":
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                st.markdown("🔒 **Finalizar Lançamentos:**")
                if st.button(f"✅ Encerrar Minha Fatura ({perfil})", use_container_width=True):
                    processar_salvamento(encerrar_fatura=False) # Força salvar antes de checar pra não perder dados!
                    faltam_agora = df_completo.loc[df_editado.index]
                    faltam_agora = faltam_agora[(faltam_agora['Conta Financeira'] == "") | (faltam_agora['C.Custo'] == "")]
                    
                    if not faltam_agora.empty:
                        st.error(f"❌ Você ainda tem {len(faltam_agora)} linha(s) com campos em branco. Preencha tudo!")
                    else:
                        processar_salvamento(encerrar_fatura=True)
                        st.success("🎉 Fatura encerrada com sucesso! O Admin já pode exportar.")
                        st.rerun()
            
            with col_btn2:
                # --- EXPORTAÇÕES DO USUÁRIO ---
                st.markdown("⬇️ **Baixar Relatórios (Para enviar):**")
                
                # Prepara o CSV com códigos limpos e colunas escondidas forçadas
                df_exp_user = df_editado.copy()
                df_exp_user['Conta Financeira'] = df_exp_user['Conta Financeira'].astype(str).apply(lambda x: str(x).split(' - ')[0].strip() if ' - ' in str(x) else x)
                df_exp_user['C.Custo'] = df_exp_user['C.Custo'].astype(str).apply(lambda x: str(x).split(' - ')[0].strip() if ' - ' in str(x) else x)
                
                for c in ['Empresa', 'Fornecedor', 'Titulo']:
                    if c not in df_exp_user.columns: 
                        df_exp_user[c] = df_completo.loc[df_editado.index, c] if c in df_completo.columns else ""

                df_exp_user['Observação'] = df_exp_user.apply(lambda row: f"{row['Histórico Banco']} - {row['Detalhes (Obs)']} | Cartão Crédito: {row['Portador']}" if str(row['Detalhes (Obs)']).strip() != "" else f"{row['Histórico Banco']} | Cartão Crédito: {row['Portador']}", axis=1)
                df_exp_user['Valor'] = df_exp_user['Valor'].apply(lambda x: f"{float(x):.2f}")
                df_exp_user['Vencimento'] = pd.to_datetime(df_exp_user['Vencimento']).dt.strftime('%d/%m/%Y')
                
                colunas_senior = ['Empresa', 'Fornecedor', 'Titulo', 'Observação', 'Valor', 'Conta Financeira', 'C.Custo', 'Vencimento']
                df_exp_user = df_exp_user[colunas_senior]
                
                csv_buffer = BytesIO()
                df_exp_user.to_csv(csv_buffer, index=False, sep=';', encoding='utf-8-sig')
                
                st.download_button("📊 1. Baixar Arquivo CSV", data=csv_buffer.getvalue(), file_name=f"fatura_ERP_{perfil}_{datetime.datetime.now().strftime('%d%m%Y')}.csv", mime="text/csv", use_container_width=True)

                # Prepara o Relatório em HTML pronto para virar PDF
                html_linhas = ""
                for idx, row in df_editado.iterrows():
                    html_linhas += f"<tr><td style='border: 1px solid #ddd; padding: 8px;'>{row['Vencimento']}</td><td style='border: 1px solid #ddd; padding: 8px;'>{row['Histórico Banco']}</td><td style='border: 1px solid #ddd; padding: 8px;'>{row['Conta Financeira']} / {row['C.Custo']}</td><td style='border: 1px solid #ddd; padding: 8px;'>{row['Detalhes (Obs)']}</td><td style='border: 1px solid #ddd; padding: 8px;'>R$ {float(row['Valor']):,.2f}</td></tr>"
                html_relatorio = f"<html><head><meta charset='utf-8'></head><body style='font-family: Arial, sans-serif; padding: 20px;'><h2 style='color: #2c3e50;'>Relatório de Conciliação - Cartão {perfil}</h2><table style='width: 100%; border-collapse: collapse; margin-top: 20px;'><tr style='background-color: #f2f2f2;'><th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Data</th><th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Histórico</th><th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Conta / C.Custo</th><th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Detalhes</th><th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Valor</th></tr>{html_linhas}</table><h3 style='text-align: right; margin-top: 20px;'>Total: R$ {total_geral:,.2f}</h3><script>window.print();</script></body></html>"
                
                st.download_button("📄 2. Baixar Fatura (PDF / Leitura)", data=html_relatorio, file_name=f"Relatorio_{perfil}_{datetime.datetime.now().strftime('%d%m%Y')}.html", mime="text/html", use_container_width=True)

# ==========================================
# ABA 3: EXPORTAÇÃO (APENAS ADMIN)
# ==========================================
with aba3:
    if perfil != "Admin":
        pass # Não desenha nada na tela dos usuários
    else:
        st.subheader("Exportação para o ERP Senior")
        
        if st.session_state.df_conciliacao.empty:
             st.info("⚠️ Aguardando processamento e conciliação dos dados.")
        else:
            # Filtros para o Admin baixar separado
            filtro_export = st.radio("Selecione o relatório para baixar:", ["Todos Juntos", "Apenas Gleider", "Apenas Lilian"], horizontal=True)
            
            df_final = st.session_state.df_conciliacao.copy()
            
            if filtro_export == "Apenas Gleider":
                df_final = df_final[df_final['Portador'].str.contains("GLEIDER", case=False, na=False)]
            elif filtro_export == "Apenas Lilian":
                df_final = df_final[df_final['Portador'].str.contains("LILIAN", case=False, na=False)]
            
            if df_final.empty:
                st.error(f"Nenhum lançamento encontrado para a opção: {filtro_export}")
            else:
                faltam_dados = df_final[(df_final['Conta Financeira'] == "") | (df_final['C.Custo'] == "")]
                
                if not faltam_dados.empty:
                    st.error(f"🛑 BLOQUEADO: Existem {len(faltam_dados)} linhas com Conta, C.Custo ou Estabelecimento em branco na visualização '{filtro_export}'. Corrija na Aba 2 antes de baixar.")
                else:
                    st.success("✅ Tudo preenchido corretamente! Layout validado e pronto para o Senior.")

                    df_exportacao = df_final.copy()
                    
                    # Remove as descrições da Conta e C.Custo (Deixa apenas o código numérico antes do hífen)
                    df_exportacao['Conta Financeira'] = df_exportacao['Conta Financeira'].astype(str).apply(lambda x: str(x).split(' - ')[0].strip() if ' - ' in str(x) else x)
                    df_exportacao['C.Custo'] = df_exportacao['C.Custo'].astype(str).apply(lambda x: str(x).split(' - ')[0].strip() if ' - ' in str(x) else x)

                    # Concatenação Nova Padrão: HISTORICO - DETALHES | Cartão Crédito: PORTADOR
                    df_exportacao['Observação'] = df_exportacao.apply(
                        lambda row: f"{row['Histórico Banco']} - {row['Detalhes (Obs)']} | Cartão Crédito: {row['Portador']}" 
                        if str(row['Detalhes (Obs)']).strip() != "" 
                        else f"{row['Histórico Banco']} | Cartão Crédito: {row['Portador']}", 
                        axis=1
                    )
                    
                    # Formata Valor com Ponto (Ex: 1400.00)
                    df_exportacao['Valor'] = df_exportacao['Valor'].apply(lambda x: f"{float(x):.2f}")
                    
                    # Formata Data para DD/MM/YYYY
                    df_exportacao['Vencimento'] = pd.to_datetime(df_exportacao['Vencimento']).dt.strftime('%d/%m/%Y')
                    
                    # FORÇA RECUPERAR EMPRESA, FORNECEDOR E TÍTULO (Evita que venham em branco)
                    for col_fixa in ['Empresa', 'Fornecedor', 'Titulo']:
                        if col_fixa not in df_exportacao.columns:
                            df_exportacao[col_fixa] = df_final[col_fixa] if col_fixa in df_final.columns else ""

                    # Define as colunas exatas da imagem
                    colunas_senior = ['Empresa', 'Fornecedor', 'Titulo', 'Observação', 'Valor', 'Conta Financeira', 'C.Custo', 'Vencimento']
                    df_exportacao = df_exportacao[colunas_senior]

                    def convert_df_to_csv(df):
                        csv_buffer = BytesIO()
                        # Mantendo o separador ponto e vírgula, mas o Valor já vai travado com Ponto.
                        df.to_csv(csv_buffer, index=False, sep=';', encoding='utf-8-sig')
                        return csv_buffer.getvalue()

                    st.download_button(
                        label=f"💾 BAIXAR ARQUIVO ({filtro_export.upper()})",
                        data=convert_df_to_csv(df_exportacao),
                        file_name=f"importacao_senior_{filtro_export.replace(' ', '_').lower()}_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        type="primary",
                        icon="💾"
                    )