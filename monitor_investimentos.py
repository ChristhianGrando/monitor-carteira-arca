import os
import re
import html
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import feedparser


CARTEIRA = {
    "IBOB11": {
        "classe": "Ações Brasil",
        "termos": [
            "ibob11", "ibovespa", "bovespa", "selic", "copom", "ipca",
            "dólar", "dolar", "petrobras", "vale", "bancos", "fiscal"
        ],
    },
    "WRLD11": {
        "classe": "Ativos Internacionais",
        "termos": [
            "wrld11", "s&p 500", "sp500", "nasdaq", "fed", "federal reserve",
            "eua", "dólar", "dolar", "bolsa americana", "mercado global"
        ],
    },
    "SPCX34": {
        "classe": "Ativos Internacionais / SpaceX",
        "termos": [
            "spcx34", "spacex", "space x", "starlink", "elon musk", "musk",
            "foguete", "nasa", "starship", "lançamento", "lancamento", "tesla",
            "ipo"
        ],
    },
    "HGLG11": {
        "classe": "Real Estate / FII Logística",
        "termos": [
            "hglg11", "fii logística", "fii logistica", "galpões", "galpoes",
            "logístico", "logistico", "vacância", "vacancia", "aluguéis", "alugueis"
        ],
    },
    "KNRI11": {
        "classe": "Real Estate / FII Renda",
        "termos": [
            "knri11", "kinea renda", "imóveis corporativos", "imoveis corporativos",
            "lajes", "galpões", "galpoes", "vacância", "vacancia", "aluguéis", "alugueis"
        ],
    },
    "KNCR11": {
        "classe": "Real Estate / FII Papel",
        "termos": [
            "kncr11", "kinea rendimentos", "cri", "cris", "cdi", "selic",
            "inadimplência", "inadimplencia", "ipca", "fii papel"
        ],
    },
    "CDB 100% CDI": {
        "classe": "Caixa / Reserva",
        "termos": [
            "cdb", "cdi", "selic", "copom", "banco central", "ipca",
            "inflação", "inflacao"
        ],
    },
}


CONSULTAS_RSS = [
    "IBOB11 OR Ibovespa OR Selic OR Copom OR IPCA",
    "WRLD11 OR S&P 500 OR Nasdaq OR Fed OR dólar",
    "SPCX34 OR SpaceX OR Starlink OR Elon Musk OR Starship",
    "HGLG11 OR KNRI11 OR KNCR11 OR fundos imobiliários OR FIIs OR CRI",
    "CDI OR Selic OR IPCA OR Banco Central OR Copom",
]


PALAVRAS_ALTO_IMPACTO = [
    "copom", "selic", "fed", "federal reserve", "ipca", "inflação", "inflacao",
    "recessão", "recessao", "crise", "guerra", "fato relevante", "inadimplência",
    "inadimplencia", "vacância", "vacancia", "starship", "nasa", "contrato",
    "explosão", "explosao", "falha", "ipo", "dólar dispara", "dolar dispara"
]

PALAVRAS_MEDIO_IMPACTO = [
    "dólar", "dolar", "juros", "dividendos", "rendimentos", "aluguel", "aluguéis",
    "alugueis", "resultados", "relatório", "relatorio", "balanço", "balanco",
    "nasdaq", "s&p 500", "ibovespa", "petrobras", "vale", "bancos"
]


# Ajuste manual dos pesos atuais da carteira.
# Como você tirou a renda fixa para comprar SPCX34, deixei Caixa zerado.
PESOS_ATUAIS = {
    "Ações Brasil": 23.76,
    "Real Estate / FIIs": 25.00,
    "Caixa / Reserva": 0.00,
    "Ativos Internacionais": 51.00,
}


META_ARCA = {
    "Ações Brasil": 25.0,
    "Real Estate / FIIs": 25.0,
    "Caixa / Reserva": 25.0,
    "Ativos Internacionais": 25.0,
}


