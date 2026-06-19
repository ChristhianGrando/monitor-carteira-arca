import os
import re
import html
import json
import time
import hashlib
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import feedparser


PASTA_RELATORIOS = Path("relatorios")
ARQUIVO_HISTORICO = PASTA_RELATORIOS / "ipos_enviados.json"

# Ajuste se quiser receber mais ou menos alertas.
# Quanto maior, menos alertas.
PONTUACAO_MINIMA_ALERTA = 7
LIMITE_ALERTAS_POR_EXECUCAO = 8


CONSULTAS_RSS = [
    "IPO OR oferta pública inicial OR abertura de capital OR estreia na bolsa",
    "IPO B3 OR oferta pública inicial B3 OR estreia na B3 OR prospecto IPO",
    "CVM IPO OR pedido de registro oferta pública inicial OR registro de oferta ações",
    "follow-on OR oferta subsequente OR oferta de ações OR oferta pública ações",
    "Nasdaq IPO OR NYSE IPO OR IPO market OR upcoming IPO",
    "SpaceX IPO OR Starlink IPO OR empresa prepara IPO",
    "banco coordenador IPO OR prospecto preliminar OR prospecto definitivo",
    "ações estreia bolsa IPO empresa brasileira",
]


TERMOS_IPO_FORTE = [
    "ipo",
    "oferta pública inicial",
    "oferta publica inicial",
    "abertura de capital",
    "estreia na bolsa",
    "estreia na b3",
    "pedido de registro",
    "prospecto preliminar",
    "prospecto definitivo",
    "reserva de ações",
    "reserva de acoes",
    "precificação",
    "precificacao",
    "faixa indicativa",
    "bookbuilding",
    "nasdaq ipo",
    "nyse ipo",
    "upcoming ipo",
]

TERMOS_OFERTA = [
    "follow-on",
    "oferta subsequente",
    "oferta de ações",
    "oferta de acoes",
    "oferta pública",
    "oferta publica",
    "emissão de ações",
    "emissao de acoes",
]

TERMOS_ALERTA_RISCO = [
    "adiado",
    "suspende",
    "suspendeu",
    "cancela",
    "cancelou",
    "retira pedido",
    "desiste",
    "volatilidade",
    "baixa demanda",
    "preço abaixo",
    "preco abaixo",
]

TERMOS_MERCADO = [
    "b3",
    "cvm",
    "nasdaq",
    "nyse",
    "bolsa",
    "ações",
    "acoes",
    "mercado",
    "investidores",
    "banco coordenador",
]


