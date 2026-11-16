#!/usr/bin/env python3
"""Busca licitações com propostas abertas no PNCP para municípios
num raio ao redor de Itupeva-SP e grava em data.json."""
import csv, io, json, math, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone

CENTRO = (-23.1526, -47.0586)   # Itupeva-SP
RAIO_KM = 100
DIAS_A_FRENTE = 180             # traz licitações que encerram propostas até daqui a N dias
PNCP = "https://pncp.gov.br/api/consulta/v1/contratacoes/proposta"
MUNICIPIOS = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
UF = {11:"RO",12:"AC",13:"AM",14:"RR",15:"PA",16:"AP",17:"TO",21:"MA",22:"PI",23:"CE",24:"RN",
      25:"PB",26:"PE",27:"AL",28:"SE",29:"BA",31:"MG",32:"ES",33:"RJ",35:"SP",41:"PR",42:"SC",
      43:"RS",50:"MS",51:"MT",52:"GO",53:"DF"}

def get(url, tentativas=5):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "portal-licitacoes/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                corpo = r.read()
                return corpo.decode("utf-8") if corpo else ""
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tentativas - 1:
                time.sleep(3 * (i + 1)); continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if i < tentativas - 1:
                time.sleep(3 * (i + 1)); continue
            raise

def km(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))

def cidades_no_raio():
    texto = get(MUNICIPIOS)
    achadas = {}
    for l in csv.DictReader(io.StringIO(texto)):
        d = km(CENTRO, (float(l["latitude"]), float(l["longitude"])))
        if d <= RAIO_KM:
            achadas[int(l["codigo_ibge"])] = {"nome": l["nome"], "uf": UF[int(l["codigo_uf"])], "km": round(d)}
    return achadas

def main():
    cidades = cidades_no_raio()
    ufs = sorted({c["uf"] for c in cidades.values()})
    print(f"{len(cidades)} municípios no raio de {RAIO_KM} km; UFs: {ufs}")
    hoje = date.today()
    limite = (hoje + timedelta(days=DIAS_A_FRENTE)).strftime("%Y%m%d")
    itens, vistos = [], set()
    for uf in ufs:
        pagina, total = 1, 1
        while pagina <= total:
            q = urllib.parse.urlencode({"dataFinal": limite, "uf": uf, "pagina": pagina, "tamanhoPagina": 50})
            texto = get(f"{PNCP}?{q}")
            if not texto:
                break
            j = json.loads(texto)
            total = j.get("totalPaginas") or 1
            for c in j.get("data", []):
                u, o = c.get("unidadeOrgao") or {}, c.get("orgaoEntidade") or {}
                ibge = u.get("codigoIbge")
                try: ibge = int(ibge)
                except (TypeError, ValueError): continue
                if ibge not in cidades:
                    continue
                id_ = c.get("numeroControlePNCP")
                enc = c.get("dataEncerramentoProposta") or ""
                if id_ in vistos or (enc and enc[:10] < hoje.isoformat()):
                    continue
                vistos.add(id_)
                itens.append({
                    "id": id_,
                    "objeto": (c.get("objetoCompra") or "").strip(),
                    "valor": c.get("valorTotalEstimado"),
                    "modalidade": c.get("modalidadeNome") or "Outra",
                    "orgao": o.get("razaoSocial") or "",
                    "esfera": {"M": "Municipal", "E": "Estadual", "F": "Federal"}.get(o.get("esferaId"), ""),
                    "cidade": cidades[ibge]["nome"], "uf": cidades[ibge]["uf"], "km": cidades[ibge]["km"],
                    "abertura": c.get("dataAberturaProposta"), "encerramento": enc,
                    "link": f"https://pncp.gov.br/app/editais/{o.get('cnpj')}/{c.get('anoCompra')}/{c.get('sequencialCompra')}",
                    "origem": c.get("linkSistemaOrigem") or "",
                })
            print(f"{uf}: página {pagina}/{total}, {len(itens)} licitações até agora")
            pagina += 1
            time.sleep(0.3)
    if not itens:
        sys.exit("Nenhuma licitação encontrada: mantendo o data.json anterior.")
    itens.sort(key=lambda x: x["encerramento"] or "9")
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({"atualizado": datetime.now(timezone.utc).isoformat(), "raio_km": RAIO_KM,
                   "itens": itens}, f, ensure_ascii=False)
    print(f"Gravado data.json com {len(itens)} licitações.")

if __name__ == "__main__":
    main()
