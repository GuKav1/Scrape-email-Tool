import streamlit as st
import warnings
import os
import json

# --- INSTALAÇÃO FORÇADA DO NAVEGADOR NA CLOUD ---
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
ARQUIVO_CACHE_SCRAPE = "cache_scrape.json"

# ==========================================
# FUNÇÕES DE LÓGICA (Scrape, Validação, Memória)
# ==========================================
def carregar_emails_enviados():
    if not os.path.exists(ARQUIVO_MEMORIA): return set()
    with open(ARQUIVO_MEMORIA, 'r') as f: return set(f.read().splitlines())

def registar_envio(email):
    with open(ARQUIVO_MEMORIA, 'a') as f: f.write(email + '\n')

def carregar_cache_scrape():
    if not os.path.exists(ARQUIVO_CACHE_SCRAPE): return {}
    try:
        with open(ARQUIVO_CACHE_SCRAPE, 'r') as f: return json.load(f)
    except: return {}

def guardar_cache_scrape(cache_dict):
    with open(ARQUIVO_CACHE_SCRAPE, 'w') as f: json.dump(cache_dict, f)

def investigar_site(dominio):
    url = 'https://' + dominio if not dominio.startswith('http') else dominio
    dados = {"Domínio": dominio, "Emails_Site": "N/A", "Email_Status": "Pendente"}
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            
            # Bloqueia imagens e vídeos para não estoirar a memória da Cloud
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())
            
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)
            html = page.content()
            
            # Procura emails no HTML
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html)
            emails_limpos = list(set([e.lower() for e in emails if dominio.split('.')[0] in e.lower() or 'gmail' in e.lower() or 'contact' in e.lower() or 'info' in e.lower()]))
            
            if emails_limpos:
                dados["Emails_Site"] = ", ".join(emails_limpos[:2])
                
            browser.close()
            
    except Exception as e:
        st.error(f"⚠️ Erro a ler o site {dominio}: {e}")
        
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
            
