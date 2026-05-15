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

# --- VERSÃO 25 ---
st.set_page_config(page_title="GD Control Center - Final", page_icon="🖥️", layout="wide")

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

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--single-process"])
            page = browser.new_page(user_agent="Mozilla/5.0")
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
            try:
                page.goto(url, timeout=25000, wait_until="domcontentloaded")
                time.sleep(2)
                raw = re.findall(regex_padrao, page.content())
                emails_encontrados.update([e.replace('[at]', '@').replace('(at)', '@').replace(' ', '').lower() for e in raw])
                
                if not emails_encontrados:
                    links = page.query_selector_all("a")
                    for link in links:
                        href = link.get_attribute("href")
                        if href and any(p in href.lower() for p in ['contact', 'contato', 'about', 'team']):
                            target = href if href.startswith('http') else url.rstrip('/') + '/' + href.lstrip('/')
                            page.goto(target, timeout=20000); time.sleep(2)
                            raw_sub = re.findall(regex_padrao, page.content())
                            emails_encontrados.update([e.replace('[at]', '@').replace('(at)', '@').replace(' ', '').lower() for e in raw_sub])
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
# 3. INTERFACE
# ==========================================
with st.sidebar:
    st.header("👤 Perfil GD")
    user_name = st.text_input("Teu Nome", value="Gonçalo")
    email_rem = st.text_input("Teu Email", value="goncalo@gd-advertising.com")
    pass_app = st.text_input("App Password", type="password")
    
    email_bcc = st.text_input("BCC (Cópia Oculta)", value="goncalo.dias@g13advertising.com")
    
    st.divider()
    # --- BOTÃO DE REENVIO ADICIONADO AQUI ---
    permitir_reenvio = st.toggle("🔄 Permitir Reenvio (Ignorar Histórico)", value=False)
    
    st.divider()
    pausa_min = st.number_input("Pausa E-mails Min (seg)", value=180)
    pausa_max = st.number_input("Pausa E-mails Max (seg)", value=420)
    st.divider()
    usar_pausa_bloco = st.toggle("Pausa entre Blocos", value=True)
    tempo_bloco_seg = st.number_input("Segundos de Pausa", value=600)
    tamanho_bloco = st.number_input("Tamanho do Bloco", value=30, min_value=1)

st.title("🖥️ GD Advertising - Control Center (Final)")

txt = st.file_uploader("Upload domínios (.txt)", type=['txt'])
alvos_total = [l.strip() for l in txt.getvalue().decode("utf-8").split("\n") if l.strip()] if txt else []

tabs = st.tabs(["🇺🇸 EN", "🇵🇹 PT", "🇪🇸 ES", "🇮🇹 IT", "🇫🇷 FR", "🇰🇷 KR", "🇯🇵 JP"])

# --- LÓGICA DE ATIVAÇÃO DE IDIOMAS E VARIANTES ---
idiomas_ativos = {}

def lang_inputs(tab, lang_code, def_subj, def_body):
    with tab:
        ativo = st.checkbox(f"Ativar idioma {lang_code}", value=True)
        if ativo:
            idiomas_ativos[lang_code] = True
            
        st.markdown("📝 **Variante 1 (Principal)**")
        s1 = st.text_input(f"Assunto 1 ({lang_code})", value=def_subj, disabled=not ativo)
        b1 = st.text_area(f"Mensagem 1 ({lang_code})", value=def_body, disabled=not ativo, height=120)
        
        with st.expander("➕ Adicionar Variante 2 (Anti-Spam)"):
            s2 = st.text_input(f"Assunto 2 ({lang_code})", value="", disabled=not ativo)
            b2 = st.text_area(f"Mensagem 2 ({lang_code})", value="", disabled=not ativo, height=120)
            
        with st.expander("➕ Adicionar Variante 3 (Anti-Spam)"):
            s3 = st.text_input(f"Assunto 3 ({lang_code})", value="", disabled=not ativo)
            b3 = st.text_area(f"Mensagem 3 ({lang_code})", value="", disabled=not ativo, height=120)
            
        # Filtra apenas as variantes que foram preenchidas
        assuntos = [s for s in [s1, s2, s3] if s.strip()]
        corpos = [b for b in [b1, b2, b3] if b.strip()]
        
        # Fallback de segurança se apagar tudo
        if not assuntos: assuntos = [def_subj]
        if not corpos: corpos = [def_body]
        
        return assuntos, corpos

