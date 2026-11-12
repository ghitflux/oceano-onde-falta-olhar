"""Coleta (OBIS, ETOPO1, Natural Earth) e carga do extrato agregado.

Fontes, todas públicas e sem chave:

- OBIS, Ocean Biodiversity Information System (https://obis.org), API v3. Só pontos de acesso
  agregados: `/checklist` (lista de táxons com contagem de registros), `/facet` (registros por
  conjunto de dados) e `/statistics`. Nenhum registro individual de ocorrência é baixado.
- ETOPO1 (NOAA NGDC), relevo global, amostrado a cada 0,5° pelo ERDDAP da NOAA CoastWatch. Serve
  para medir quanto de cada célula é oceano e até que profundidade a coluna d'água vai.
- Natural Earth 1:110m, linha de costa (domínio público), só para desenhar os mapas.

Recorte: o globo em células de 10° x 10° (de 80°S a 90°N) cruzadas com quatro faixas de
profundidade. Uma "unidade" do estudo é uma célula numa faixa.

O bruto fica em `data/brutos/` (fora do git, retomável). O que a análise usa é o agregado em
`data/`: por célula, por unidade e a distribuição de frequência das espécies (quantas espécies com
1 registro, com 2, ...), que é tudo de que os estimadores precisam.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

API = "https://api.obis.org/v3"
URL_ETOPO = (
    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/etopo180.csv"
    "?altitude[(-89.75):30:(89.75)][(-179.75):30:(179.75)]"
)
URL_COSTA = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_coastline.geojson"
AGENTE = "portfolio-estudos/1.0"
PAUSA_S = 0.25

PASSO = 10  # graus
LAT_MIN, LAT_MAX = -80, 90
RAIO_TERRA_KM = 6371.0088
LINHAS_ETOPO = 360 * 720  # pontos da amostra de 0,5°

# (identificador, rótulo, profundidade inicial, profundidade final), em metros. O filtro da API é
# inclusivo nas duas pontas, então as faixas usam inteiros que não se sobrepõem.
FAIXAS = [
    ("0-200", "0 a 200 m", 0, 200),
    ("200-1000", "200 a 1.000 m", 201, 1000),
    ("1000-4000", "1.000 a 4.000 m", 1001, 4000),
    ("4000+", "mais de 4.000 m", 4001, 12000),
]
ID_FAIXAS = [f[0] for f in FAIXAS]
ROTULO_FAIXA = {f[0]: f[1] for f in FAIXAS}
TOPO_FAIXA = {"0-200": 0, "200-1000": 200, "1000-4000": 1000, "4000+": 4000}

ANO_DE_CORTE = 2010
MIN_REGISTROS_AVALIAVEL = 500  # registros de espécie para a unidade entrar nos estimadores
MIN_REGISTROS_DEPOIS = 1000  # registros de espécie depois do corte para entrar na validação

PASTA = Path("data")
BRUTOS = PASTA / "brutos"


# ----------------------------------------------------------------------------------------------
# Grade
# ----------------------------------------------------------------------------------------------


def id_celula(lat_sul: int, lon_oeste: int) -> str:
    """Identificador pelo canto sudoeste: 'N40W030', 'S10E120'."""
    return f"{'N' if lat_sul >= 0 else 'S'}{abs(lat_sul):02d}{'E' if lon_oeste >= 0 else 'W'}{abs(lon_oeste):03d}"


def rotulo_celula(lat_sul: int, lon_oeste: int) -> str:
    """Rótulo legível: '40°N a 50°N, 30°W a 20°W'."""

    def lat(v: int) -> str:
        return "0°" if v == 0 else f"{abs(v)}°{'S' if v < 0 else 'N'}"

    def lon(v: int) -> str:
        return "0°" if v == 0 else ("180°" if abs(v) == 180 else f"{abs(v)}°{'W' if v < 0 else 'E'}")

    return f"{lat(lat_sul)} a {lat(lat_sul + PASSO)}, {lon(lon_oeste)} a {lon(lon_oeste + PASSO)}"


def poligono(lat_sul: int, lon_oeste: int) -> str:
    n, l = lat_sul + PASSO, lon_oeste + PASSO
    return f"POLYGON(({lon_oeste} {lat_sul}, {l} {lat_sul}, {l} {n}, {lon_oeste} {n}, {lon_oeste} {lat_sul}))"


def area_da_celula_km2(lat_sul: float, passo: float = PASSO) -> float:
    """Área de uma célula de `passo` graus na esfera: R² · Δλ · (sen φ2 − sen φ1).

    A célula encolhe com a latitude: a de 80° a 90° tem cerca de 9% da área da célula do equador.
    """
    f1, f2 = np.radians(lat_sul), np.radians(lat_sul + passo)
    return float(RAIO_TERRA_KM**2 * np.radians(passo) * (np.sin(f2) - np.sin(f1)))


def grade_de_celulas(relevo: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por célula, com a área e a fração da célula em que há água em cada faixa.

    `relevo` tem latitude, longitude e altitude (m; negativa no mar) numa grade regular. Dentro de
    uma célula os pontos são pesados pelo cosseno da latitude, porque um ponto perto do polo
    representa menos área. A fração da faixa "200 a 1.000 m" é a parte da célula em que o fundo
    fica abaixo de 200 m, isto é, onde essa camada de água existe.
    """
    r = relevo.copy()
    r["lat_sul"] = (np.floor(r["latitude"] / PASSO) * PASSO).astype(int)
    r["lon_oeste"] = (np.floor(r["longitude"] / PASSO) * PASSO).astype(int)
    r = r[(r["lat_sul"] >= LAT_MIN) & (r["lat_sul"] < LAT_MAX)]
    r["peso"] = np.cos(np.radians(r["latitude"]))
    for faixa, topo in TOPO_FAIXA.items():
        r[f"f_{faixa}"] = r["peso"] * (r["altitude"] < -topo)
    soma = r.groupby(["lat_sul", "lon_oeste"])[["peso"] + [f"f_{f}" for f in ID_FAIXAS]].sum().reset_index()
    saida = soma[["lat_sul", "lon_oeste"]].copy()
    saida["celula"] = [id_celula(a, o) for a, o in zip(saida["lat_sul"], saida["lon_oeste"])]
    saida["area_km2"] = [area_da_celula_km2(a) for a in saida["lat_sul"]]
    for faixa in ID_FAIXAS:
        saida[f"fracao_{faixa}"] = soma[f"f_{faixa}"] / soma["peso"]
        saida[f"area_{faixa}_km2"] = saida[f"fracao_{faixa}"] * saida["area_km2"]
    saida = saida.rename(columns={"fracao_0-200": "fracao_oceano"})
    colunas = ["celula", "lat_sul", "lon_oeste", "area_km2", "fracao_oceano"]
    colunas += [f"fracao_{f}" for f in ID_FAIXAS[1:]] + [f"area_{f}_km2" for f in ID_FAIXAS]
    return saida[colunas].sort_values(["lat_sul", "lon_oeste"]).reset_index(drop=True)


