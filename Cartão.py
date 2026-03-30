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

# --- ARQUIVOS PARA SALVAR NO COMPUTADOR ---
DB_FILE = "cadastros_base.json"
FATURA_FILE = "fatura_dados.pkl" # Formato super seguro para salvar planilhas do Pandas
META_FILE = "fatura_meta.json"

def salvar_dados_permanentes():
    dados = {
        "forn": st.session_state.lista_forn,
        "cc": st.session_state.lista_cc,
        "contas": st.session_state.lista_contas
    }
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False)

def salvar_fatura_no_disco():
    # Salva a tabela
    if not st.session_state.df_conciliacao.empty:
        st.session_state.df_conciliacao.to_pickle(FATURA_FILE)
    # Salva o fornecedor fixo
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump({"fornecedor_global": st.session_state.fornecedor_global}, f, ensure_ascii=False)

def carregar_tudo():
    # Carrega cadastros
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
            st.session_state.lista_forn = dados.get("forn", [])
            st.session_state.lista_cc = dados.get("cc", [])
            st.session_state.lista_contas = dados.get("contas", [])
    
    # Carrega fatura salva
    if os.path.exists(FATURA_FILE):
        st.session_state.df_conciliacao = pd.read_pickle(FATURA_FILE)
    if os.path.exists(META_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
            st.session_state.fornecedor_global = meta.get("fornecedor_global", "")

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
aba1, aba2, aba3 = st.tabs(["📂 1. Importar Arquivos", "⚙️ 2. Mesa de Conciliação", "💾 3. Exportar Dados"])

# ==========================================
# ABA 1: IMPORTAÇÃO
# ==========================================
with aba1:
    if perfil != "Admin":
        st.error("🚫 Acesso restrito! Apenas o 'Admin' pode importar arquivos.")
    else:
        st.subheader("Upload de Arquivos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📑 Cadastros Base (Opcionais)")
        st.info("Suba os arquivos de cadastro separadamente (Excel ou CSV).")
        file_forn = st.file_uploader("1. Fornecedores", type=['xlsx', 'csv'])
        file_cc = st.file_uploader("2. Centros de Custo", type=['xlsx', 'csv'])
        file_conta = st.file_uploader("3. Contas Financeiras", type=['xlsx', 'csv'])

    with col2:
        st.markdown("#### 💳 Fatura do Cartão")
        # Força o formato brasileiro na caixinha de data
        venc_global = st.date_input("📅 Vencimento desta Fatura", datetime.date.today(), format="DD/MM/YYYY")
        
        # NOVO: Pergunta o Fornecedor Fixo do Cartão
        if st.session_state.lista_forn:
            forn_cartao = st.selectbox("🏦 Fornecedor Fixo do Cartão (Vai para o ERP)", options=["Selecione..."] + st.session_state.lista_forn)
        else:
            forn_cartao = st.text_input("🏦 Fornecedor Fixo do Cartão (Vai para o ERP)")
            
        file_fatura = st.file_uploader("Upload Extrato Bradesco", type=['csv', 'xlsx', 'xls'])

if file_fatura:
    try:
        # 1. Lê os dados e transforma tudo em lista (suporta .xlsx, .xls e .csv)
        if file_fatura.name.endswith(('.xlsx', '.xls')):
            df_bruto = pd.read_excel(file_fatura, header=None).astype(str).values.tolist()
        else:
            try: conteudo = file_fatura.getvalue().decode('utf-8').splitlines()
            except: conteudo = file_fatura.getvalue().decode('latin1').splitlines()
            sep = ',' if any(',' in l for l in conteudo[:20]) else ';'
            df_bruto = [l.split(sep) for l in conteudo]

        # 2. Processa os Lançamentos pelo Limpador Inteligente
        if st.button("🚀 Processar Lançamentos"):
            if not forn_cartao or forn_cartao == "Selecione...":
                st.error("⚠️ Por favor, informe o 'Fornecedor Fixo do Cartão' antes de processar.")
                st.stop() # Para a execução aqui se estiver em branco
                
            st.session_state.fornecedor_global = forn_cartao
            linhas = []
            portador = "Desconhecido"
            
            for partes in df_bruto:
                if len(partes) < 2: continue
                p0, p1 = str(partes[0]).strip(), str(partes[1]).strip()

                # Detecta Titular (Ex: ROMULO D NOGUEIRA - 5293)
                if " - " in p0 and (p1 == "" or p1 == "nan"):
                    portador = p0
                    continue
                
                # Detecta Compra (Data DD/MM)
                if re.match(r'^\d{2}/\d{2}$', p0):
                    if any(x in p1.upper() for x in ["SALDO ANTERIOR", "PAGTO", "PAGAMENTO", "TOTAL PARA"]):
                        continue
                    
                    try:
                        # Pega valor da coluna 5 (índice 4)
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
                df_c['Portador'] = df_f['Portador']
                df_c['Histórico Banco'] = df_f['Hist']
                df_c['Detalhes (Obs)'] = ""
                df_c['Estabelecimento'] = "" # Nova coluna para o usuário digitar a loja
                
                # NOVO: Lógica do Título Inteligente (Máx 8 caracteres)
                # Pega as 4 primeiras letras do primeiro nome do titular (Ex: ROMULO -> ROMU)
                nomes_curtos = df_f['Portador'].apply(lambda x: str(x).split()[0][:4].upper())
                # Cria a sequência 001, 002, 003... para cada linha
                sequencia = [f"{i:03d}" for i in range(1, len(df_f) + 1)]
                # Junta tudo (Ex: ROMU001, ROMU002). Total = 7 caracteres!
                df_c['Título'] = nomes_curtos + sequencia
                
                df_c['Conta Financeira'] = ""
                df_c['C.Custo'] = ""
                df_c['Valor'] = df_f['Val']
                df_c['Vencimento'] = venc_global
                        
                st.session_state.df_conciliacao = df_c
                salvar_fatura_no_disco() # Salva a fatura no HD!
                st.success("✅ Lançamentos processados e salvos com sucesso! A equipe já pode conciliar.")
        
        # 4. Lê os arquivos de cadastro base (Forn, CC, Conta)
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

        with aba1:
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
        # Puxa os dados originais
        df_completo = st.session_state.df_conciliacao.copy()
        
        # Filtra pela visão do usuário logado
        if perfil == "Gleider":
            df_visao = df_completo[df_completo['Portador'].str.contains("GLEIDER", case=False, na=False)]
        elif perfil == "Lilian":
            df_visao = df_completo[df_completo['Portador'].str.contains("LILIAN", case=False, na=False)]
        else:
            df_visao = df_completo # Admin vê tudo

        st.markdown(f"**Fornecedor Fixo no ERP:** `{st.session_state.fornecedor_global}` | **Visão Atual:** `{perfil}`")

        # NOVO: Barra de progresso interativa e aviso de salvamento
        total_linhas = len(df_visao)
        if total_linhas > 0:
            # Conta quantas linhas ainda têm algum campo em branco
            linhas_incompletas = df_visao[(df_visao['Conta Financeira'] == "") | (df_visao['C.Custo'] == "") | (df_visao['Estabelecimento'] == "")]
            linhas_preenchidas = total_linhas - len(linhas_incompletas)
            
            # Calcula a porcentagem para a barra (de 0.0 a 1.0)
            percentual = linhas_preenchidas / total_linhas
            
            # Mostra a barra na tela
            st.progress(percentual, text=f"📊 Progresso: {linhas_preenchidas} de {total_linhas} lançamentos preenchidos.")
            st.caption("💾 O sistema salva automaticamente a cada edição! Pode preencher aos poucos e fechar quando quiser.")

        # Configura as colunas
        config_colunas = {
            "Portador": st.column_config.TextColumn("Portador (Cartão)", disabled=True),
            "Histórico Banco": st.column_config.TextColumn("Histórico Original", disabled=True),
            "Estabelecimento": st.column_config.TextColumn("Loja / Compra (Obrigatório)", required=True),
            "Detalhes (Obs)": st.column_config.TextColumn("Detalhes"),
            "Valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
            "Vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
            "Status": st.column_config.TextColumn("Status", disabled=True)
        }
        
        if st.session_state.lista_contas: config_colunas["Conta Financeira"] = st.column_config.SelectboxColumn("Conta Financeira", options=st.session_state.lista_contas, required=True)
        else: config_colunas["Conta Financeira"] = st.column_config.TextColumn("Conta Financeira", required=True)

        if st.session_state.lista_cc: config_colunas["C.Custo"] = st.column_config.SelectboxColumn("C.Custo", options=st.session_state.lista_cc, required=True)
        else: config_colunas["C.Custo"] = st.column_config.TextColumn("C.Custo", required=True)

        # Exibe a tabela filtrada
        df_editado = st.data_editor(
            df_visao,
            column_config=config_colunas,
            num_rows="dynamic",
            width="stretch",
            height=500 
        )
        
        # Atualiza o banco principal APENAS com o que o usuário mexeu e SALVA no computador!
        if not df_editado.empty:
            df_completo.update(df_editado)
            
        st.session_state.df_conciliacao = df_completo
        salvar_fatura_no_disco() 
        
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
        # Botão para o usuário encerrar a fatura dele
        if perfil != "Admin":
            faltam = df_editado[(df_editado['Conta Financeira'] == "") | (df_editado['C.Custo'] == "") | (df_editado['Estabelecimento'] == "")]
            if st.button(f"🔒 Encerrar Minha Fatura ({perfil})"):
                if not faltam.empty:
                    st.error(f"❌ Você ainda tem {len(faltam)} linha(s) com campos em branco. Preencha tudo antes de encerrar!")
                else:
                    # Muda o status para concluído
                    st.session_state.df_conciliacao.loc[df_editado.index, 'Status'] = "Concluído ✅"
                    salvar_fatura_no_disco()
                    st.success("🎉 Parabéns! Sua fatura foi encerrada com sucesso. O Admin já pode exportar.")
                    st.rerun() # Atualiza a tela automaticamente

# ==========================================
# ABA 3: EXPORTAÇÃO (APENAS ADMIN)
# ==========================================
with aba3:
    if perfil != "Admin":
        st.error("🚫 Acesso restrito! Apenas o 'Admin' pode validar e exportar relatórios para o ERP.")
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
                faltam_dados = df_final[(df_final['Conta Financeira'] == "") | (df_final['C.Custo'] == "") | (df_final['Estabelecimento'] == "")]
                
                if not faltam_dados.empty:
                    st.error(f"🛑 BLOQUEADO: Existem {len(faltam_dados)} linhas com Conta, C.Custo ou Estabelecimento em branco na visualização '{filtro_export}'. Corrija na Aba 2 antes de baixar.")
                else:
                    st.success("✅ Tudo preenchido corretamente! Layout validado e pronto para o Senior.")

                    df_exportacao = df_final.copy()
                    df_exportacao['Fornecedor'] = st.session_state.fornecedor_global
                    
                    df_exportacao['Observação'] = df_exportacao.apply(
                        lambda row: f"{row['Histórico Banco']} - {row['Estabelecimento']} - {row['Detalhes (Obs)']} - {row['Portador']}" 
                        if row['Detalhes (Obs)'].strip() != "" 
                        else f"{row['Histórico Banco']} - {row['Estabelecimento']} - {row['Portador']}", 
                        axis=1
                    )
                    
                    colunas_senior = ['Fornecedor', 'Título', 'Observação', 'Valor', 'Conta Financeira', 'C.Custo', 'Vencimento']
                    df_exportacao = df_exportacao[colunas_senior]

                    def convert_df_to_csv(df):
                        csv_buffer = BytesIO()
                        df.to_csv(csv_buffer, index=False, sep=';', decimal=',', encoding='utf-8-sig')
                        return csv_buffer.getvalue()

                    st.download_button(
                        label=f"💾 BAIXAR ARQUIVO ({filtro_export.upper()})",
                        data=convert_df_to_csv(df_exportacao),
                        file_name=f"importacao_senior_{filtro_export.replace(' ', '_').lower()}_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        type="primary",
                        icon="💾"
                    )