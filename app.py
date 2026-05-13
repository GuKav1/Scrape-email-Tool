import streamlit as st
from streamlit_gsheets import GSheetsConnection
import warnings
import os
import datetime

# --- INSTALAÇÃO FORÇADA DO NAVEGADOR NA CLOUD ---
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

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Team Pipeline | GD Advertising", page_icon="🚀", layout="wide")

# URL DA TUA BASE DE DADOS CENTRAL
URL_FOLHA = "https://docs.google.com/spreadsheets/d/1Yq3Vo-yaNrSyBkVLxETB6nNrqGSoefJ6-rtIwHHjabU/edit?usp=sharing"

# ==========================================
# 1. FUNÇÕES DE BASE DE DADOS (GOOGLE SHEETS)
# ==========================================
def get_db_data():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        try:
            df_enviados = conn.read(spreadsheet=URL_FOLHA, worksheet="Enviados")
            df_enviados = df_enviados.dropna(how="all")
        except:
            df_enviados = pd.DataFrame(columns=['Data', 'Dominio', 'Email', 'Enviado_Por'])

        try:
            df_cache = conn.read(spreadsheet=URL_FOLHA, worksheet="Cache")
            df_cache = df_cache.dropna(how="all")
        except:
            df_cache = pd.DataFrame(columns=['Dominio', 'Emails_Encontrados'])
            
        return df_enviados, df_cache
    except Exception:
        return pd.DataFrame(columns=['Data', 'Dominio', 'Email', 'Enviado_Por']), pd.DataFrame(columns=['Dominio', 'Emails_Encontrados'])

def salvar_envio_gsheets(dominio, email, user, df_atual):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        nova_linha = pd.DataFrame([{
            "Data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Dominio": dominio,
            "Email": email,
            "Enviado_Por": user
        }])
        df_final = pd.concat([df_atual, nova_linha], ignore_index=True)
        conn.update(spreadsheet=URL_FOLHA, worksheet="Enviados", data=df_final)
        return df_final
    except Exception:
        st.toast(f"⚠️ Google Sheets ocupada. O email para {dominio} foi enviado, mas o registo pode ter falhado.")
        return df_atual

def salvar_cache_lote_gsheets(lista_novos_caches, df_atual):
    if not lista_novos_caches: return df_atual
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        novas_linhas = pd.DataFrame(lista_novos_caches)
        df_final = pd.concat([df_atual, novas_linhas], ignore_index=True)
        df_final = df_final.drop_duplicates(subset=['Dominio'], keep='last')
        conn.update(spreadsheet=URL_FOLHA, worksheet="Cache", data=df_final)
        return df_final
    except Exception:
        st.toast("⚠️ Falha ao guardar lote no Cache. A pesquisa continua na RAM.")
        return df_atual

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
            # Upgrade Ninja: Bloqueia media para não estoirar a RAM
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())
            
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)
            html = page.content()
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html)
            emails_limpos = list(set([e.lower() for e in emails if dominio.split('.')[0] in e.lower() or 'gmail' in e.lower() or 'contact' in e.lower() or 'info' in e.lower()]))
            if emails_limpos:
                resultado = ", ".join(emails_limpos[:2])
            browser.close()
    except: pass
    return resultado

def validar_email_smtp(email):
    try:
        dom = email.split('@')[1]
        mx = dns.resolver.resolve(dom, 'MX')
        server = smtplib.SMTP(timeout=8)
        server.connect(str(mx[0].exchange))
        server.helo(socket.gethostname())
        server.mail('goncalo.dias@cleveradvertising.com')
        code, _ = server.rcpt(str(email))
        server.quit()
        if code == 250: return "✅ Entregável"
        elif code == 550: return "❌ Inexistente"
        else: return f"⚠️ Duvidoso ({code})"
    except: return "❓ Inconclusivo"

# ==========================================
# 3. INTERFACE (DASHBOARD)
# ==========================================
st.title("🚀 GD Advertising - Team Pipeline")

with st.sidebar:
    st.header("👤 Utilizador")
    user_name = st.text_input("O teu Nome", value="Gonçalo")
    
    st.divider()
    st.header("⚙️ Opções de Envio")
    allow_personal_repeat = st.toggle("Permitir re-enviar para domínios já contactados por MIM", value=False)
    
    st.divider()
    email_remetente = st.text_input("Email de Envio", value="goncalo@gd-advertising.com")
    password_app = st.text_input("App Password", type="password")
    nome_remetente = st.text_input("Nome Visível", value="Gonçalo | GD Advertising")
    email_bcc = st.text_input("BCC (Cópia Oculta)", value="goncalo.dias@g13advertising.com")
    
    st.divider()
    pausa_min = st.number_input("Pausa Min (seg)", value=180)
    pausa_max = st.number_input("Pausa Max (seg)", value=420)

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Domínios (.TXT)")
    ficheiro_txt = st.file_uploader("Upload do ficheiro", type=['txt'])
    alvos = [l.strip() for l in ficheiro_txt.getvalue().decode("utf-8").split("\n") if l.strip()] if ficheiro_txt else []