# ----------------------------------------------------------------------------------------------
# Rede
# ----------------------------------------------------------------------------------------------


def _baixar_bytes(url: str, tentativas: int = 5, espera: int = 300) -> bytes:
    """Uma requisição por vez, com pausa depois e repetição com espera crescente."""
    requisicao = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    for tentativa in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(requisicao, timeout=espera) as resposta:
                corpo = resposta.read()
            time.sleep(PAUSA_S)
            return corpo
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            if tentativa == tentativas:
                raise
            time.sleep(8 * tentativa)
    raise RuntimeError("inalcançável")


def obter(caminho: str, **parametros) -> dict:
    """Uma chamada à API do OBIS, devolvendo o JSON."""
    url = f"{API}/{caminho}?{urllib.parse.urlencode(parametros)}"
    for tentativa in range(1, 4):
        try:
            return json.loads(_baixar_bytes(url))
        except json.JSONDecodeError:
            if tentativa == 3:
                raise
            time.sleep(8 * tentativa)
    raise RuntimeError("inalcançável")


def resumir_checklist(linhas: list[dict]) -> dict:
    """Reduz a lista de táxons de uma unidade ao que o estudo usa.

    A contagem de cada linha do `/checklist` é exclusiva (registros identificados exatamente naquele
    táxon), então a soma das linhas é o total de registros. "Espécie" aqui é o `speciesid` do
    WoRMS: subespécies, variedades e formas somam na espécie a que pertencem, e o nome é o aceito.
    Linhas sem `speciesid` são registros identificados só acima de espécie (gênero, família, ...)
    e ficam fora dos estimadores; a contagem deles é guardada para medir esse viés.
    """
    por_especie: dict[int, int] = {}
    total = genero = 0
    for linha in linhas:
        n = int(linha.get("records") or 0)
        total += n
        especie = linha.get("speciesid")
        if especie:
            por_especie[int(especie)] = por_especie.get(int(especie), 0) + n
        elif linha.get("taxonRank") == "Genus":
            genero += n
    return {
        "registros": total,
        "registros_especie": sum(por_especie.values()),
        "registros_genero": genero,
        "linhas": len(linhas),
        "contagens": sorted(por_especie.items()),
    }