def limpar_texto(texto: str) -> str:
    texto = html.unescape(texto or "")
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


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

            chave = (titulo.lower(), link)

            if chave in vistos:
                continue

            vistos.add(chave)

            noticias.append({
                "titulo": titulo,
                "resumo": resumo,
                "link": link,
                "fonte": fonte,
                "consulta": consulta,
            })

    return noticias


def ativos_afetados(noticia):
    texto = f"{noticia['titulo']} {noticia['resumo']}".lower()
    afetados = []

    for ativo, dados in CARTEIRA.items():
        for termo in dados["termos"]:
            if termo.lower() in texto:
                afetados.append(ativo)
                break

    return afetados


def classificar_impacto(noticia, afetados):
    texto = f"{noticia['titulo']} {noticia['resumo']}".lower()

    score = 0
    score += len(afetados) * 2

    for palavra in PALAVRAS_ALTO_IMPACTO:
        if palavra in texto:
            score += 4

    for palavra in PALAVRAS_MEDIO_IMPACTO:
        if palavra in texto:
            score += 2

    if score >= 8:
        return "Alto"

    if score >= 4:
        return "Médio"

    return "Baixo"


def explicar_impacto(afetados):
    explicacoes = []

    if "IBOB11" in afetados:
        explicacoes.append("pode mexer com bolsa brasileira/IBOV")

    if "WRLD11" in afetados:
        explicacoes.append("pode afetar exposição global e dólar")

    if "SPCX34" in afetados:
        explicacoes.append("pode afetar SpaceX/BDR e tecnologia internacional")

    if any(a in afetados for a in ["HGLG11", "KNRI11"]):
        explicacoes.append("pode afetar FIIs de tijolo, vacância ou aluguéis")

    if "KNCR11" in afetados:
        explicacoes.append("pode afetar FII de papel, CDI, CRIs ou inadimplência")

    if "CDB 100% CDI" in afetados:
        explicacoes.append("pode afetar a rentabilidade do caixa/CDI")

    if not explicacoes:
        return "impacto indireto ou apenas informativo"

    return "; ".join(explicacoes)


def sugestao_aporte():
    caixa = PESOS_ATUAIS.get("Caixa / Reserva", 0)

    if caixa < 20:
        return (
            "Priorizar CDB 100% CDI nos próximos aportes, porque a parte "
            "Caixa/Reserva está abaixo da meta do ARCA."
        )

    diferencas = {}

    for classe, meta in META_ARCA.items():
        atual = PESOS_ATUAIS.get(classe, 0)
        diferencas[classe] = meta - atual

    classe_prioritaria = max(diferencas, key=diferencas.get)

    return f"Priorizar aporte em {classe_prioritaria}, pois está mais abaixo da meta."