# Inicializar abas com CAIXAS DISTINTAS
sub_en, body_en = lang_inputs(tabs[0], "EN", "Partnership with {empresa}", "Hi {empresa}, I'm {user}...")
sub_pt, body_pt = lang_inputs(tabs[1], "PT", "Parceria com a {empresa}", "Olá {empresa}, sou o {user}...")
sub_es, body_es = lang_inputs(tabs[2], "ES", "Alianza con {empresa}", "Hola {empresa}, soy {user}...")
sub_it, body_it = lang_inputs(tabs[3], "IT", "Collaborazione con {empresa}", "Ciao {empresa}, sono {user}...")
sub_fr, body_fr = lang_inputs(tabs[4], "FR", "Partenariat avec {empresa}", "Bonjour {empresa}, je suis {user}...")
sub_kr, body_kr = lang_inputs(tabs[5], "KR", "{empresa} 파트너십 제안", "{empresa} 안녕하세요, {user}입니다...")
sub_jp, body_jp = lang_inputs(tabs[6], "JP", "{empresa} との提携について", "{empresa} 様, 初めまして {user} と申します...")

# ==========================================
# 4. EXECUÇÃO COM LOGS DETALHADOS E FALLBACK
# ==========================================
def escolher_idioma(dominio):
    ext = dominio.split('.')[-1].lower()
    mapping = {'pt':'PT','br':'PT','es':'ES','mx':'ES','co':'ES','it':'IT','fr':'FR','kr':'KR','jp':'JP'}
    return mapping.get(ext, 'EN')

if st.button("🚀 INICIAR PIPELINE FINAL", type="primary", use_container_width=True):
    st.session_state.running = True

