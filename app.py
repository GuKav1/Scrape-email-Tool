import streamlit as st
from streamlit_gsheets import GSheetsConnection
import warnings
import os
import datetime

# --- INSTALAÇÃO FORÇADA NA CLOUD ---
os.system("playwright install chromium")

import socket
import requests
import pandas as pd
import time
import re
import urllib3
import random
import dns.resolver
import smtplib
from playwright.sync_api import sync_playwright
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- SILENCIADOR DE AVISOS ---
warnings.filterwarnings("ignore")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="Team Pipeline | GD Advertising", page_icon="🚀", layout="wide")

# LIGAÇÃO À TUA GOOGLE SHEET
URL_FOLHA = "https://docs.google.com/spreadsheets/d/1Yq3Vo-yaNrSyBkVLxETB6nNrqGSoefJ6-rtIwHHjabU/edit?usp=sharing"

# ==========================================
# 1. FUNÇÕES DE BASE DE DADOS (GOOGLE SHEETS)
# ==========================================
def get_db_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_enviados = conn.read(spreadsheet=URL_FOLHA, worksheet="Enviados")
        df_enviados = df_enviados.dropna(how="all") # Limpa linhas vazias
    except:
        df_enviados = pd.DataFrame(columns=['Data', 'Dominio', 'Email', 'Enviado_Por'])

    try:
        df_cache = conn.read(spreadsheet=URL_FOLHA, worksheet="Cache")
        df_cache = df_cache.dropna(how="all")
    except:
        df_cache = pd.DataFrame(columns=['Dominio', 'Emails_Encontrados'])
        
    return df_enviados, df_cache

def salvar_envio_gsheets(dominio, email, user, df_atual):
    conn = st.connection("gsheets", type=GSheetsConnection)
    nova_linha = pd.DataFrame([{
        "Data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Dominio": dominio,
        "Email": email,
        "Enviado_Por": user
    }])
    df_final = pd.concat([df_atual, nova_linha], ignore_index=True)
    conn.update(spreadsheet=URL_FOLHA, worksheet="Enviados", data=df_final)
    return df_final # Devolve o df atualizado

def salvar_cache_gsheets(dominio, emails_encontrados, df_atual):
    conn = st.connection("gsheets", type=GSheetsConnection)
    nova_linha = pd.DataFrame([{
        "Dominio": dominio,
        "Emails_Encontrados": emails_encontrados
    }])
    df_final = pd.concat([df_atual, nova_linha], ignore_index=True)
    conn.update(spreadsheet=URL_FOLHA, worksheet="Cache", data=df_final)
    return df_final

# ==========================================
# 2. FUNÇÕES DO MOTOR (Scrape & SMTP)
# ==========================================
def investigar_site(dominio):
    url = 'https://' + dominio if not dominio.startswith('http') else dominio
    resultado = "N/A"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            # Bloqueia imagens/videos para poupar RAM na Cloud
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())
            
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)
            html = page.content()
            
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html)
            emails_limpos = list(set([e.lower() for e in emails if dominio.split('.')[0] in e.lower() or 'gmail' in e.lower() or 'contact' in e.lower() or 'info' in e.lower()]))
            
            if emails_limpos:
                resultado = ", ".join(emails_limpos[:2])
            browser.close()
    except Exception as e:
        pass # Ignora silenciosamente para não parar o pipeline
    return resultado

def validar_email_smtp(email):
    try:
        dominio = email.split('@')[1]
        registos_mx = dns.resolver.resolve(dominio, 'MX')
        servidor_mx = str(registos_mx[0].exchange)
        host = socket.gethostname()
        server = smtplib.SMTP(timeout=8)
        server.set_debuglevel(0)
        server.connect(servidor_mx)
        server.helo(host)
        server.mail('goncalo.dias@cleveradvertising.com')
        code, _ = server.rcpt(str(email))
        server.quit()
        if code == 250: return "✅ Entregável"
        elif code == 550: return "❌ Inexistente"
        else: return f"⚠️ Duvidoso ({code})"
    except Exception:
        return "❓ Inconclusivo"