def limpar_texto(texto: str) -> str:
    texto = html.unescape(texto or "")
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def normalizar(texto: str) -> str:
    texto = limpar_texto(texto).lower()
    texto = re.sub(r"[^a-z0-9áéíóúàâêôãõç\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def chave_noticia(titulo: str, link: str) -> str:
    base = f"{normalizar(titulo)[:180]}|{link}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def carregar_json(caminho, padrao):
    if not caminho.exists():
        return padrao
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:
        return padrao


def salvar_json(caminho, dados):
    caminho.parent.mkdir(exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def montar_url_google_news(consulta: str) -> str:
    q = urllib.parse.quote_plus(consulta)
    return f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def buscar_noticias():
    noticias = []
    vistos = set()

    for consulta in CONSULTAS_RSS:
        url = montar_url_google_news(consulta)
        feed = feedparser.parse(url)

        for item in feed.entries[:10]:
            titulo = limpar_texto(getattr(item, "title", ""))
            resumo = limpar_texto(getattr(item, "summary", ""))
            link = getattr(item, "link", "")
            fonte = "Google News"

            try:
                fonte = item.source.title
            except Exception:
                pass

            chave = chave_noticia(titulo, link)

            if chave in vistos:
                continue

            vistos.add(chave)

            noticias.append({
                "titulo": titulo,
                "resumo": resumo,
                "link": link,
                "fonte": fonte,
                "consulta": consulta,
                "chave": chave,
            })

    return noticias


def classificar_estagio(noticia):
    texto = normalizar(f"{noticia.get('titulo', '')} {noticia.get('resumo', '')}")

    if any(t in texto for t in ["prospecto definitivo", "precificação", "precificacao", "estreia na bolsa", "estreia na b3"]):
        return "Fase avançada / estreia ou precificação"

    if any(t in texto for t in ["reserva de ações", "reserva de acoes", "bookbuilding", "faixa indicativa"]):
        return "Período de reserva / bookbuilding"

    if any(t in texto for t in ["pedido de registro", "prospecto preliminar", "cvm"]):
        return "Pedido de registro / prospecto preliminar"

    if any(t in texto for t in TERMOS_OFERTA):
        return "Oferta subsequente / follow-on"

    if any(t in texto for t in ["prepara ipo", "planeja ipo", "avalia ipo", "upcoming ipo"]):
        return "Rumor ou preparação"

    if "ipo" in texto or "oferta pública inicial" in texto or "oferta publica inicial" in texto:
        return "IPO / abertura de capital"

    return "Mercado de ofertas"


def pontuar_noticia(noticia):
    texto = normalizar(f"{noticia.get('titulo', '')} {noticia.get('resumo', '')}")

    score = 0
    motivos = []

    if any(normalizar(t) in texto for t in TERMOS_IPO_FORTE):
        score += 6
        motivos.append("cita IPO, abertura de capital, prospecto ou estreia")

    if any(normalizar(t) in texto for t in TERMOS_OFERTA):
        score += 4
        motivos.append("cita oferta pública, follow-on ou emissão de ações")

    if any(normalizar(t) in texto for t in TERMOS_ALERTA_RISCO):
        score += 4
        motivos.append("tem sinal de risco, adiamento, cancelamento ou baixa demanda")

    if any(normalizar(t) in texto for t in TERMOS_MERCADO):
        score += 2
        motivos.append("tem relação direta com mercado financeiro/bolsa")

    # Dá peso extra para fontes/títulos com B3, CVM, Nasdaq ou NYSE
    if any(t in texto for t in ["b3", "cvm", "nasdaq", "nyse"]):
        score += 2
        motivos.append("envolve bolsa, regulador ou mercado externo")

    return score, motivos


def tipo_alerta(noticia):
    texto = normalizar(f"{noticia.get('titulo', '')} {noticia.get('resumo', '')}")

    if any(normalizar(t) in texto for t in TERMOS_ALERTA_RISCO):
        return "Atenção / risco na oferta"

    if any(t in texto for t in ["prospecto definitivo", "precificação", "precificacao", "estreia"]):
        return "IPO em fase avançada"

    if any(t in texto for t in ["pedido de registro", "prospecto preliminar", "cvm"]):
        return "Novo IPO em análise"

    if any(normalizar(t) in texto for t in TERMOS_OFERTA):
        return "Oferta / follow-on"

    return "Radar de IPO"


def acao_sugerida(noticia):
    estagio = classificar_estagio(noticia)

    if "avançada" in estagio or "bookbuilding" in estagio:
        return (
            "Vale estudar com calma antes de entrar. Ver preço/faixa indicativa, setor, dívida, lucro, "
            "destinação dos recursos e se combina com sua estratégia ARCA."
        )

    if "Rumor" in estagio:
        return "Apenas acompanhar. Rumor de IPO não é motivo para comprar ativo relacionado."

    if "follow-on" in estagio.lower() or "Oferta subsequente" in estagio:
        return (
            "Ver se a oferta pode diluir acionistas ou melhorar caixa da empresa. Não entrar sem analisar preço e objetivo da captação."
        )

    if "Pedido de registro" in estagio:
        return (
            "Acompanhar próximos passos: prospecto, faixa de preço, coordenadores e período de reserva."
        )

    return "Acompanhar. Não é recomendação de compra, apenas radar para estudo."


def analisar_noticias(noticias, historico):
    chaves_enviadas = {item.get("chave") for item in historico if item.get("chave")}
    alertas = []

    for noticia in noticias:
        if noticia.get("chave") in chaves_enviadas:
            continue

        score, motivos = pontuar_noticia(noticia)

        if score < PONTUACAO_MINIMA_ALERTA:
            continue

        alerta = {
            **noticia,
            "score": score,
            "motivos": motivos,
            "tipo": tipo_alerta(noticia),
            "estagio": classificar_estagio(noticia),
            "acao": acao_sugerida(noticia),
        }

        alertas.append(alerta)

    alertas.sort(key=lambda x: x["score"], reverse=True)
    return alertas[:LIMITE_ALERTAS_POR_EXECUCAO]


def gerar_mensagem(alertas):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    linhas = []
    linhas.append(f"🆕 Radar de IPOs e Ofertas — {agora}")
    linhas.append("")

    if not alertas:
        linhas.append("Nenhum alerta novo de IPO/oferta forte o suficiente nesta rodada.")
        return "\n".join(linhas)

    linhas.append(f"Alertas novos encontrados: {len(alertas)}")
    linhas.append("")

    for i, alerta in enumerate(alertas, 1):
        linhas.append(f"{i}. {alerta['titulo']}")
        linhas.append(f"Tipo: {alerta['tipo']}")
        linhas.append(f"Estágio: {alerta['estagio']}")
        linhas.append(f"Pontuação: {alerta['score']}")
        linhas.append(f"Fonte: {alerta['fonte']}")
        linhas.append(f"Motivo: {'; '.join(alerta['motivos'])}")
        linhas.append(f"Ação: {alerta['acao']}")
        linhas.append(f"Link: {alerta['link']}")
        linhas.append("")

    linhas.append("Observação: radar informativo. IPO costuma ter volatilidade alta e não deve ser comprado só por notícia.")

    return "\n".join(linhas)


def enviar_telegram(texto):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram não configurado.")
        return False

    partes = []
    limite = 3500

    while len(texto) > limite:
        corte = texto.rfind("\n\n", 0, limite)
        if corte == -1:
            corte = limite
        partes.append(texto[:corte].strip())
        texto = texto[corte:].strip()

    if texto:
        partes.append(texto.strip())

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for i, parte in enumerate(partes, 1):
        prefixo = f"Radar IPO — Parte {i}/{len(partes)}\n\n" if len(partes) > 1 else ""

        dados = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": prefixo + parte,
            "disable_web_page_preview": "true",
        }).encode("utf-8")

        req = urllib.request.Request(url, data=dados, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                print(f"Telegram enviado. Parte {i}/{len(partes)}. Status {resp.status}")
        except Exception as e:
            print(f"Erro ao enviar Telegram: {e}")
            return False

        time.sleep(1)

    return True


def salvar_relatorio(mensagem, alertas):
    PASTA_RELATORIOS.mkdir(exist_ok=True)
    agora = datetime.now().strftime("%Y-%m-%d_%H-%M")

    (PASTA_RELATORIOS / f"radar_ipos_{agora}.txt").write_text(mensagem, encoding="utf-8")
    (PASTA_RELATORIOS / "ultimo_radar_ipos.txt").write_text(mensagem, encoding="utf-8")
    (PASTA_RELATORIOS / "ultimo_radar_ipos.json").write_text(
        json.dumps(alertas, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def atualizar_historico(historico, alertas):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for alerta in alertas:
        historico.append({
            "data_envio": agora,
            "chave": alerta.get("chave"),
            "titulo": alerta.get("titulo"),
            "link": alerta.get("link"),
            "fonte": alerta.get("fonte"),
            "score": alerta.get("score"),
            "tipo": alerta.get("tipo"),
            "estagio": alerta.get("estagio"),
        })

    return historico[-1000:]


def main():
    historico = carregar_json(ARQUIVO_HISTORICO, [])

    print("Buscando notícias de IPOs e ofertas...")
    noticias = buscar_noticias()
    print(f"Notícias coletadas: {len(noticias)}")

    alertas = analisar_noticias(noticias, historico)
    print(f"Alertas novos: {len(alertas)}")

    mensagem = gerar_mensagem(alertas)
    salvar_relatorio(mensagem, alertas)

    if alertas:
        enviar_telegram(mensagem)
        historico = atualizar_historico(historico, alertas)
        salvar_json(ARQUIVO_HISTORICO, historico)
    else:
        print("Sem alertas novos. Nada enviado ao Telegram.")

    print(mensagem)


if __name__ == "__main__":
    main()