def gerar_relatorio(noticias):
    hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
    analisadas = []

    for noticia in noticias:
        afetados = ativos_afetados(noticia)
        impacto = classificar_impacto(noticia, afetados)

        # Descarta notícias muito genéricas sem relação clara
        if not afetados and impacto == "Baixo":
            continue

        analisadas.append({
            **noticia,
            "afetados": afetados,
            "impacto": impacto,
            "explicacao": explicar_impacto(afetados),
        })

    ordem = {"Alto": 0, "Médio": 1, "Baixo": 2}
    analisadas.sort(key=lambda x: ordem[x["impacto"]])

    # Limite de notícias no relatório
    analisadas = analisadas[:15]

    altos = sum(1 for n in analisadas if n["impacto"] == "Alto")
    medios = sum(1 for n in analisadas if n["impacto"] == "Médio")
    baixos = sum(1 for n in analisadas if n["impacto"] == "Baixo")

    linhas = []

    linhas.append(f"# Relatório da Carteira ARCA — {hoje}")
    linhas.append("")
    linhas.append("## Carteira monitorada")
    linhas.append("")
    linhas.append("- IBOB11")
    linhas.append("- WRLD11")
    linhas.append("- SPCX34")
    linhas.append("- HGLG11")
    linhas.append("- KNCR11")
    linhas.append("- KNRI11")
    linhas.append("- CDB 100% CDI / Caixa")
    linhas.append("")
    linhas.append("## Resumo")
    linhas.append("")

    if analisadas:
        linhas.append(
            f"Foram encontradas {len(analisadas)} notícias relevantes: "
            f"{altos} de alto impacto, {medios} de médio impacto e {baixos} de baixo impacto."
        )
    else:
        linhas.append("Nenhuma notícia relevante encontrada hoje.")

    linhas.append("")
    linhas.append("## Notícias relevantes")
    linhas.append("")

    for i, n in enumerate(analisadas, 1):
        afetados = ", ".join(n["afetados"]) if n["afetados"] else "Carteira em geral"

        linhas.append(f"### {i}. {n['titulo']}")
        linhas.append("")
        linhas.append(f"- Impacto: {n['impacto']}")
        linhas.append(f"- Ativos afetados: {afetados}")
        linhas.append(f"- Fonte: {n['fonte']}")
        linhas.append(f"- Explicação: {n['explicacao']}")
        linhas.append(f"- Link: {n['link']}")
        linhas.append("")

    linhas.append("## Conclusão para o próximo aporte")
    linhas.append("")
    linhas.append(sugestao_aporte())
    linhas.append("")
    linhas.append(
        "Observação: este relatório não é recomendação de compra ou venda. "
        "Ele serve para acompanhar notícias e manter disciplina no rebalanceamento."
    )
    linhas.append("")

    relatorio = "\n".join(linhas)

    return relatorio, analisadas


def dividir_texto_telegram(texto, limite=3500):
    partes = []

    while len(texto) > limite:
        corte = texto.rfind("\n### ", 0, limite)

        if corte == -1:
            corte = texto.rfind("\n## ", 0, limite)

        if corte == -1:
            corte = texto.rfind("\n\n", 0, limite)

        if corte == -1:
            corte = limite

        parte = texto[:corte].strip()
        if parte:
            partes.append(parte)

        texto = texto[corte:].strip()

    if texto:
        partes.append(texto.strip())

    return partes


def enviar_telegram(texto):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram não configurado. Secrets não encontrados.")
        return False

    partes = dividir_texto_telegram(texto, limite=3500)
    total = len(partes)

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for i, parte in enumerate(partes, start=1):
        mensagem = f"📊 Relatório Carteira ARCA — Parte {i}/{total}\n\n{parte}"

        dados = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": mensagem,
            "disable_web_page_preview": "true"
        }).encode("utf-8")

        req = urllib.request.Request(url, data=dados, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                print(f"Parte {i}/{total} enviada para o Telegram. Status: {resp.status}")
        except Exception as e:
            print(f"Erro ao enviar parte {i}/{total} para o Telegram: {e}")
            return False

        # Pequena pausa para evitar erro de limite do Telegram
        time.sleep(1)

    return True


def salvar_relatorios(relatorio, analisadas):
    pasta = Path("relatorios")
    pasta.mkdir(exist_ok=True)

    data_arquivo = datetime.now().strftime("%Y-%m-%d")

    caminho_md = pasta / f"relatorio_{data_arquivo}.md"
    caminho_md.write_text(relatorio, encoding="utf-8")

    caminho_ultimo_md = pasta / "ultimo_relatorio.md"
    caminho_ultimo_md.write_text(relatorio, encoding="utf-8")

    caminho_json = pasta / "ultimo_relatorio.json"
    caminho_json.write_text(
        json.dumps(analisadas, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def main():
    print("Buscando notícias...")
    noticias = buscar_noticias()

    print(f"Notícias encontradas: {len(noticias)}")

    relatorio, analisadas = gerar_relatorio(noticias)

    salvar_relatorios(relatorio, analisadas)

    print(relatorio)

    enviar_telegram(relatorio)


if __name__ == "__main__":
    main()