# ==========================================
# 3. INTERFACE (DASHBOARD)
# ==========================================
st.title("🚀 GD Advertising - Team Pipeline")
st.markdown("Base de Dados conectada em tempo real. Os envios da equipa estão sincronizados.")

with st.sidebar:
    st.header("👤 Identificação")
    user_name = st.text_input("O teu Nome", value="Gonçalo")
    
    st.divider()
    st.header("⚙️ Chaves de Envio")
    email_remetente = st.text_input("O teu Email de Envio", value="goncalo@gd-advertising.com")
    password_app = st.text_input("App Password", type="password")
    nome_remetente = st.text_input("Nome do Remetente", value="Gonçalo | GD Advertising")
    email_bcc = st.text_input("BCC (Oculto)", value="goncalo.dias@g13advertising.com")
    
    st.divider()
    st.header("⏳ Proteção Anti-Spam (Segundos)")
    pausa_min = st.number_input("Pausa Mínima", value=180)
    pausa_max = st.number_input("Pausa Máxima", value=420)

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Base de Dados (.TXT)")
    ficheiro_txt = st.file_uploader("Carrega os domínios (1 por linha)", type=['txt'])
    alvos = []
    if ficheiro_txt:
        alvos = [l.strip() for l in ficheiro_txt.getvalue().decode("utf-8").split("\n") if l.strip()]
        st.success(f"{len(alvos)} domínios carregados.")

with col2:
    st.subheader("2. Mensagem")
    assunto_template = st.text_input("Assunto", value="Direct Ad Partnership with {empresa} / Fixed Rates")
    corpo_template = st.text_area("Corpo do Email", height=250, value="""Hello,

My name is Gonçalo Dias, Media Buyer at Clever Advertising.

We manage global budgets for Tier-1 brands in the Fintech and Trading sectors (such as XM and Stake). We’ve been following {empresa} and we are interested in purchasing direct display inventory for a long-term partnership to reach your tech-savvy audience.

Our standard operating model:
Commercials: We work with Fixed CPM or Monthly Flat Fees.
Finance: We offer Prepayment for the first test run to eliminate any risk on your side.
Tech: Our ads are served via HTML5 3rd-party tags (100% Brand Safe), fully compatible with AdGlare, Google Ad Manager, or any other ad server you use.

Could you please share your latest Media Kit and Direct Rates for display placements (300x250 / 728x90)? We are ready to start a test campaign immediately.

Best regards,

Gonçalo Dias
Media Buyer | Clever Advertising""")

st.divider()
iniciar = st.button("🚀 INICIAR CAMPANHA DA EQUIPA", type="primary", use_container_width=True)

