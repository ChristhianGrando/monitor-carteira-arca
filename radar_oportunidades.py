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
ARQUIVO_HISTORICO = PASTA_RELATORIOS / "radar_oportunidades_enviadas.json"
ARQUIVO_CARTEIRA = Path("carteira.json")

PONTUACAO_MINIMA_ALERTA = 9
LIMITE_ALERTAS_POR_EXECUCAO = 5

CARTEIRA_PADRAO = {
    "meta": {
        "Ações Brasil": 25,
        "Real Estate / FIIs": 25,
        "Caixa / Reserva": 25,
        "Ativos Internacionais": 25,
    },
    "ativos": [
        {"classe": "Ações Brasil", "ativo": "IBOB11", "valor": 2395.30},
        {"classe": "Real Estate / FIIs", "ativo": "HGLG11", "valor": 908.40},
        {"classe": "Real Estate / FIIs", "ativo": "KNCR11", "valor": 855.36},
        {"classe": "Real Estate / FIIs", "ativo": "KNRI11", "valor": 0.00},
        {"classe": "Caixa / Reserva", "ativo": "CDB 100% CDI", "valor": 0.00},
        {"classe": "Ativos Internacionais", "ativo": "WRLD11", "valor": 2423.86},
        {"classe": "Ativos Internacionais", "ativo": "SPCX34", "valor": 0.00},
    ],
}

MAPA_ATIVOS = {
    "IBOB11": {
        "classe": "Ações Brasil",
        "termos": ["ibob11", "ibovespa", "bovespa", "bolsa brasileira", "petrobras", "vale", "bancos", "selic", "copom", "ipca", "fiscal"],
    },
    "WRLD11": {
        "classe": "Ativos Internacionais",
        "termos": ["wrld11", "s&p 500", "sp500", "nasdaq", "fed", "federal reserve", "eua", "bolsa americana", "dólar", "dolar", "mercado global"],
    },
    "SPCX34": {
        "classe": "Ativos Internacionais",
        "termos": ["spcx34", "spacex", "space x", "starlink", "elon musk", "musk", "starship", "nasa", "foguete", "lançamento", "lancamento", "ipo"],
    },
    "HGLG11": {
        "classe": "Real Estate / FIIs",
        "termos": ["hglg11", "galpões", "galpoes", "logística", "logistica", "fii logístico", "fii logistico", "vacância", "vacancia", "aluguéis", "alugueis"],
    },
    "KNRI11": {
        "classe": "Real Estate / FIIs",
        "termos": ["knri11", "kinea renda", "imóveis corporativos", "imoveis corporativos", "lajes", "galpões", "galpoes", "vacância", "vacancia", "aluguéis", "alugueis"],
    },
    "KNCR11": {
        "classe": "Real Estate / FIIs",
        "termos": ["kncr11", "kinea rendimentos", "cri", "cris", "cdi", "selic", "fii papel", "inadimplência", "inadimplencia", "ipca"],
    },
    "CDB 100% CDI": {
        "classe": "Caixa / Reserva",
        "termos": ["cdb", "cdi", "selic", "copom", "banco central", "ipca", "inflação", "inflacao"],
    },
}

CONSULTAS_RSS = [
    "Ibovespa OR IBOB11 OR BOVA11 OR Selic OR Copom OR IPCA",
    "WRLD11 OR S&P 500 OR Nasdaq OR Fed OR dólar",
    "SPCX34 OR SpaceX OR Starlink OR Elon Musk OR Starship",
    "HGLG11 OR KNRI11 OR KNCR11 OR fundos imobiliários OR FIIs OR CRI",
    "ações oportunidade compra bolsa brasileira dividendos preço alvo",
    "FIIs oportunidade compra desconto vacância dividendos Selic",
    "CDI OR Selic OR Banco Central OR Copom OR IPCA",
]

TERMOS_OPORTUNIDADE = [
    "oportunidade", "barato", "desconto", "queda", "cai", "caem", "correção", "correcao",
    "preço-alvo", "preco-alvo", "recomendação de compra", "recomendacao de compra",
    "compra", "dividendos", "dividend yield", "potencial de alta", "atrativo",
    "corte da selic", "queda da selic", "juros menores", "fundos imobiliários sobem",
    "fii barato", "fii com desconto", "ações descontadas", "acoes descontadas",
]

