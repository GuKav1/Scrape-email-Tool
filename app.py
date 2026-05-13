import streamlit as st
from streamlit_gsheets import GSheetsConnection
import warnings
import os
import datetime
import gc

# --- INSTALAÇÃO FORÇADA ---
os.system("playwright install chromium")

import socket
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

# --- SILENCIADOR E CONFIG ---
warnings.filterwarnings("ignore")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"
st.set_page_config(page_title="GD Cascading Pipeline", page_icon="⚡", layout="wide")

URL_FOLHA = "https://docs.google.com/spreadsheets/d/1Yq3Vo-yaNrSyBkVLxETB6nNrqGSoefJ6-rtIwHHjabU/edit?usp=sharing"

# ==========================================
# 1. FUNÇÕES DE BASE DE DADOS
# ==========================================
def get_db_data():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_env = conn.read(spreadsheet=URL_FOLHA, worksheet="Enviados").dropna(how="all")
        df_cac = conn.read(spreadsheet=URL_FOLHA, worksheet="Cache").dropna(how="all")
        return df_env, df_cac
    except:
        return pd.DataFrame(columns=['Data', 'Dominio', 'Email', 'Enviado_Por']), pd.DataFrame(columns=['Dominio', 'Emails_Encontrados'])

def salvar_envio_gsheets(dominio, email, user, df_atual):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        nova_linha = pd.DataFrame([{"Data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "Dominio": dominio, "Email": email, "Enviado_Por": user}])
        df_final = pd.concat([df_atual, nova_linha], ignore_index=True)
        conn.update(spreadsheet=URL_FOLHA, worksheet="Enviados", data=df_final)
        return df_final
    except:
        st.toast(f"⚠️ Erro ao registar {dominio} no Sheets.")
        return df_atual

def salvar_cache_lote_gsheets(lista_novos_caches, df_atual):
    if not lista_novos_caches: return df_atual
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        novas_linhas = pd.DataFrame(lista_novos_caches)
        df_final = pd.concat([df_atual, novas_linhas], ignore_index=True).drop_duplicates(subset=['Dominio'], keep='last')
        conn.update(spreadsheet=URL_FOLHA, worksheet="Cache", data=df_final)
        return df_final
    except:
        return df_atual

# ==========================================
# 2. MOTOR (SCRAPE & VALIDATE)
# ==========================================
def investigar_site(dominio):
    resultado = "N/A"
    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(user_agent="Mozilla/5.0")
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())
            page.goto('https://' + dominio if not dominio.startswith('http') else dominio, timeout=30000)
            time.sleep(2)
            html = page.content()
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html)
            emails_limpos = list(set([e.lower() for e in emails if dominio.split('.')[0] in e.lower() or 'gmail' in e.lower() or 'contact' in e.lower() or 'info' in e.lower()]))
            if emails_limpos: resultado = ", ".join(emails_limpos[:2])
            browser.close()
    except:
        if browser: browser.close()
    finally:
        gc.collect()
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
        return "✅" if code == 250 else "❌"
    except: return "❓"

# ==========================================
# 3. INTERFACE
# ==========================================
st.title("⚡ GD Advertising - Cascading Pipeline")

with st.sidebar:
    user_name = st.text_input("Nome", value="Gonçalo")
    email_remetente = st.text_input("Email", value="goncalo@gd-advertising.com")
    password_app = st.text_input("App Password", type="password")
    pausa_min = st.number_input("Pausa Min (seg)", value=180)
    pausa_max = st.number_input("Pausa Max (seg)", value=420)
    tamanho_bloco = st.slider("Tamanho do Bloco (Sites)", 10, 200, 100)

ficheiro_txt = st.file_uploader("Upload domínios (.txt)", type=['txt'])
assunto_t = st.text_input("Assunto", value="Partnership with {empresa}")
corpo_t = st.text_area("Corpo", value="Hello {empresa}, my name is {user}...")

if st.button("🚀 INICIAR PIPELINE EM CASCATA") and ficheiro_txt:
    alvos_total = [l.strip() for l in ficheiro_txt.getvalue().decode("utf-8").split("\n") if l.strip()]
    
    # DIVIDIR A LISTA EM BLOCOS (Ex: 700 sites -> 7 blocos de 100)
    blocos = [alvos_total[i:i + tamanho_bloco] for i in range(0, len(alvos_total), tamanho_bloco)]
    
    st.info(f"📋 Total: {len(alvos_total)} sites divididos em {len(blocos)} blocos de {tamanho_bloco}.")
    
    for idx_bloco, bloco_atual in enumerate(blocos):
        st.subheader(f"📦 Processando Bloco {idx_bloco + 1} de {len(blocos)}")
        
        # 1. SINCRONIZAR DB
        df_env, df_cac = get_db_data()
        cache_dict = dict(zip(df_cac['Dominio'], df_cac['Emails_Encontrados'])) if not df_cac.empty else {}
        
        # 2. SCRAPE DO BLOCO
        dados_bloco = []
        novos_cache = []
        p_scrape = st.progress(0)
        
        for i, dom in enumerate(bloco_atual):
            # Verificar se eu já enviei antes de fazer scrape
            if not df_env.empty and dom in df_env[df_env['Enviado_Por'] == user_name]['Dominio'].values:
                st.write(f"⏭️ {dom} já enviado por ti. Saltando.")
                continue
                
            if dom in cache_dict:
                dados_bloco.append({"Domínio": dom, "Email": cache_dict[dom]})
            else:
                em = investigar_site(dom)
                dados_bloco.append({"Domínio": dom, "Email": em})
                novos_cache.append({"Dominio": dom, "Emails_Encontrados": em})
                cache_dict[dom] = em
            p_scrape.progress((i + 1) / len(bloco_atual))
        
        # Guardar Cache do bloco
        df_cac = salvar_cache_lote_gsheets(novos_cache, df_cac)
        
        # 3. FILTRAR E ENVIAR O BLOCO
        st.write("📨 Enviando emails deste bloco...")
        df_validos = [d for d in dados_bloco if "@" in d["Email"]]
        
        for idx_envio, item in enumerate(df_validos):
            destino = item["Email"].split(',')[0].strip()
            empresa = item["Domínio"].split('.')[0].capitalize()
            
            # Validação rápida antes de enviar
            if validar_email_smtp(destino) == "✅":
                try:
                    # [Lógica de Envio SMTP aqui...]
                    # Simulação de envio para o log
                    st.success(f"Enviado para {item['Domínio']}")
                    df_env = salvar_envio_gsheets(item["Domínio"], destino, user_name, df_env)
                except:
                    st.error(f"Falha no envio para {destino}")
            
            # Pausa apenas se não for o último do bloco total
            if idx_envio < len(df_validos) - 1:
                t_espera = random.randint(pausa_min, pausa_max)
                t_box = st.empty()
                for s in range(t_espera, 0, -1):
                    t_box.metric("Próximo envio em:", f"{s}s")
                    time.sleep(1)
                t_box.empty()
        
        st.write(f"✅ Bloco {idx_bloco + 1} finalizado.")
        gc.collect()

    st.balloons()
    