# ==========================================
# 4. EXECUÇÃO
# ==========================================
if iniciar:
    if not ficheiro_txt or not password_app or not user_name:
        st.error("⚠️ Preenche o teu Nome, a App Password e carrega a lista antes de começar.")
    else:
        # Carrega dados atualizados da Google Sheet
        st.info("🔄 A sincronizar com a Base de Dados Central...")
        df_enviados_db, df_cache_db = get_db_data()
        
        # Converte Cache para dicionário para pesquisa super rápida
        cache_dict = {}
        if not df_cache_db.empty:
            cache_dict = dict(zip(df_cache_db['Dominio'], df_cache_db['Emails_Encontrados']))
            
        # Converte Enviados para lista
        enviados_list = []
        if not df_enviados_db.empty:
            enviados_list = df_enviados_db['Dominio'].tolist()

        # --- FASE 1: SCRAPING (COM CACHE DA EQUIPA) ---
        st.subheader("🔎 Fase 1: Scrapping Centralizado")
        progresso_scrape = st.progress(0)
        caixa_scrape = st.empty()
        
        dados_scraped = []
        
        for i, dominio in enumerate(alvos):
            # 1. Se já alguém da equipa enviou, ignora logo o scrape!
            if dominio in enviados_list:
                quem_enviou = df_enviados_db[df_enviados_db['Dominio'] == dominio]['Enviado_Por'].values[0]
                caixa_scrape.warning(f"⏭️ {dominio} ignorado. Contactado por: {quem_enviou}")
                dados_scraped.append({"Domínio": dominio, "Emails_Site": "N/A - Já Contactado"})
                progresso_scrape.progress((i + 1) / len(alvos))
                continue

            # 2. Se já estiver no Cache (alguém já pesquisou antes)
            if dominio in cache_dict:
                caixa_scrape.info(f"⚡ Recuperado do Cache (Cloud): {dominio}")
                dados_scraped.append({"Domínio": dominio, "Emails_Site": cache_dict[dominio]})
            
            # 3. Faz o Scrape real
            else:
                caixa_scrape.text(f"A investigar: {dominio}...")
                emails_encontrados = investigar_site(dominio)
                dados_scraped.append({"Domínio": dominio, "Emails_Site": emails_encontrados})
                
                # Guarda na Folha de Cálculo para o próximo colega não ter de procurar
                df_cache_db = salvar_cache_gsheets(dominio, emails_encontrados, df_cache_db)
                cache_dict[dominio] = emails_encontrados
                
            progresso_scrape.progress((i + 1) / len(alvos))
            
        # --- FASE 2: VALIDAÇÃO ---
        st.subheader("🛡️ Fase 2: Validação SMTP")
        caixa_valid = st.empty()
        
        dados_finais = []
        for linha in dados_scraped:
            email_bruto = linha.get("Emails_Site", "N/A")
            if "@" in email_bruto and "Já Contactado" not in email_bruto:
                primeiro_email = email_bruto.split(',')[0].strip()
                linha["Email_Status"] = validar_email_smtp(primeiro_email)
            else:
                linha["Email_Status"] = "N/A"
            dados_finais.append(linha)
            
        df_all = pd.DataFrame(dados_finais)
        df_validos = df_all[df_all['Email_Status'].str.contains('✅|⚠️|❓', na=False)]
        
        with st.expander("Ver lista de Emails Prontos a Enviar", expanded=True):
            st.dataframe(df_validos[['Domínio', 'Emails_Site', 'Email_Status']])

        # --- FASE 3: ENVIO E REGISTO NA BD ---
        if df_validos.empty:
            st.error("❌ Nenhum e-mail novo e válido para enviar.")
        else:
            st.subheader("📨 Fase 3: Disparo e Sincronização")
            progresso_envio = st.progress(0)
            caixa_envio = st.empty()
            
            total = len(df_validos)
            
            for index, linha in df_validos.reset_index(drop=True).iterrows():
                destino = linha['Emails_Site'].split(',')[0].strip()
                dominio_alvo = linha['Domínio']
                empresa_limpa = dominio_alvo.replace('www.', '').split('.')[0].capitalize()
                
                assunto_final = assunto_template.replace("{empresa}", empresa_limpa)
                corpo_final = corpo_template.replace("{empresa}", empresa_limpa)
                
                msg = MIMEMultipart()
                msg['From'] = f"{nome_remetente} <{email_remetente}>"
                msg['To'] = destino
                msg['Subject'] = assunto_final
                msg.attach(MIMEText(corpo_final, 'plain'))
                msg.add_header('List-Unsubscribe', f'<mailto:{email_remetente}?subject=unsubscribe>')
                
                destinatarios_reais = [destino, email_bcc] if email_bcc else [destino]
                
                try:
                    server = smtplib.SMTP('smtp.gmail.com', 587)
                    server.starttls()
                    server.login(email_remetente, password_app)
                    server.sendmail(email_remetente, destinatarios_reais, msg.as_string())
                    server.quit()
                    
                    # REGISTA NA GOOGLE SHEET!
                    df_enviados_db = salvar_envio_gsheets(dominio_alvo, destino, user_name, df_enviados_db)
                    
                    caixa_envio.success(f"✅ Enviado: {empresa_limpa} (Registado na BD)")
                except Exception as e:
                    caixa_envio.error(f"❌ Erro em {destino}: {e}")
                
                progresso_envio.progress((index + 1) / total)
                
                if index < total - 1:
                    t_espera = random.randint(int(pausa_min), int(pausa_max))
                    with st.spinner(f"⏳ Pausa de {round(t_espera/60, 1)} min. NÃO FECHES A PÁGINA..."):
                        time.sleep(t_espera)

            st.balloons()
            st.success("🏁 CAMPANHA TERMINADA! A Base de Dados Central foi atualizada.")
