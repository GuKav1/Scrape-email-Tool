import streamlit as st
import warnings
import os

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
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)
            html = page.content()
            
            # Procura emails no HTML
            emails = re.findall(r'[a-zA-
