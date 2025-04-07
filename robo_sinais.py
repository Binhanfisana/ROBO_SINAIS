import asyncio
import time
from solana.rpc.api import Client
from solders.pubkey import Pubkey as PublicKey
import requests
import numpy as np
import talib
from base58 import b58decode
from telegram import Bot
import matplotlib.pyplot as plt
import io
import os
import ccxt
from dotenv import load_dotenv 

load_dotenv() #caregar variaveis

# ========== CONFIGURAÇÕES ==========
wallet_address = "CiYJqkSdUpPcU6MWgZtEWkmVLxoorBMvpx5wCZXpwT2E"  # Endereço da sua carteira
TOKEN_TELEGRAM = os.getenv("TELEGRAM_TOKEN") 
CHAT_ID = os.getenv("CHAT_ID")                                           
BINANCE_SYMBOL = "SOL/USDT"                                          # Par SOL/USDT
API_KEY = "SUA_API_KEY"                                              # API Key da Binance
API_SECRET = "SUA_SECRET_KEY"                                        # Secret Key da Binance
QUANTIDADE_OPERAR = 0.1                                              # Quantidade de SOL para operar
# ====================================

# --- Parte 1: Conexão com Solana e verificação de saldo ---
def validar_chave(wallet_address):
    try:
        decoded_address = b58decode(wallet_address)
        if len(decoded_address) != 32:
            raise ValueError("Endereço inválido! Deve ter 32 bytes.")
        return PublicKey(decoded_address)
    except Exception as e:
        print(f"Erro ao validar chave pública: {e}")
        return None

solana_client = Client("https://api.mainnet-beta.solana.com")

def verificar_saldo(wallet):
    try:
        public_key = validar_chave(wallet)
        if not public_key:
            return None
        saldo = solana_client.get_balance(public_key).value / 1e9
        print(f"Saldo da carteira: {saldo} SOL")
        return saldo
    except Exception as e:
        print(f"Erro ao verificar saldo: {e}")
        return None

# --- Parte 2: Obtenção do preço em tempo real via ccxt ---
def obter_preco_em_tempo_real():
    try:
        exchange = ccxt.binance()
        ticker = exchange.fetch_ticker(BINANCE_SYMBOL)
        return ticker['last']
    except Exception as e:
        print(f"Erro ao obter preço: {e}")
        return None

# --- Parte 3: Obtenção de dados históricos em tempo real ---
def obter_dados_historicos():
    try:
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv(BINANCE_SYMBOL, timeframe="1h", limit=100)
        precos = [candle[4] for candle in ohlcv]  # Preços de fechamento
        return np.array(precos)
    except Exception as e:
        print(f"Erro ao obter dados históricos: {e}")
        return None

# --- Parte 4: Cálculo de indicadores técnicos ---
def calcular_indicadores(precos_historicos):
    try:
        media_movel = talib.SMA(precos_historicos, timeperiod=5)
        rsi = talib.RSI(precos_historicos, timeperiod=14)
        print(f"Média Móvel: {media_movel[-10:] if media_movel is not None else 'Erro ao calcular Média Móvel'}")
        print(f"RSI: {rsi[-10:] if rsi is not None else 'Erro ao calcular RSI'}")
        return media_movel, rsi
    except Exception as e:
        print(f"Erro ao calcular indicadores: {e}")
        return None, None

# --- Parte 5: Geração do gráfico ---
def gerar_grafico(precos_historicos, media_movel):
    plt.figure(figsize=(10, 5))
    plt.plot(precos_historicos, label='Preços Históricos', marker='o')
    if media_movel is not None:
        plt.plot(media_movel, label='Média Móvel', linestyle='--', marker='x')
    plt.title("Histórico de Preços e Média Móvel (dados reais)")
    plt.xlabel("Período")
    plt.ylabel("Preço (USDT)")
    plt.legend()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

# --- Parte 6: Geração do sinal de trading ---
def gerar_sinal(preco_atual, media_movel, rsi):
    sinal = "NEUTRO"
    if media_movel is not None and rsi is not None:
        print(f"Preço Atual: {preco_atual}, Última Média Móvel: {media_movel[-1]}, Último RSI: {rsi[-1]}")
        if preco_atual > media_movel[-1] and rsi[-1] < 40:  # Flexibilizado
            sinal = "COMPRA"
        elif preco_atual < media_movel[-1] and rsi[-1] > 60:  # Flexibilizado
            sinal = "VENDA"
    else:
        print("Erro: Média Móvel ou RSI não disponíveis para cálculo do sinal.")
    return sinal