def _checklist(tamanho: int = 10000, **filtro) -> dict:
    linhas: list[dict] = []
    while True:
        pagina = obter("checklist", size=tamanho, skip=len(linhas), **filtro)
        lote = pagina.get("results", [])
        linhas.extend(lote)
        if len(lote) < tamanho:
            return resumir_checklist(linhas)


def _coletar_unidade(lat_sul: int, lon_oeste: int, inicio: int, fim: int) -> dict:
    filtro = {"geometry": poligono(lat_sul, lon_oeste), "startdepth": inicio, "enddepth": fim}
    unidade: dict = {"todos": _checklist(**filtro), "ate_corte": None, "depois_corte": None, "conjuntos": None}
    n_especie = unidade["todos"]["registros_especie"]
    if n_especie < MIN_REGISTROS_AVALIAVEL:
        return unidade  # amostra insuficiente: o estudo só usa as contagens gerais
    faceta = obter("facet", facets="dataset_id", **filtro)["results"].get("dataset_id", [])
    # A faceta devolve só os dez maiores conjuntos; o estudo usa apenas o maior.
    unidade["conjuntos"] = {
        "maior_id": faceta[0]["key"] if faceta else None,
        "maior_registros": max((c["records"] for c in faceta), default=0),
    }
    # A validação no tempo pede pelo menos 500 registros de espécie até o corte e 1.000 depois.
    # Só se consulta o recorte que ainda pode cumprir a exigência.
    if n_especie >= MIN_REGISTROS_AVALIAVEL + MIN_REGISTROS_DEPOIS:
        unidade["ate_corte"] = _checklist(enddate=f"{ANO_DE_CORTE}-12-31", **filtro)
        n_antes = unidade["ate_corte"]["registros_especie"]
        if n_antes >= MIN_REGISTROS_AVALIAVEL and n_especie - n_antes >= MIN_REGISTROS_DEPOIS:
            unidade["depois_corte"] = _checklist(startdate=f"{ANO_DE_CORTE + 1}-01-01", **filtro)
    return unidade


def baixar_relevo(brutos: Path = BRUTOS) -> pd.DataFrame:
    """ETOPO1 a cada 0,5°. Confere o número de pontos (360 x 720)."""
    arquivo = brutos / "etopo1_meio_grau.csv"
    if not arquivo.exists():
        brutos.mkdir(parents=True, exist_ok=True)
        arquivo.write_bytes(_baixar_bytes(URL_ETOPO))
    relevo = pd.read_csv(arquivo, skiprows=[1])
    if len(relevo) != LINHAS_ETOPO or relevo["altitude"].isna().any():
        arquivo.unlink()
        raise RuntimeError(f"ETOPO1 incompleto: {len(relevo)} pontos, esperados {LINHAS_ETOPO}")
    return relevo


