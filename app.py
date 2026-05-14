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

# --- CONFIGURAÇÕES DE ESTABILIDADE ---
warnings.filterwarnings("ignore")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

st.set_page_config(page_title="GD Stable Pro + Logs", page_icon="🛡️", layout="wide")

URL_FOLHA = "https://docs.google.com/spreadsheets/d/1Yq3Vo-yaNrSyBkVLxETB6nNrqGSoefJ6-rtIwHHjabU/edit?usp=sharing"

# ==========================================
# 1. PERSISTÊNCIA DE SESSÃO
# ==========================================
if 'running' not in st.session_state:
    st.session_state.running = False
if 'bloco_atual' not in st.session_state:
    st.session_state.bloco_atual = 0

# ==========================================
# 2. FUNÇÕES DE BASE DE DADOS
# ==========================================
def get_db_data():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_env = conn.read(spreadsheet=URL_FOLHA, worksheet="Enviados", ttl=0).dropna(how="all")
        df_cac = conn.read(spreadsheet=URL_FOLHA, worksheet="Cache", ttl=0).dropna(how="all")
        return df_env, df_cac
    except:
        return pd.DataFrame(columns=['Data', 'Dominio', 'Email', 'Enviado_Por']), pd.DataFrame(columns=['Dominio', 'Emails_Encontrados'])

