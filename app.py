import streamlit as st
from streamlit_gsheets import GSheetsConnection
import warnings
import os
import datetime
import gc
import random

# --- INSTALAÇÃO FORÇADA ---
os.system("playwright install chromium")

import socket
import pandas as pd
import time
import re
import urllib3
import dns.resolver
import smtplib
from playwright.sync_api import sync_playwright
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURAÇÕES ---
warnings.filterwarnings("ignore")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

st.set_page_config(page_title="GD Polyglot Stable Pro", page_icon="🌐", layout="wide")

URL_FOLHA = "https://docs.google.com/spreadsheets/d/1Yq3Vo-yaNrSyBkVLxETB6nNrqGSoefJ6-rtIwHHjabU/edit?usp=sharing"

if 'running' not in st.session_state: st.session_state.running = False
if 'bloco_atual' not in st.session_state: st.session_state.bloco_atual = 0

# ==========================================
# 1. FUNÇÕES DE BASE DE DADOS
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
    except: return df_atual

def salvar_cache_lote_gsheets(lista_novos_caches, df_atual):
    if not lista_novos_caches: return df_atual
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        novas_linhas = pd.DataFrame(lista_novos_caches)
        df_final = pd.concat([df_atual, novas_linhas], ignore_index=True).drop_duplicates(subset=['Dominio'], keep='last')
        conn.update(spreadsheet=URL_FOLHA, worksheet="Cache", data=df_final)
        return df_final
    except: return df_atual

# ==========================================
# 2. MOTOR DE INVESTIGAÇÃO
# ==========================================
def investigar_site(dominio):
    url = 'https://' + dominio if not dominio.startswith('http') else dominio
    emails_encontrados = set()
    regex_padrao = r'[a-zA-Z0-9_.+-]+(?:\s?\[at\]\s?|\s?\(at\)\s?|@)[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'

    def extrair_e_limpar(html_content):
        raw = re.findall(regex_padrao, html_content)
        return [e.replace('[at]', '@').replace('(at)', '@').replace(' ', '').lower() for e in raw if "@" in e or "[at]" in e or "(at)" in e]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--single-process"])
            page = browser.new_page(user_agent="Mozilla/5.0")
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
            try:
                page.goto(url, timeout=25000, wait_until="domcontentloaded")
                time.sleep(2)
                emails_encontrados.update(extrair_e_limpar(page.content()))
                if not emails_encontrados:
                    links = page.query_selector_all("a")
                    for link in links:
                        href = link.get_attribute("href")
                        if href and any(p in href.lower() for p in ['contact', 'contato', 'about', 'team', 'info']):
                            target = href if href.startswith('http') else url.rstrip('/') + '/' + href.lstrip('/')
                            page.goto(target, timeout=20000); time.sleep(2)
                            emails_encontrados.update(extrair_e_limpar(page.content()))
                            break
            except: pass
            browser.close()
    except: pass
    finally: gc.collect()
    return ", ".join(list(emails_encontrados)[:2]) if emails_encontrados else "N/A"

def validar_email_smtp(email):
    try:
        email_str = str(email).split(',')[0].strip()
        dom = email_str.split('@')[1]
        mx = dns.resolver.resolve(dom, 'MX')
        server = smtplib.SMTP(timeout=5); server.connect(str(mx[0].exchange))
        server.helo(socket.gethostname()); server.mail('goncalo.dias@cleveradvertising.com')
        code, _ = server.rcpt(email_str); server.quit()
        return "✅" if code == 250 else "❌"
    except: return "❓"

# ==========================================
# 3. INTERFACE POLIGLOTA
# ==========================================
with st.sidebar:
    st.header("👤 Perfil GD")
    user_name = st.text_input("Teu Nome", value="Gonçalo")
    email_rem = st.text_input("Teu Email", value="goncalo@gd-advertising.com")
    pass_app = st.text_input("App Password", type="password")
    
    st.divider()
    st.subheader("⏱️ Temporizadores")
    pausa_min = st.number_input("Pausa E-mails Min (seg)", value=180)
    pausa_max = st.number_input("Pausa E-mails Max (seg)", value=420)
    
    st.divider()
    usar_pausa_bloco = st.toggle("Pausa entre Blocos", value=True)
    tempo_bloco_seg = st.number_input("Segundos de Pausa", value=600)
    
    # --- AQUI ESTÁ A TUA MUDANÇA: VALOR EXATO ---
    tamanho_bloco = st.number_input("Tamanho do Bloco (Ex: 30, 40, 100)", value=30, step=1, min_value=1)

st.title("🌍 GD Advertising - International Turbo")

txt = st.file_uploader("Upload domínios (.txt)", type=['txt'])
alvos_total = [l.strip() for l in txt.getvalue().decode("utf-8").split("\n") if l.strip()] if txt else []

tabs = st.tabs(["🇺🇸 EN", "🇵🇹 PT", "🇪🇸 ES", "🇮🇹 IT", "🇫🇷 FR", "🇰🇷 KR", "🇯🇵 JP"])

def lang_inputs(tab, lang_code, def_subj, def_body):
    with tab:
        subj = st.text_area(f"Assuntos {lang_code} (separa com [VARIANTE])", value=def_subj)
        body = st.text_area(f"Mensagens {lang_code} (separa com [VARIANTE])", value=def_body)
        return subj, body

