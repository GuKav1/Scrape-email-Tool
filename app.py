import streamlit as st
import warnings
import os
os.system("playwright install chromium")
import socket
import requests
import pandas as pd
import time
import re
import urllib3
import random
import whois
import dns.resolver
import smtplib
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- SILENCIADOR DE AVISOS E MAC FIX ---
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", module="urllib3")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="God Mode | GD Advertising", page_icon="⚡", layout="wide")
st.title("⚡ God Mode Pipeline - GD Advertising")
st.markdown("Dropa o teu ficheiro `.txt` com os domínios. A IA vai encontrar os emails, validar a segurança e disparar a campanha automaticamente.")

ARQUIVO_MEMORIA = "enviados.txt"

# ==========================================
# FUNÇÕES DE LÓGICA (Scrape, Validação, Memória)
# ==========================================
def carregar_emails_enviados():
    if not os.path.exists(ARQUIVO_MEMORIA): return set()
    with open(ARQUIVO_MEMORIA, 'r') as f: return set(f.read().splitlines())

def registar_envio(email):
    with open(ARQUIVO_MEMORIA, 'a') as f: f.write(email + '\n')

def investigar_site(dominio):
    url = 'https://' + dominio if not dominio.startswith('http') else dominio
    dados = {"Domínio": dominio, "Emails_Site": "N/A", "Email_Status": "Pendente"}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
            page.goto(url, timeout=25000, wait_until="domcontentloaded")
            time.sleep(3)
            html = page.content()
            
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html)
            dados["Emails_Site"] = ", ".join(list(set([e.lower() for e in emails if dominio.split('.')[0] in e.lower() or 'gmail' in e.lower()]))[:2])
            browser.close()
    except Exception:
        pass
    return dados

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
# INTERFACE (DASHBOARD)
# ==========================================
with st.sidebar:
    st.header("⚙️ Configurações Gerais")
    email_remetente = st.text_input("O teu Email", value="goncalo@gd-advertising.com")
    password_app = st.text_input("App Password", type="password")
    nome_remetente = st.text_input("Nome do Remetente", value="Gonçalo | GD Advertising")
    email_bcc = st.text_input("Email em Cópia Oculta (BCC)", value="goncalo.dias@g13advertising.com")
    
    st.divider()
    st.header("⏳ Proteção Anti-Spam (Segundos)")
    pausa_min = st.number_input("Pausa Mínima", value=180)
    pausa_max = st.number_input("Pausa Máxima", value=420)

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Base de Dados (.TXT)")
    ficheiro_txt = st.file_uploader("Carrega o ficheiro com os domínios (1 por linha)", type=['txt'])
    alvos = []
    if ficheiro_txt:
        linhas = ficheiro_txt.getvalue().decode("utf-8").split("\n")
        alvos = [l.strip() for l in linhas if l.strip()]
        st.success(f"Ficheiro carregado! {len(alvos)} domínios encontrados.")

with col2:
    st.subheader("2. Mensagem")
    assunto_template = st.text_input("Assunto do Email", value="Direct Ad Partnership with {empresa} / Fixed Rates")
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
iniciar = st.button("🚀 INICIAR GOD MODE PIPELINE", type="primary", use_container_width=True)

# ==========================================
# O MOTOR (EXECUÇÃO)
# ==========================================
if iniciar:
    if not ficheiro_txt or not password_app:
        st.error("⚠️ Carrega o ficheiro TXT e insere a App Password na barra lateral antes de começar.")
    else:
        st.info("🔥 God Mode Ativado! Não feches esta página.")
        
        # --- FASE 1: SCRAPING ---
        st.subheader("🔎 Fase 1: Scrapping (A procurar emails...)")
        progresso_scrape = st.progress(0)
        caixa_scrape = st.empty()
        
        dados_scraped = []
        for i, dominio in enumerate(alvos):
            caixa_scrape.text(f"A investigar: {dominio}...")
            res = investigar_site(dominio)
            dados_scraped.append(res)
            progresso_scrape.progress((i + 1) / len(alvos))
        
        caixa_scrape.success("✅ Scrape concluído!")
        
        # --- FASE 2: VALIDAÇÃO ---
        st.subheader("🛡️ Fase 2: Validação (A testar caixas de correio...)")
        progresso_valid = st.progress(0)
        caixa_valid = st.empty()
        
        def validar_linha_com_progresso(index, linha):
            email_bruto = linha.get("Emails_Site", "N/A")
            if email_bruto != "N/A" and "@" in email_bruto:
                primeiro_email = email_bruto.split(',')[0].strip()
                linha["Email_Status"] = validar_email_smtp(primeiro_email)
            else:
                linha["Email_Status"] = "N/A"
            return linha

        dados_finais = []
        for i, linha in enumerate(dados_scraped):
            caixa_valid.text(f"A validar: {linha['Domínio']}...")
            dados_finais.append(validar_linha_com_progresso(i, linha))
            progresso_valid.progress((i + 1) / len(dados_scraped))
            
        caixa_valid.success("✅ Validação concluída!")

        # Filtra os válidos e salva um backup em Excel (just in case)
        df_all = pd.DataFrame(dados_finais)
        df_validos = df_all[df_all['Email_Status'].str.contains('✅|⚠️|❓', na=False)]
        df_all.to_excel("backup_ultima_campanha.xlsx", index=False)
        st.write(f"📊 Encontrados **{len(df_validos)}** emails válidos para contacto. (Backup guardado na pasta).")

        # --- FASE 3: ENVIO DE EMAILS ---
        if df_validos.empty:
            st.error("❌ Nenhum email válido foi encontrado nesta lista de domínios.")
        else:
            st.subheader("📨 Fase 3: Disparo de Cold Emails")
            progresso_envio = st.progress(0)
            caixa_envio = st.empty()
            emails_ja_enviados = carregar_emails_enviados()
            
            total_contactos = len(df_validos)
            
            for index, linha in df_validos.reset_index(drop=True).iterrows():
                email_bruto = linha['Emails_Site']
                destino = email_bruto.split(',')[0].strip()
                empresa_limpa = linha['Domínio'].replace('www.', '').split('.')[0].capitalize()
                
                if destino in emails_ja_enviados:
                    caixa_envio.warning(f"⏭️ Ignorado (já enviado antes): {destino}")
                    progresso_envio.progress((index + 1) / total_contactos)
                    continue
                
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
                    
                    registar_envio(destino)
                    caixa_envio.success(f"✅ Enviado: {empresa_limpa} ({destino})")
                except Exception as e:
                    caixa_envio.error(f"❌ Erro em {destino}: {e}")
                
                progresso_envio.progress((index + 1) / total_contactos)
                
                if index < total_contactos - 1:
                    tempo_espera = random.randint(int(pausa_min), int(pausa_max))
                    minutos = round(tempo_espera / 60, 1)
                    with st.spinner(f"⏳ Pausa de {minutos} minutos. NÃO FECHES A PÁGINA..."):
                        time.sleep(tempo_espera)

            st.balloons()
            st.success("🏁 PIPELINE COMPLETO! Campanha enviada com sucesso!")
            