with col2:
    st.subheader("2. Mensagem")
    assunto_t = st.text_input("Assunto", value="Direct Ad Partnership with {empresa}")
    corpo_t = st.text_area("Mensagem", height=200, value="Hello,\n\nMy name is {user}, Media Buyer at Clever Advertising...")

st.divider()
iniciar = st.button("🚀 INICIAR PIPELINE INTELIGENTE", type="primary", use_container_width=True)

# ==========================================
# 4. EXECUÇÃO
# ==========================================
if iniciar and alvos:
    st.info("🔄 Sincronizando com a Base de Dados Central...")
    df_env, df_cac = get_db_data()
    
    # --- FASE 1: SCRAPE EM LOTE (CHECKPOINTS DE 75 EM 75) ---
    st.subheader("🔎 Fase 1: Scrapping (Cache c/ Checkpoints)")
    prog_s = st.progress(0)
    log_s = st.empty()
    
    cache_dict = dict(zip(df_cac['Dominio'], df_cac['Emails_Encontrados'])) if not df_cac.empty else {}
    dados_scraped = []
    novos_para_cache = [] 
    
    TAMANHO_LOTE = 75 # Configurado para 75 como pediste
    
    for i, dom in enumerate(alvos):
        if dom in cache_dict:
            log_s.text(f"⚡ Recuperado do Cache: {dom}")
            dados_scraped.append({"Domínio": dom, "Emails_Site": cache_dict[dom]})
        else:
            log_s.text(f"🌐 Investigando: {dom}...")
            em = investigar_site(dom)
            dados_scraped.append({"Domínio": dom, "Emails_Site": em})
            
            novos_para_cache.append({"Dominio": dom, "Emails_Encontrados": em})
            cache_dict[dom] = em
            
            # Checkpoint de 75
            if len(novos_para_cache) >= TAMANHO_LOTE:
                log_s.info(f"📦 A guardar checkpoint de {TAMANHO_LOTE} sites na Google Sheet...")
                df_cac = salvar_cache_lote_gsheets(novos_para_cache, df_cac)
                novos_para_cache = [] 
                
        prog_s.progress((i + 1) / len(alvos))
        
    # Salva o que sobrar no fim do loop
    if novos_para_cache:
        log_s.info(f"📦 A guardar os últimos {len(novos_para_cache)} sites na Google Sheet...")
        df_cac = salvar_cache_lote_gsheets(novos_para_cache, df_cac)
        
    log_s.success("✅ Scrape concluído e Cache atualizado!")
    
    # --- FASE 2: VALIDAÇÃO ---
    st.subheader("🛡️ Fase 2: Validação SMTP")
    dados_val = []
    for l in dados_scraped:
        em = l["Emails_Site"]
        l["Email_Status"] = validar_email_smtp(em.split(',')[0].strip()) if "@" in em else "N/A"
        dados_val.append(l)
    
    df_pronto = pd.DataFrame(dados_val)
    df_validos = df_pronto[df_pronto['Email_Status'].str.contains('✅|⚠️|❓', na=False)]
    
    # --- FASE 3: DISPARO ---
    st.subheader("📨 Fase 3: Disparo Estratégico")
    prog_e = st.progress(0)
    log_e = st.empty()
    
    total = len(df_validos)
    for idx, linha in df_validos.reset_index(drop=True).iterrows():
        dom = linha['Domínio']
        email_to = linha['Emails_Site'].split(',')[0].strip()
        empresa = dom.replace('www.', '').split('.')[0].capitalize()
        
        # Filtro de repetição
        ja_enviado_por_MIM = not df_env.empty and not df_env[(df_env['Dominio'] == dom) & (df_env['Enviado_Por'] == user_name)].empty
        
        if ja_enviado_por_MIM and not allow_personal_repeat:
            log_e.warning(f"⏭️ {dom} ignorado: Tu já contactaste este domínio.")
        else:
            try:
                msg = MIMEMultipart()
                msg['From'] = f"{nome_remetente} <{email_remetente}>"
                msg['To'] = email_to
                msg['Subject'] = assunto_t.format(empresa=empresa)
                msg.attach(MIMEText(corpo_t.format(empresa=empresa, user=user_name), 'plain'))
                
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(email_remetente, password_app)
                server.sendmail(email_remetente, [email_to, email_bcc], msg.as_string())
                server.quit()
                
                # Registo individual na folha
                df_env = salvar_envio_gsheets(dom, email_to, user_name, df_env)
                log_e.success(f"✅ Enviado: {dom}")
            except Exception as e:
                log_e.error(f"❌ Erro em {dom}: {e}")
        
        prog_e.progress((idx + 1) / total)
        if idx < total - 1: time.sleep(random.randint(pausa_min, pausa_max))

    st.balloons()
    st.success("🏁 Processo concluído com sucesso!")
    