if st.session_state.running and alvos_total:
    mapa_idiomas = {
        "EN": {"assuntos": sub_en, "corpos": body_en},
        "PT": {"assuntos": sub_pt, "corpos": body_pt},
        "ES": {"assuntos": sub_es, "corpos": body_es},
        "IT": {"assuntos": sub_it, "corpos": body_it},
        "FR": {"assuntos": sub_fr, "corpos": body_fr},
        "KR": {"assuntos": sub_kr, "corpos": body_kr},
        "JP": {"assuntos": sub_jp, "corpos": body_jp}
    }
    
    blocos = [alvos_total[i:i + tamanho_bloco] for i in range(0, len(alvos_total), tamanho_bloco)]
    
    for idx_b in range(st.session_state.bloco_atual, len(blocos)):
        bloco = blocos[idx_b]
        st.markdown(f"--- \n### 📦 BLOCO {idx_b + 1} / {len(blocos)}")
        
        df_env, df_cac = get_db_data()
        cache_dict = dict(zip(df_cac['Dominio'], df_cac['Emails_Encontrados']))
        
        dados_bloco = []
        novos_cac = []
        
        barra_prog = st.progress(0)
        status_txt = st.empty()
        
        # --- FASE 1: INVESTIGAÇÃO (AGORA INVESTIGA TUDO) ---
        for i, dom in enumerate(bloco):
            posicao = f"({i+1}/{len(bloco)})"
            
            idiomas_sel = list(idiomas_ativos.keys())
            if len(idiomas_sel) == 0:
                status_txt.error("⚠️ Nenhum idioma selecionado! Cancela a operação ou seleciona pelo menos um.")
                break

            # LÓGICA DE REENVIO / HISTÓRICO
            if permitir_reenvio:
                ja_enviado = False
            else:
                ja_enviado = not df_env.empty and dom in df_env[df_env['Enviado_Por'] == user_name]['Dominio'].values
            
            if ja_enviado:
                status_txt.warning(f"⏭️ {posicao} Ignorado: {dom} (Já enviado anteriormente)")
            else:
                if dom in cache_dict:
                    email_cache = str(cache_dict[dom])
                    status_txt.info(f"⚡ {posicao} Recuperado do Cache: {dom} ⮕ {email_cache}")
                    dados_bloco.append({"Domínio": dom, "Email": email_cache})
                else:
                    status_txt.text(f"🌐 {posicao} Scrapping Ativo: {dom}...")
                    em = investigar_site(dom)
                    status_txt.success(f"🔍 {posicao} Resultado do Scrape: {dom} ⮕ {em}")
                    dados_bloco.append({"Domínio": dom, "Email": em})
                    novos_cac.append({"Dominio": dom, "Emails_Encontrados": em})
                    cache_dict[dom] = em
            
            barra_prog.progress((i + 1) / len(bloco))
            time.sleep(0.1) 

        status_txt.text("💾 Sincronizando descobertas com a Google Sheet...")
        df_cac = salvar_cache_lote_gsheets(novos_cac, df_cac)
        
        # --- FASE 2: ENVIOS COM LÓGICA FALLBACK E VARIANTES ---
        enviar_estes = [d for d in dados_bloco if d.get("Email") and "@" in str(d["Email"])]
        
        if enviar_estes:
            st.markdown(f"**📧 Iniciando disparos para {len(enviar_estes)} e-mails encontrados no bloco...**")
            for idx_e, item in enumerate(enviar_estes):
                pos_envio = f"({idx_e+1}/{len(enviar_estes)})"
                dest = str(item["Email"]).split(',')[0].strip()
                dom = item["Domínio"]
                emp = dom.replace('www.','').split('.')[0].capitalize()
                
                idiomas_sel = list(idiomas_ativos.keys())
                
                # --- LÓGICA INTELIGENTE DE IDIOMA E DEFAULT ENGLISH ---
                if len(idiomas_sel) == 1:
                    # Regra 1: Só 1 idioma ativo -> Força esse idioma
                    idioma = idiomas_sel[0]
                    
                    # Usa a lista das Variantes de forma aleatória
                    esc_assunto = random.choice(mapa_idiomas[idioma]["assuntos"]).strip().format(empresa=emp, user=user_name)
                    esc_corpo = random.choice(mapa_idiomas[idioma]["corpos"]).strip().format(empresa=emp, user=user_name)
                    tag_idioma = idioma
                else:
                    # Regra 2: Múltiplos idiomas ativos -> Verifica o domínio
                    idioma_detetado = escolher_idioma(dom)
                    if idioma_detetado in idiomas_sel:
                        idioma = idioma_detetado
                        esc_assunto = random.choice(mapa_idiomas[idioma]["assuntos"]).strip().format(empresa=emp, user=user_name)
                        esc_corpo = random.choice(mapa_idiomas[idioma]["corpos"]).strip().format(empresa=emp, user=user_name)
                        tag_idioma = idioma
                    else:
                        # Regra 3: Domínio de idioma inativo (ou desconhecido) -> Manda DEFAULT
                        tag_idioma = "DEFAULT-EN"
                        esc_assunto = f"Partnership with {empresa}"
                        esc_corpo = f"""Hi {empresa} Team,

Are you currently accepting new direct display partnerships?

I’m Gonçalo from Clever Advertising. We have a dedicated budget for Tier-1 Fintech and Trading brands and are highly interested in buying ad space directly on {empresa}.

Why publishers work with us:
Fixed CPM or Flat Fee (Zero CPA or rev-share risk).
100% Prepayment for the initial test month.
Seamless Tech: 100% Brand Safe HTML5 tags (GAM compatible).

Could you share your latest media kit and rate card?

Best, 
Gonçalo Dias 
Media Buyer | Clever Advertising"""
                # ---------------------------------------------------
                
                status_txt.text(f"📧 {pos_envio} Validando e Enviando: {dest} [{tag_idioma}]...")
                
                if validar_email_smtp(dest) == "✅":
                    try:
                        msg = MIMEMultipart(); msg['From'] = email_rem; msg['To'] = dest
                        msg['Subject'] = esc_assunto
                        msg.attach(MIMEText(esc_corpo, 'plain'))
                        
                        destinatarios = [dest]
                        if email_bcc:
                            destinatarios.append(email_bcc)
                        
                        server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls()
                        server.login(email_rem, pass_app)
                        server.sendmail(email_rem, destinatarios, msg.as_string())
                        server.quit()
                        
                        df_env = salvar_envio_gsheets(dom, dest, user_name, df_env)
                        st.success(f"✅ {pos_envio} Sucesso: {dom} (E-mail: {dest})")
                    except Exception as e: 
                        st.error(f"❌ {pos_envio} Falha no envio para {dest}: {e}")
                else:
                    st.warning(f"⚠️ {pos_envio} Saltado: {dest} parece ser um e-mail inválido ou inexistente.")

                if idx_e < len(enviar_estes) - 1:
                    t_esp = random.randint(pausa_min, pausa_max)
                    for s in range(t_esp, 0, -1):
                        status_txt.warning(f"⏳ Pausa Anti-Spam {pos_envio}: {s}s para o próximo e-mail...")
                        time.sleep(1)
        
        st.session_state.bloco_atual = idx_b + 1
        
        if usar_pausa_bloco and idx_b < len(blocos) - 1:
            st.error(f"⏸️ BLOCO {idx_b+1} FINALIZADO. Entrando em pausa estratégica...")
            for s in range(int(tempo_bloco_seg), 0, -1):
                status_txt.metric("Retomando Pipeline em:", f"{s}s", f"Bloco Seguinte: {idx_b+2}")
                time.sleep(1)
            status_txt.empty()
            
        gc.collect()

    st.session_state.running = False
    st.balloons()
    