def baixar_costa(destino: Path = PASTA) -> Path:
    """Linha de costa do Natural Earth 1:110m. Confere que é um GeoJSON com as 134 linhas."""
    arquivo = destino / "costa_natural_earth_110m.geojson"
    if not arquivo.exists():
        destino.mkdir(parents=True, exist_ok=True)
        corpo = _baixar_bytes(URL_COSTA)
        if len(json.loads(corpo)["features"]) < 100:
            raise RuntimeError("linha de costa incompleta")
        arquivo.write_bytes(corpo)
    return arquivo


def baixar_obis(celulas: pd.DataFrame, brutos: Path = BRUTOS, relatar=print) -> None:
    """Percorre as células com oceano e guarda um JSON por célula em `data/brutos/obis/`.

    Retomável: célula já gravada não é consultada de novo. Uma célula sem nenhum registro (pela
    `/statistics` sem filtro de profundidade) não gera consultas por faixa.
    """
    pasta = brutos / "obis"
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = celulas[celulas["fracao_oceano"] > 0.01]
    for i, linha in enumerate(alvo.itertuples(), start=1):
        arquivo = pasta / f"{linha.celula}.json"
        if arquivo.exists():
            continue
        t0 = time.time()
        geral = obter("statistics", geometry=poligono(linha.lat_sul, linha.lon_oeste))
        registro = {"celula": linha.celula, "geral": geral, "faixas": {}}
        if geral["records"] > 0:
            for faixa, _, inicio, fim in FAIXAS:
                registro["faixas"][faixa] = _coletar_unidade(linha.lat_sul, linha.lon_oeste, inicio, fim)
        temporario = arquivo.with_suffix(".parcial")
        temporario.write_text(json.dumps(registro), encoding="utf-8")
        temporario.replace(arquivo)
        relatar(f"[{i}/{len(alvo)}] {linha.celula}: {geral['records']} registros, {time.time() - t0:.0f} s")


def baixar_globais(brutos: Path = BRUTOS) -> dict:
    """Totais do OBIS inteiro: geral, por faixa de profundidade e com alguma profundidade."""
    arquivo = brutos / "globais.json"
    if arquivo.exists():
        return json.loads(arquivo.read_text(encoding="utf-8"))
    globais = {"geral": obter("statistics"), "com_profundidade": obter("statistics", startdepth=0, enddepth=12000)}
    globais["por_faixa"] = {f: obter("statistics", startdepth=a, enddepth=b) for f, _, a, b in FAIXAS}
    globais["ate_corte"] = obter("statistics", enddate=f"{ANO_DE_CORTE}-12-31")
    globais["depois_corte"] = obter("statistics", startdate=f"{ANO_DE_CORTE + 1}-01-01")
    arquivo.write_text(json.dumps(globais), encoding="utf-8")
    return globais


def baixar_titulos(ids: list[str], brutos: Path = BRUTOS) -> dict[str, str]:
    """Título dos conjuntos de dados que dominam alguma unidade (para dizer quem é a fonte)."""
    arquivo = brutos / "titulos_conjuntos.json"
    titulos = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}
    for chave in ids:
        if chave in titulos:
            continue
        try:
            resultado = obter(f"dataset/{chave}").get("results", [])
            titulos[chave] = " ".join(str(resultado[0].get("title") or "").split())[:160] if resultado else ""
        except (urllib.error.URLError, OSError, KeyError):
            titulos[chave] = ""
        arquivo.write_text(json.dumps(titulos, ensure_ascii=False), encoding="utf-8")
    return titulos


# ----------------------------------------------------------------------------------------------
# Do bruto para o agregado versionado
# ----------------------------------------------------------------------------------------------


def histograma(contagens: list[int]) -> dict[int, int]:
    """Distribuição de frequência: {k: número de espécies com exatamente k registros}."""
    valores, quantas = np.unique(np.asarray(contagens, dtype=np.int64), return_counts=True)
    return {int(k): int(f) for k, f in zip(valores, quantas) if k > 0}