def salvar_envio_gsheets(dominio, email, user, df_atual):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        nova_linha = pd.DataFrame([{"Data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "Dominio": dominio, "Email": str(email), "Enviado_Por": user}])
        df_final = pd.concat([df_atual, nova_linha], ignore_index=True)
        conn.update(spreadsheet=URL_FOLHA, worksheet="Enviados", data=df_final)
        return df_final
    except:
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
# 3. MOTOR DE INVESTIGAÇÃO
# ==========================================
def investigar_site(dominio):
    url = 'https://' + dominio if not dominio.startswith('http') else dominio
    resultado = "N/A"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--single-process"])
            page = browser.new_page(user_agent="Mozilla/5.0")
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())
            try:
                page.goto(url, timeout=25000, wait_until="commit")
                time.sleep(2)
                html = page.content()
                emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html)
                emails_limpos = list(set([e.lower() for e in emails if dominio.split('.')[0] in e.lower() or 'gmail' in e.lower() or 'contact' in e.lower() or 'info' in e.lower()]))
                if emails_limpos:
                    resultado = ", ".join(emails_limpos[:2])
            except: pass
            browser.close()
    except: pass
    finally: gc.collect()
    return str(resultado)

def validar_email_smtp(email):
    try:
        email_str = str(email)
        dom = email_str.split('@')[1]
        mx = dns.resolver.resolve(dom, 'MX')
        server = smtplib.SMTP(timeout=5)
        server.connect(str(mx[0].exchange))
        server.helo(socket.gethostname())
        server.mail('goncalo.dias@cleveradvertising.com')
        code, _ = server.rcpt(email_str)
        server.quit()
        return "✅" if code == 250 else "❌"
    except: return "❓"

# ==========================================
# 4. INTERFACE
# ==========================================
with st.sidebar:
    st.header("👤 Perfil")
    user_name = st.text_input("Teu Nome", value="Gonçalo")
    email_rem = st.text_input("Teu Email", value="goncalo@gd-advertising.com")
    pass_app = st.text_input("App Password", type="password")
    
    st.divider()
    pausa_min = st.number_input("Pausa E-mails Min", value=180)
    pausa_max = st.number_input("Pausa E-mails Max", value=420)
    
    st.divider()
    usar_pausa_bloco = st.toggle("Pausa entre blocos", value=True)
    tempo_bloco_seg = st.number_input("Segundos", value=600)
    tamanho_bloco = st.slider("Tamanho do Bloco", 10, 50, 30)

st.title("🛡️ GD Advertising - Stable Pro Pipeline")

txt = st.file_uploader("Upload domínios (.txt)", type=['txt'])
alvos_total = [l.strip() for l in txt.getvalue().decode("utf-8").split("\n") if l.strip()] if txt else []

col_msg1, col_msg2 = st.columns(2)
with col_msg1:
    assunto_t = st.text_input("Assunto", value="Partnership with {empresa}")
with col_msg2:
    corpo_t = st.text_area("Mensagem", value="Hello {empresa}, I'm {user}...")

# ==========================================
# 5. EXECUÇÃO CASCATA
# ==========================================
if st.button("🚀 INICIAR PIPELINE", type="primary"):
    st.session_state.running = True

if st.session_state.running and alvos_total:
    blocos = [alvos_total[i:i + tamanho_bloco] for i in range(0, len(alvos_total), tamanho_bloco)]
    
    for idx_b in range(st.session_state.bloco_atual, len(blocos)):
        bloco = blocos[idx_b]
        st.markdown(f"### 📦 Processando Bloco {idx_b + 1} de {len(blocos)}")
        
        # Sincronizar dados
        df_env, df_cac = get_db_data()
        cache_dict = dict(zip(df_cac['Dominio'], df_cac['Emails_Encontrados'])) if not df_cac.empty else {}
        
        dados_bloco = []
        novos_cac = []
        
        # --- UI DE STATUS ---
        barra_progresso = st.progress(0)
        status_texto = st.empty() # AQUI É O LOG EM TEMPO REAL
        
        # SCRAPE
        for i, dom in enumerate(bloco):
            # Verificar se já enviado por mim
            ja_enviado = not df_env.empty and dom in df_env[df_env['Enviado_Por'] == user_name]['Dominio'].values
            
            if ja_enviado:
                status_texto.warning(f"⏭️ {dom} já enviado anteriormente. Ignorando...")
            else:
                if dom in cache_dict:
                    status_texto.info(f"⚡ Recuperado do Cache: {dom}")
                    dados_bloco.append({"Domínio": dom, "Email": str(cache_dict[dom])})
                else:
                    status_texto.text(f"🌐 Investigando novo site: {dom}...")
                    em = investigar_site(dom)
                    dados_bloco.append({"Domínio": dom, "Email": em})
                    novos_cac.append({"Dominio": dom, "Emails_Encontrados": em})
                    cache_dict[dom] = em
            
            barra_progresso.progress((i + 1) / len(bloco))
        
        # Guardar progresso do Scrape
        status_texto.text("💾 Guardando descobertas na Google Sheet...")
        df_cac = salvar_cache_lote_gsheets(novos_cac, df_cac)
        
        # ENVIOS
        enviar_estes = [d for d in dados_bloco if d.get("Email") and "@" in str(d["Email"])]
        
        if enviar_estes:
            status_texto.success(f"📨 Encontrados {len(enviar_estes)} emails válidos. Iniciando disparos...")
            for idx_e, item in enumerate(enviar_estes):
                dest = str(item["Email"]).split(',')[0].strip()
                emp = item["Domínio"].replace('www.','').split('.')[0].capitalize()
                
                status_texto.text(f"📧 Enviando para: {dest} ({item['Domínio']})")
                
                if validar_email_smtp(dest) == "✅":
                    try:
                        msg = MIMEMultipart(); msg['From'] = email_rem; msg['To'] = dest
                        msg['Subject'] = assunto_t.format(empresa=emp)
                        msg.attach(MIMEText(corpo_t.format(empresa=emp, user=user_name), 'plain'))
                        
                        server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls()
                        server.login(email_rem, pass_app); server.sendmail(email_rem, [dest], msg.as_string()); server.quit()
                        
                        df_env = salvar_envio_gsheets(item["Domínio"], dest, user_name, df_env)
                        st.toast(f"✅ Sucesso: {item['Domínio']}")
                    except: 
                        st.error(f"❌ Erro crítico no envio para {dest}")
                
                # Pausa entre e-mails com contador visual
                if idx_e < len(enviar_estes) - 1:
                    t_esp = random.randint(pausa_min, pausa_max)
                    for s in range(t_esp, 0, -1):
                        status_texto.warning(f"⏳ Pausa de segurança: {s}s restantes antes do próximo envio...")
                        time.sleep(1)
        
        # Atualiza o progresso da sessão
        st.session_state.bloco_atual = idx_b + 1
        
        if usar_pausa_bloco and idx_b < len(blocos) - 1:
            for s in range(int(tempo_bloco_seg), 0, -1):
                status_texto.error(f"⏸️ Pausa entre BLOCOS: Retomando em {s}s...")
                time.sleep(1)
            
        gc.collect()

    st.session_state.running = False
    status_texto.success("🏁 TODA A CAMPANHA FOI CONCLUÍDA!")
    st.balloons()
    