# --- Parte 7: Envio do sinal e gráfico para o Telegram ---
async def enviar_sinal_telegram(sinal, preco_atual, precos_historicos, media_movel, rsi, saldo):
    try:
        bot = Bot(token=TOKEN_TELEGRAM)
        
        # Organizando as informações
        mensagem = (
            f"🚀 **Sinal de Trading** 🚀\n\n"
            f"**Sinal:** {sinal}\n"
            f"**Preço Atual:** {preco_atual:.2f} USDT\n"
            f"**Saldo da Carteira:** {saldo:.4f} SOL\n\n"
            f"**Indicadores Técnicos:**\n"
            f"- Média Móvel (Última): {media_movel[-1]:.2f}\n"
            f"- RSI (Último): {rsi[-1]:.2f}\n\n"
            f"📊 **Dados Históricos:**\n"
            f"Últimos 5 Preços:\n"
            f"{', '.join([f'{preco:.2f}' for preco in precos_historicos[-5:]])}\n\n"
            f"#Solana #Crypto"
        )
        
        # Gerando o gráfico
        grafico = gerar_grafico(precos_historicos, media_movel)
        
        # Enviando o gráfico com as informações organizadas
        await bot.send_photo(chat_id=CHAT_ID, photo=grafico, caption=mensagem, parse_mode="Markdown")
        print("Sinal, saldo, indicadores e gráfico enviados para o Telegram.")
    except Exception as e:
        print(f"Erro ao enviar mensagem no Telegram: {e}")


# --- Parte 8: Execução de ordens reais na Binance ---
def configurar_exchange():
    try:
        exchange = ccxt.binance({
            "apiKey": API_KEY,
            "secret": API_SECRET,
            "enableRateLimit": True
        })
        print("Exchange configurada com sucesso.")
        return exchange
    except Exception as e:
        print(f"Erro ao configurar a exchange: {e}")
        return None

def executar_trade_real(exchange, sinal, preco):
    try:
        if sinal == "COMPRA":
            ordem = exchange.create_market_buy_order(BINANCE_SYMBOL, QUANTIDADE_OPERAR)
            print(f"Ordem de COMPRA executada: {ordem}")
        elif sinal == "VENDA":
            ordem = exchange.create_market_sell_order(BINANCE_SYMBOL, QUANTIDADE_OPERAR)
            print(f"Ordem de VENDA executada: {ordem}")
        else:
            print("Nenhuma ação tomada, sinal neutro.")
    except Exception as e:
        print(f"Erro ao executar ordem real: {e}")

# --- Monitoramento contínuo em tempo real ---
async def monitorar_precos():
    exchange = configurar_exchange()
    if exchange is None:
        print("Erro na configuração da exchange. Não será possível executar ordens reais.")
        return

    while True:
        saldo = verificar_saldo(wallet_address)
        if saldo is None:
            print("Erro ao verificar saldo da carteira Solana.")
            continue

        precos_historicos = obter_dados_historicos()
        if precos_historicos is None:
            print("Erro ao obter dados históricos.")
            continue

        media_movel, rsi = calcular_indicadores(precos_historicos)
        if media_movel is None or rsi is None:
            print("Erro ao calcular indicadores técnicos.")
            continue

        preco_atual = obter_preco_em_tempo_real()
        if preco_atual is None:
            print("Erro ao obter preço atual.")
            continue

        sinal = gerar_sinal(preco_atual, media_movel, rsi)
        print(f"SINAL GERADO: {sinal} | Preço Atual: {preco_atual} USDT | Saldo: {saldo:.4f} SOL")

        # Corrigindo a chamada da função com todos os parâmetros necessários
        await enviar_sinal_telegram(sinal, preco_atual, precos_historicos, media_movel, rsi, saldo)

        executar_trade_real(exchange, sinal, preco_atual)

        await asyncio.sleep(60)


# --- Execução Principal ---
if __name__ == "__main__":
    asyncio.run(monitorar_precos())