TERMOS_RISCO = [
    "risco", "crise", "guerra", "investigação", "investigacao", "fraude", "prejuízo",
    "prejuizo", "queda forte", "despenca", "desabam", "falha", "explosão", "explosao",
    "inadimplência", "inadimplencia", "vacância alta", "vacancia alta", "rebaixamento",
    "juros sobem", "alta da selic", "fed duro", "inflação acelera", "inflacao acelera",
]

TERMOS_MACRO_ALTO_IMPACTO = [
    "copom", "selic", "fed", "federal reserve", "ipca", "inflação", "inflacao",
    "dólar", "dolar", "recessão", "recessao", "pib", "juros", "banco central",
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


def carregar_carteira():
    carteira = carregar_json(ARQUIVO_CARTEIRA, CARTEIRA_PADRAO)
    if not ARQUIVO_CARTEIRA.exists():
        ARQUIVO_CARTEIRA.write_text(json.dumps(carteira, ensure_ascii=False, indent=2), encoding="utf-8")
    return carteira


def calcular_alocacao(carteira):
    totais = {}
    total = 0.0
    for ativo in carteira.get("ativos", []):
        classe = ativo.get("classe", "Sem classe")
        valor = float(ativo.get("valor", 0) or 0)
        totais[classe] = totais.get(classe, 0.0) + valor
        total += valor
    percentuais = {}
    if total > 0:
        for classe, valor in totais.items():
            percentuais[classe] = (valor / total) * 100
    return total, totais, percentuais


def classe_mais_abaixo_da_meta(carteira):
    meta = carteira.get("meta", CARTEIRA_PADRAO["meta"])
    _, _, percentuais = calcular_alocacao(carteira)
    diferencas = {}
    for classe, meta_pct in meta.items():
        atual = percentuais.get(classe, 0.0)
        diferencas[classe] = float(meta_pct) - atual
    if not diferencas:
        return "Caixa / Reserva", 0.0
    classe = max(diferencas, key=diferencas.get)
    return classe, diferencas[classe]


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


def detectar_ativos_e_classes(noticia):
    texto = normalizar(f"{noticia.get('titulo', '')} {noticia.get('resumo', '')}")
    ativos = []
    classes = set()
    for ativo, dados in MAPA_ATIVOS.items():
        termos = [normalizar(t) for t in dados["termos"]]
        if any(t in texto for t in termos):
            ativos.append(ativo)
            classes.add(dados["classe"])
    return ativos, sorted(classes)


def pontuar_noticia(noticia, ativos, classes, carteira):
    texto = normalizar(f"{noticia.get('titulo', '')} {noticia.get('resumo', '')}")
    score = 0
    motivos = []
    if ativos:
        score += 4 + len(ativos)
        motivos.append("cita ativos ou temas ligados à sua carteira")
    if any(normalizar(t) in texto for t in TERMOS_OPORTUNIDADE):
        score += 3
        motivos.append("tem linguagem de oportunidade/compra/desconto")
    if any(normalizar(t) in texto for t in TERMOS_RISCO):
        score += 4
        motivos.append("tem linguagem de risco/queda/alerta")
    if any(normalizar(t) in texto for t in TERMOS_MACRO_ALTO_IMPACTO):
        score += 2
        motivos.append("envolve macroeconomia/juros/dólar")
    classe_prioritaria, _ = classe_mais_abaixo_da_meta(carteira)
    if classe_prioritaria in classes:
        score += 3
        motivos.append(f"afeta a classe mais abaixo da meta: {classe_prioritaria}")
    return score, motivos


def tipo_alerta(noticia):
    texto = normalizar(f"{noticia.get('titulo', '')} {noticia.get('resumo', '')}")
    if any(normalizar(t) in texto for t in TERMOS_RISCO):
        return "Risco / Atenção"
    if any(normalizar(t) in texto for t in TERMOS_OPORTUNIDADE):
        return "Oportunidade de estudo"
    return "Acompanhamento"


def acao_sugerida(classes, carteira):
    classe_prioritaria, diferenca = classe_mais_abaixo_da_meta(carteira)
    caixa_atual = calcular_alocacao(carteira)[2].get("Caixa / Reserva", 0.0)
    if caixa_atual < 20:
        return (
            "Caixa/Reserva está abaixo de 20%. Mesmo com oportunidades, priorizar recompor "
            "CDB 100% CDI nos próximos aportes, salvo se você já tiver reserva fora do BTG."
        )
    if classe_prioritaria in classes and diferenca > 2:
        return (
            f"Pode valer estudar essa notícia para o próximo aporte, porque {classe_prioritaria} "
            "está abaixo da meta ARCA."
        )
    return "Acompanhar. Não comprar por impulso. Usar como informação para o próximo aporte e respeitar a meta ARCA."


def analisar_noticias(noticias, historico, carteira):
    chaves_enviadas = {item.get("chave") for item in historico if item.get("chave")}
    alertas = []
    for noticia in noticias:
        if noticia.get("chave") in chaves_enviadas:
            continue
        ativos, classes = detectar_ativos_e_classes(noticia)
        score, motivos = pontuar_noticia(noticia, ativos, classes, carteira)
        if score < PONTUACAO_MINIMA_ALERTA:
            continue
        alertas.append({
            **noticia,
            "ativos": ativos,
            "classes": classes,
            "score": score,
            "motivos": motivos,
            "tipo": tipo_alerta(noticia),
            "acao": acao_sugerida(classes, carteira),
        })
    alertas.sort(key=lambda x: x["score"], reverse=True)
    return alertas[:LIMITE_ALERTAS_POR_EXECUCAO]


def formatar_reais(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_mensagem(alertas, carteira):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    total, _, percentuais = calcular_alocacao(carteira)
    classe_prioritaria, diferenca = classe_mais_abaixo_da_meta(carteira)
    linhas = []
    linhas.append(f"🚨 Radar de Oportunidades ARCA — {agora}")
    linhas.append("")
    linhas.append("Carteira considerada:")
    linhas.append(f"- Total informado: {formatar_reais(total)}")
    for classe in carteira.get("meta", CARTEIRA_PADRAO["meta"]).keys():
        pct = percentuais.get(classe, 0.0)
        linhas.append(f"- {classe}: {pct:.2f}%")
    linhas.append("")
    linhas.append(f"Classe mais abaixo da meta: {classe_prioritaria} ({diferenca:.2f} p.p. abaixo da meta).")
    linhas.append("")
    if not alertas:
        linhas.append("Nenhum alerta novo forte o suficiente nesta rodada.")
        return "\n".join(linhas)
    linhas.append(f"Alertas novos encontrados: {len(alertas)}")
    linhas.append("")
    for i, alerta in enumerate(alertas, 1):
        ativos = ", ".join(alerta["ativos"]) if alerta["ativos"] else "Carteira em geral"
        classes = ", ".join(alerta["classes"]) if alerta["classes"] else "Geral"
        linhas.append(f"{i}. {alerta['titulo']}")
        linhas.append(f"Tipo: {alerta['tipo']}")
        linhas.append(f"Pontuação: {alerta['score']}")
        linhas.append(f"Afeta: {ativos}")
        linhas.append(f"Classe: {classes}")
        linhas.append(f"Fonte: {alerta['fonte']}")
        linhas.append(f"Motivo: {'; '.join(alerta['motivos'])}")
        linhas.append(f"Ação: {alerta['acao']}")
        linhas.append(f"Link: {alerta['link']}")
        linhas.append("")
    linhas.append("Observação: radar de estudo, não recomendação automática de compra ou venda.")
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
        prefixo = f"Radar ARCA — Parte {i}/{len(partes)}\n\n" if len(partes) > 1 else ""
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
    (PASTA_RELATORIOS / f"radar_{agora}.txt").write_text(mensagem, encoding="utf-8")
    (PASTA_RELATORIOS / "ultimo_radar.txt").write_text(mensagem, encoding="utf-8")
    (PASTA_RELATORIOS / "ultimo_radar.json").write_text(json.dumps(alertas, ensure_ascii=False, indent=2), encoding="utf-8")


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
            "ativos": alerta.get("ativos", []),
            "classes": alerta.get("classes", []),
        })
    return historico[-1000:]


def main():
    carteira = carregar_carteira()
    historico = carregar_json(ARQUIVO_HISTORICO, [])
    print("Buscando notícias para o radar...")
    noticias = buscar_noticias()
    print(f"Notícias coletadas: {len(noticias)}")
    alertas = analisar_noticias(noticias, historico, carteira)
    print(f"Alertas novos: {len(alertas)}")
    mensagem = gerar_mensagem(alertas, carteira)
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