def agregar(celulas: pd.DataFrame, brutos: Path = BRUTOS) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Lê os JSON por célula e devolve (células com totais, unidades, frequências)."""
    linhas_unidade, linhas_freq, totais = [], [], {}
    for arquivo in sorted((brutos / "obis").glob("*.json")):
        registro = json.loads(arquivo.read_text(encoding="utf-8"))
        celula, geral = registro["celula"], registro["geral"]
        totais[celula] = {
            "registros_total": geral["records"],
            "registros_especie_total": geral["specieslevel"],
            "especies_total": geral["species"],
            "conjuntos_total": geral["datasets"],
        }
        for faixa, unidade in registro["faixas"].items():
            todos = unidade["todos"]
            if todos["registros"] == 0:
                continue
            contagens = dict(todos["contagens"])
            conjuntos = unidade["conjuntos"] or {"maior_id": None, "maior_registros": float("nan")}
            linha = {
                "celula": celula,
                "faixa": faixa,
                "registros": todos["registros"],
                "registros_especie": todos["registros_especie"],
                "registros_genero": todos["registros_genero"],
                "especies": len(contagens),
                "maior_conjunto_id": conjuntos["maior_id"],
                "fracao_maior_conjunto": conjuntos["maior_registros"] / todos["registros"],
            }
            for k, f in histograma(list(contagens.values())).items():
                linhas_freq.append({"celula": celula, "faixa": faixa, "periodo": "todos", "k": k, "f": f})
            antes, depois = unidade["ate_corte"], unidade["depois_corte"]
            if antes is not None:
                c_antes = dict(antes["contagens"])
                linha["registros_especie_ate_corte"] = antes["registros_especie"]
                linha["especies_ate_corte"] = len(c_antes)
                for k, f in histograma(list(c_antes.values())).items():
                    linhas_freq.append({"celula": celula, "faixa": faixa, "periodo": "ate_corte", "k": k, "f": f})
                if depois is not None:
                    c_depois = dict(depois["contagens"])
                    linha["registros_especie_depois_corte"] = depois["registros_especie"]
                    linha["especies_depois_corte"] = len(c_depois)
                    # Espécies que só aparecem depois do corte: é o que a validação tenta prever.
                    # Uma espécie que também tem registro sem data pode ser antiga: fica de fora das
                    # "novas" (escolha conservadora) e é contada à parte.
                    so_depois = {e: n for e, n in c_depois.items() if e not in c_antes}
                    novas = [n for e, n in so_depois.items() if contagens.get(e, 0) <= n]
                    linha["especies_novas_depois_corte"] = len(novas)
                    linha["especies_sem_data_antes_do_corte"] = len(so_depois) - len(novas)
                    for k, f in histograma(novas).items():
                        linhas_freq.append({"celula": celula, "faixa": faixa, "periodo": "novas_depois_corte", "k": k, "f": f})
            linhas_unidade.append(linha)
    cel = celulas.copy()
    for coluna in ("registros_total", "registros_especie_total", "especies_total", "conjuntos_total"):
        cel[coluna] = cel["celula"].map(lambda c, k=coluna: totais.get(c, {}).get(k, 0)).astype(int)
    unidades = pd.DataFrame(linhas_unidade)
    for coluna in unidades.columns:
        if coluna.endswith("_corte"):
            unidades[coluna] = unidades[coluna].astype("Int64")
    return cel, unidades, pd.DataFrame(linhas_freq)


def _hash(arquivo: Path) -> str:
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()[:16]


def baixar(destino: Path = PASTA, relatar=print) -> dict:
    """Coleta tudo, agrega e grava o extrato versionado em `data/` com o registro da coleta."""
    brutos = destino / "brutos"
    relevo = baixar_relevo(brutos)
    baixar_costa(destino)
    grade = grade_de_celulas(relevo)
    globais = baixar_globais(brutos)
    baixar_obis(grade, brutos, relatar)
    celulas, unidades, frequencias = agregar(grade, brutos)
    titulos = baixar_titulos(sorted(unidades["maior_conjunto_id"].dropna().unique()), brutos)
    unidades["maior_conjunto_titulo"] = unidades["maior_conjunto_id"].map(titulos).fillna("")

    # Conferência: a soma das faixas de uma célula não pode passar do total da célula sem filtro.
    soma = unidades.groupby("celula")["registros"].sum()
    excesso = soma - celulas.set_index("celula")["registros_total"].reindex(soma.index)
    if (excesso > 0).any():
        raise RuntimeError(f"faixas somam mais que o total em {list(excesso[excesso > 0].index)}")

    celulas.round(6).to_csv(destino / "celulas.csv", index=False)
    unidades.round(6).to_csv(destino / "unidades.csv", index=False)
    frequencias.to_csv(destino / "frequencias.csv", index=False)
    datas = [(brutos / "obis" / f"{c}.json").stat().st_mtime for c in celulas["celula"] if (brutos / "obis" / f"{c}.json").exists()]
    coleta = {
        "coletado_em": datetime.fromtimestamp(max(datas), timezone.utc).isoformat(timespec="minutes"),
        "coleta_iniciada_em": datetime.fromtimestamp(min(datas), timezone.utc).isoformat(timespec="minutes"),
        "api": API,
        "relevo": "ETOPO1 (NOAA NGDC), amostrado a cada 0,5° pelo ERDDAP da NOAA CoastWatch (etopo180)",
        "costa": "Natural Earth 1:110m coastline (domínio público)",
        "grade": {"passo_graus": PASSO, "lat_min": LAT_MIN, "lat_max": LAT_MAX},
        "faixas": {f: [a, b] for f, _, a, b in FAIXAS},
        "ano_de_corte": ANO_DE_CORTE,
        "globais": globais,
        "linhas": {"celulas": len(celulas), "unidades": len(unidades), "frequencias": len(frequencias)},
        "sha256_16": {n: _hash(destino / n) for n in ("celulas.csv", "unidades.csv", "frequencias.csv")},
    }
    (destino / "coleta.json").write_text(json.dumps(coleta, indent=2, ensure_ascii=False), encoding="utf-8")
    return coleta


# ----------------------------------------------------------------------------------------------
# Carga
# ----------------------------------------------------------------------------------------------


def carregar(pasta: Path = PASTA) -> dict:
    """Lê o extrato agregado versionado. Confere o hash gravado na coleta."""
    coleta = json.loads((pasta / "coleta.json").read_text(encoding="utf-8"))
    for nome, esperado in coleta["sha256_16"].items():
        if _hash(pasta / nome) != esperado:
            raise RuntimeError(f"{nome} não confere com o hash registrado na coleta")
    unidades = pd.read_csv(pasta / "unidades.csv", keep_default_na=True)
    unidades["maior_conjunto_titulo"] = unidades["maior_conjunto_titulo"].fillna("")
    return {
        "celulas": pd.read_csv(pasta / "celulas.csv"),
        "unidades": unidades,
        "frequencias": pd.read_csv(pasta / "frequencias.csv"),
        "coleta": coleta,
        "costa": carregar_costa(pasta),
    }


def carregar_costa(pasta: Path = PASTA) -> list[np.ndarray]:
    """Linhas de costa como lista de matrizes (longitude, latitude)."""
    geo = json.loads((pasta / "costa_natural_earth_110m.geojson").read_text(encoding="utf-8"))
    linhas = []
    for feicao in geo["features"]:
        g = feicao["geometry"]
        partes = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
        linhas.extend(np.asarray(p, dtype=float)[:, :2] for p in partes)
    return linhas


def frequencias_da_unidade(frequencias: pd.DataFrame, periodo: str = "todos") -> dict[tuple[str, str], np.ndarray]:
    """{(célula, faixa): vetor de registros por espécie}, reconstruído da distribuição de frequência.

    A identidade das espécies não importa para os estimadores, só quantas têm 1, 2, 3... registros.
    """
    saida = {}
    recorte = frequencias[frequencias["periodo"] == periodo]
    for (celula, faixa), grupo in recorte.groupby(["celula", "faixa"], sort=False):
        saida[(celula, faixa)] = np.repeat(grupo["k"].to_numpy(np.int64), grupo["f"].to_numpy(np.int64))
    return saida
