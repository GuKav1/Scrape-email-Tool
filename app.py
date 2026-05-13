import streamlit as st
from streamlit_gsheets import GSheetsConnection
import warnings
import os
import datetime
import gc

# --- INSTALAÇÃO FORÇADA NA CLOUD ---
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

# --- SILENCIADOR DE AVISOS ---
warnings.filterwarnings("ignore")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="GD Cascading Pipeline", page_icon="⚡", layout="wide")

URL_FOLHA = "https://docs.google.com/spreadsheets/d/1Yq3Vo-yaNrSyBkVLxETB6nNrqGSoefJ6-rtIwHHjabU/edit?usp=sharing"

# ==========================================
# 1. FUNÇÕES DE BASE DE DADOS (GOOGLE SHEETS)
# ==========================================
def get_db_data():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        try:
            df_env = conn.read(spreadsheet=URL_FOLHA, worksheet="Enviados").dropna(how="all")
        except:
            df_env = pd.DataFrame(columns=['Data', 'Dominio', 'Email', 'Enviado_Por'])
        try:
            df_cac = conn.read(spreadsheet=URL_FOLHA, worksheet="Cache").dropna(how="all")
        except:
            df_cac = pd.DataFrame(columns=['Dominio', 'Emails_Encontrados'])
        return df_env, df_cac
    except Exception:
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
# 2. MOTOR DE INVESTIGAÇÃO (ESTÁVEL)
# ==========================================
def investigar_site(dominio):
    url = 'https://' + dominio if not dominio.startswith('http') else dominio
    resultado = "N/A"
    try:
        with sync_playwright() as p:
            # Launcher ultra-estável para Cloud
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            page = context.new_page()
            
            # Bloqueio de lixo visual
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())
            
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)
                html = page.content()
                emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html)
                emails_limpos = list(set([e.lower() for e in emails if dominio.split('.')[0] in e.lower() or 'gmail' in e.lower() or 'contact' in e.lower() or 'info' in e.lower()]))
                if emails_limpos:
                    resultado = ", ".join(emails_limpos[:2])
            except:
                pass
            
            # O Context Manager 'with' fecha tudo automaticamente aqui, evitando o erro de loop
    except Exception:
        pass
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
with st.sidebar:
    st.header("👤 Perfil")
    user_name = st.text_input("Teu Nome", value="Gonçalo")
    email_rem = st.text_input("Teu Email", value="goncalo@gd-advertising.com")
    pass_app = st.text_input("App Password", type="password")
    
    st.divider()
    pausa_min = st.number_input("Pausa Min (seg)", value=180)
    pausa_max = st.number_input("Pausa Max (seg)", value=420)
    tamanho_bloco = st.slider("Tamanho do Bloco (Sites)", 10, 200, 75)

st.title("⚡ GD Advertising - Cascading Pipeline")
col1, col2 = st.columns(2)

with col1:
    txt = st.file_uploader("Upload domínios (.txt)", type=['txt'])
    alvos_total = [l.strip() for l in txt.getvalue().decode("utf-8").split("\n") if l.strip()] if txt else []

with col2:
    assunto_t = st.text_input("Assunto", value="Partnership with {empresa}")
    corpo_t = st.text_area("Mensagem", height=150, value="Hello {empresa}, I'm {user}...")

# ==========================================
# 4. EXECUÇÃO EM CASCATA
# ==========================================
if st.button("🚀 INICIAR PIPELINE EM CASCATA", type="primary", use_container_width=True) and alvos_total:
    blocos = [alvos_total[i:i + tamanho_bloco] for i in range(0, len(alvos_total), tamanho_bloco)]
    st.info(f"📋 {len(alvos_total)} sites divididos em {len(blocos)} blocos de {tamanho_bloco}.")
    
    for idx_b, bloco in enumerate(blocos):
        st.subheader(f"📦 Bloco {idx_b + 1} de {len(blocos)}")
        
        # Sincronizar DB
        df_env, df_cac = get_db_data()
        cache_dict = dict(zip(df_cac['Dominio'], df_cac['Emails_Encontrados'])) if not df_cac.empty else {}
        
        # SCRAPE DO BLOCO
        dados_bloco = []
        novos_cac = []
        p_scrape = st.progress(0)
        log_s = st.empty()
        
        for i, dom in enumerate(bloco):
            # Filtro: Eu já enviei?
            if not df_env.empty and dom in df_env[df_env['Enviado_Por'] == user_name]['Dominio'].values:
                log_s.text(f"⏭️ Ignorado (Já enviado): {dom}")
            else:
                if dom in cache_dict:
                    log_s.text(f"⚡ Cache: {dom}")
                    dados_bloco.append({"Domínio": dom, "Email": cache_dict[dom]})
                else:
                    log_s.text(f"🌐 Scrapping: {dom}")
                    em = investigar_site(dom)
                    dados_bloco.append({"Domínio": dom, "Email": em})
                    novos_cac.append({"Dominio": dom, "Emails_Encontrados": em})
                    cache_dict[dom] = em
            p_scrape.progress((i + 1) / len(bloco))
        
        # Salva cache do bloco
        df_cac = salvar_cache_lote_gsheets(novos_cac, df_cac)
        
        # ENVIO DO BLOCO
        validos_bloco = [d for d in dados_bloco if "@" in d["Email"]]
        if validos_bloco:
            st.write(f"📨 Encontrados {len(validos_bloco)} e-mails. Iniciando envios...")
            for idx_e, item in enumerate(validos_bloco):
                dest = item["Email"].split(',')[0].strip()
                emp = item["Domínio"].replace('www.','').split('.')[0].capitalize()
                
                if validar_email_smtp(dest) == "✅":
                    try:
                        msg = MIMEMultipart()
                        msg['From'] = email_rem
                        msg['To'] = dest
                        msg['Subject'] = assunto_t.format(empresa=emp)
                        msg.attach(MIMEText(corpo_t.format(empresa=emp, user=user_name), 'plain'))
                        
                        server = smtplib.SMTP('smtp.gmail.com', 587)
                        server.starttls()
                        server.login(email_rem, pass_app)
                        server.sendmail(email_rem, [dest], msg.as_string())
                        server.quit()
                        
                        df_env = salvar_envio_gsheets(item["Domínio"], dest, user_name, df_env)
                        st.success(f"✅ Bloco {idx_b+1} | Enviado: {item['Domínio']}")
                    except Exception as e:
                        st.error(f"❌ Erro no envio: {e}")
                
                # Pausa entre e-mails (exceto no último do bloco final)
                if idx_e < len(validos_bloco) - 1:
                    t_esp = random.randint(pausa_min, pausa_max)
                    timer = st.empty()
                    for s in range(t_esp, 0, -1):
                        timer.metric("Próximo envio em:", f"{s}s", f"Bloco {idx_b+1}")
                        time.sleep(1)
                    timer.empty()
        
        st.write(f"✔️ Bloco {idx_b + 1} concluído.")
        gc.collect()

    st.balloons()
    