sub_en, body_en = lang_inputs(tabs[0], "EN", "Partnership with {empresa}", "Hi {empresa}...")
sub_pt, body_pt = lang_inputs(tabs[1], "PT", "Parceria com a {empresa}", "Olá {empresa}...")
sub_es, body_es = lang_inputs(tabs[2], "ES", "Alianza con {empresa}", "Hola {empresa}...")
sub_it, body_it = lang_inputs(tabs[3], "IT", "Collaborazione {empresa}", "Ciao {empresa}...")
sub_fr, body_fr = lang_inputs(tabs[4], "FR", "Partenariat {empresa}", "Bonjour {empresa}...")
sub_kr, body_kr = lang_inputs(tabs[5], "KR", "{empresa} 파트너십", "{empresa} 안녕하세요...")
sub_jp, body_jp = lang_inputs(tabs[6], "JP", "{empresa} との提携", "{empresa} 様...")

# ==========================================
# 4. LÓGICA DE DETECÇÃO E EXECUÇÃO
# ==========================================
def escolher_idioma(dominio):
    ext = dominio.split('.')[-1].lower()
    mapping = {'pt':'PT','br':'PT','es':'ES','mx':'ES','co':'ES','it':'IT','fr':'FR','kr':'KR','jp':'JP'}
    return mapping.get(ext, 'EN')

if st.button("🚀 INICIAR PIPELINE FINAL", type="primary", use_container_width=True):
    st.session_state.running = True
    st.session_state.bloco_atual = 0 # Reinicia se clicar de novo

if st.session_state.running and alvos_total:
    mapa_idiomas = {
        "EN": {"assuntos": sub_en.split("[VARIANTE]"), "corpos": body_en.split("[VARIANTE]")},
        "PT": {"assuntos": sub_pt.split("[VARIANTE]"), "corpos": body_pt.split("[VARIANTE]")},
        "ES": {"assuntos": sub_es.split("[VARIANTE]"), "corpos": body_es.split("[VARIANTE]")},
        "IT": {"assuntos": sub_it.split("[VARIANTE]"), "corpos": body_it.split("[VARIANTE]")},
        "FR": {"assuntos": sub_fr.split("[VARIANTE]"), "corpos": body_fr.split("[VARIANTE]")},
        "KR": {"assuntos": sub_kr.split("[VARIANTE]"), "corpos": body_kr.split("[VARIANTE]")},
        "JP": {"assuntos": sub_jp.split("[VARIANTE]"), "corpos": body_jp.split("[VARIANTE]")}
    }
    
    blocos = [alvos_total[i:i + tamanho_bloco] for i in range(0, len(alvos_total), tamanho_bloco)]
    
    for idx_b in range(st.session_state.bloco_atual, len(blocos)):
        bloco = blocos[idx_b]
        st.markdown(f"### 📦 Bloco {idx_b + 1} de {len(blocos)} (Tamanho: {len(bloco)})")
        
        df_env, df_cac = get_db_data()
        cache_dict = dict(zip(df_cac['Dominio'], df_cac['Emails_Encontrados']))
        
        dados_bloco = []
        novos_cac = []
        barra_prog = st.progress(0); status_txt = st.empty()
        
        for i, dom in enumerate(bloco):
            ja_enviado = not df_env.empty and dom in df_env[df_env['Enviado_Por'] == user_name]['Dominio'].values
            
            if ja_enviado:
                status_txt.warning(f"⏭️ {dom} já enviado anteriormente por ti. Ignorando...")
            else:
                if dom in cache_dict:
                    status_txt.info(f"⚡ Cache: {dom}")
                    dados_bloco.append({"Domínio": dom, "Email": str(cache_dict[dom])})
                else:
                    status_txt.text(f"🌐 Investigando: {dom}...")
                    em = investigar_site(dom)
                    dados_bloco.append({"Domínio": dom, "Email": em})
                    novos_cac.append({"Dominio": dom, "Emails_Encontrados": em})
                    cache_dict[dom] = em
            barra_prog.progress((i + 1) / len(bloco))
        
        df_cac = salvar_cache_lote_gsheets(novos_cac, df_cac)
        enviar_estes = [d for d in dados_bloco if d.get("Email") and "@" in str(d["Email"])]
        
        for idx_e, item in enumerate(enviar_estes):
            dest = str(item["Email"]).split(',')[0].strip()
            dom = item["Domínio"]
            emp = dom.replace('www.','').split('.')[0].capitalize()
            
            idioma = escolher_idioma(dom)
            esc_assunto = random.choice(mapa_idiomas[idioma]["assuntos"]).strip().format(empresa=emp, user=user_name)
            esc_corpo = random.choice(mapa_idiomas[idioma]["corpos"]).strip().format(empresa=emp, user=user_name)
            
            status_txt.text(f"📧 [{idioma}] Enviando para: {dest}")
            
            if validar_email_smtp(dest) == "✅":
                try:
                    msg = MIMEMultipart(); msg['From'] = email_rem; msg['To'] = dest
                    msg['Subject'] = esc_assunto
                    msg.attach(MIMEText(esc_corpo, 'plain'))
                    
                    server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls()
                    server.login(email_rem, pass_app); server.sendmail(email_rem, [dest, "goncalo.dias@g13advertising.com"], msg.as_string()); server.quit()
                    
                    df_env = salvar_envio_gsheets(dom, dest, user_name, df_env)
                    st.toast(f"✅ Sucesso ({idioma}): {dom}")
                except Exception as e: st.error(f"❌ Erro: {e}")
            
            if idx_e < len(enviar_estes) - 1:
                t_esp = random.randint(pausa_min, pausa_max)
                for s in range(t_esp, 0, -1):
                    status_txt.warning(f"⏳ Pausa {idioma}: {s}s")
                    time.sleep(1)
        
        st.session_state.bloco_atual = idx_b + 1
        
        if usar_pausa_bloco and idx_b < len(blocos) - 1:
            for s in range(int(tempo_bloco_seg), 0, -1):
                status_txt.error(f"⏸️ Pausa entre Blocos: {s}s")
                time.sleep(1)
            
        gc.collect()

    st.session_state.running = False
    st.balloons()
    
