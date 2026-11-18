#!/usr/bin/env python3
"""Expiração de propostas do pages.autz.com.br (7 dias / 168 horas por padrão).

Roda de hora em hora pelo workflow .github/workflows/expirar-paginas.yml e também à mão:
  python3 .github/scripts/expirar.py
  DRY_RUN=true HORAS=168 python3 .github/scripts/expirar.py

Data de publicação de cada pasta da raiz:
  1. <pasta>/published.json -> {"published_at": "2026-11-18T14:30:00-03:00", "tipo": "proposta", "expira": true}
  2. sem published.json: data do primeiro commit que criou a pasta (só para listar).

Quando uma proposta vence, o script NÃO apaga a pasta e NÃO muda a URL.
Ele troca o conteúdo publicado por a página .github/templates/proposta-expirada.html
(index.html com noindex) e um published.json com status "expirada".
O conteúdo original sai do site, mas permanece no histórico do Git.

A troca automática acontece quando TUDO isto vale:
  - a pasta é proposta (published.json com tipo "proposta", slug proposta-*,
    ou slug na lista SLUGS_PROPOSTA: adz-demarchi-target-rdstation, zummo-app-fase1);
  - expira diferente de false;
  - passaram HORAS (168, 7 dias) desde published_at ou, se não houver, do primeiro commit;
  - o prazo de 7 dias termina depois do CORTE (se já tinha vencido no CORTE, é legado
    e só sai com DELETE_LEGACY=true);
  - EXPIRAR_NOVAS=true e DRY_RUN=false;
  - a pasta ainda não está com status "expirada".

Nas execuções agendadas, DRY_RUN=false: propostas que vencem depois do CORTE
são trocadas automaticamente ao completar 168 horas (mesmo as publicadas antes do CORTE,
se o prazo de 7 dias ainda não tinha acabado no CORTE).
Pastas já vencidas no CORTE (legado, ex.: proposta-integracao-rd-cvcrm) só seriam
trocadas com DELETE_LEGACY=true e DRY_RUN_LEGACY=false. Diagnóstico, e-mail, reunião
e outro nunca expiram. Nunca mexe em assets/, pastas que começam com ponto nem
arquivos soltos da raiz.

Variáveis: HORAS (168), EXPIRAR_NOVAS (true), DRY_RUN (true), DELETE_LEGACY (false),
DRY_RUN_LEGACY (true), CORTE (ISO 8601), RELATORIO_DIR (relatorio-expiracao).
Grava RELATORIO_DIR/relatorio.md e relatorio.csv e, no Actions, o resumo da execução.
"""
import csv, html, json, os, pathlib, re, shutil, subprocess, sys
from datetime import datetime, timedelta, timezone

BRT = timezone(timedelta(hours=-3))
PROTEGIDAS = {"assets"}
SLUGS_PROPOSTA = {"adz-demarchi-target-rdstation", "zummo-app-fase1"}
MODELO = pathlib.Path(".github/templates/proposta-expirada.html")


def flag(nome, padrao):
    return os.environ.get(nome, padrao).strip().lower() in ("1", "true", "sim", "yes")


HORAS = float(os.environ.get("HORAS", "168"))
EXPIRAR_NOVAS = flag("EXPIRAR_NOVAS", "true")
DRY_RUN = flag("DRY_RUN", "true")
DELETE_LEGACY = flag("DELETE_LEGACY", "false")
DRY_RUN_LEGACY = flag("DRY_RUN_LEGACY", "true")
CORTE = datetime.fromisoformat(os.environ.get("CORTE", "2026-11-18T14:00:00-03:00"))
SAIDA = pathlib.Path(os.environ.get("RELATORIO_DIR", "relatorio-expiracao"))
AGORA = datetime.fromisoformat(os.environ["AGORA"]) if os.environ.get("AGORA") else datetime.now(timezone.utc)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def primeiro_commit(pasta):
    datas = git("log", "--diff-filter=A", "--format=%aI", "--", pasta).splitlines()
    return datetime.fromisoformat(datas[-1]) if datas else None


def titulo(pasta):
    p = pathlib.Path(pasta, "index.html")
    if not p.exists():
        return ""
    m = re.search(r"<title>(.*?)</title>", p.read_text(encoding="utf-8", errors="replace")[:60000], re.I | re.S)
    return html.unescape(m.group(1)).strip().replace("\ufeff", "") if m else ""


def classificar(slug, tit, tipo=None):
    if tipo:
        return tipo
    s, t = slug.lower(), tit.lower()
    if slug in PROTEGIDAS:
        return "asset"
    if slug in SLUGS_PROPOSTA or s.startswith("proposta-"):
        return "proposta"
    if "-email-" in s or s.endswith("-emails") or s.startswith("email-"):
        return "e-mail"
    if "reuniao" in s or "reunião" in t:
        return "reuniao"
    if "diagnostico" in s or "diagnóstico" in t:
        return "diagnostico"
    return "outro"


def eh_proposta(classe, meta):
    if classe == "proposta":
        return True
    tipo = (meta or {}).get("tipo") if meta and "erro" not in meta else None
    return tipo == "proposta"


def ler_meta(pasta):
    p = pathlib.Path(pasta, "published.json")
    if not p.exists():
        return None, None
    try:
        meta = json.loads(p.read_text(encoding="utf-8"))
        return meta, datetime.fromisoformat(meta["published_at"]) if meta.get("published_at") else None
    except Exception as e:
        return {"erro": str(e)[:120]}, None


def ja_expirada(meta):
    return bool(meta) and "erro" not in meta and meta.get("status") == "expirada"


def substituir_por_pagina_expirada(pasta, meta, publicada, criada):
    """Troca o conteúdo publicado da pasta pela página de validade encerrada.

    Arquivos atuais saem do working tree (e, no commit da Action, do site).
    O original permanece no histórico do Git.
    """
    modelo = MODELO.read_text(encoding="utf-8")
    raiz = pathlib.Path(pasta)
    rastreados = git("ls-files", "-z", "--", pasta).split("\0")
    rastreados = [x for x in rastreados if x]
    if rastreados:
        git("rm", "-q", "-r", "--ignore-unmatch", "--", pasta)
    if raiz.exists():
        for filho in raiz.iterdir():
            if filho.is_dir():
                shutil.rmtree(filho)
            else:
                filho.unlink()
    else:
        raiz.mkdir(parents=True, exist_ok=True)
    (raiz / "index.html").write_text(modelo, encoding="utf-8")
    origem = publicada or criada
    novo = {
        "published_at": origem.isoformat() if origem else AGORA.astimezone(BRT).isoformat(),
        "tipo": "proposta",
        "expira": True,
        "status": "expirada",
        "expirada_em": AGORA.astimezone(BRT).isoformat(),
    }
    if meta and "erro" not in meta:
        if meta.get("publicado_por"):
            novo["publicado_por"] = meta["publicado_por"]
        if meta.get("published_at"):
            novo["published_at"] = meta["published_at"]
    (raiz / "published.json").write_text(json.dumps(novo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git("add", "--", f"{pasta}/index.html", f"{pasta}/published.json")


def main():
    linhas, trocadas = [], []
    for d in sorted(x for x in os.listdir(".") if os.path.isdir(x)):
        if d.startswith("."):
            continue
        criada = primeiro_commit(d)
        meta, publicada = ler_meta(d)
        data = publicada or criada
        idade = (AGORA - data).total_seconds() / 3600 if data else None
        passou = idade is not None and idade >= HORAS
        tipo = (meta or {}).get("tipo") if meta and "erro" not in meta else None
        classe = classificar(d, titulo(d), tipo)
        proposta = eh_proposta(classe, meta)
        # Legado protegido: proposta cujo prazo de 7 dias já tinha acabado no CORTE.
        # Ex.: proposta-integracao-rd-cvcrm. As que ainda estavam no prazo no CORTE
        # (adz-demarchi, zummo, glauciane) seguem a troca automática.
        vencida_no_corte = data is not None and (data + timedelta(hours=HORAS)) <= CORTE
        if d in PROTEGIDAS:
            grupo = "protegida"
        elif not proposta:
            grupo = "nao-expira"
        elif vencida_no_corte:
            grupo = "legado"
        else:
            grupo = "automatica"
        if d in PROTEGIDAS:
            acao = "protegida"
        elif not proposta:
            acao = "não expira (não é proposta)"
        elif ja_expirada(meta):
            acao = "já substituída (fora da validade)"
        elif (meta or {}).get("expira") is False:
            acao = "mantida (não expira)"
        elif grupo == "legado":
            if passou and DELETE_LEGACY and not DRY_RUN_LEGACY and not DRY_RUN:
                substituir_por_pagina_expirada(d, meta, publicada, criada)
                acao = "SUBSTITUÍDA (legado, fora da validade)"
                trocadas.append(d)
            elif passou:
                acao = "legado: substituiria por página de validade encerrada se ligado (desligado)"
            else:
                acao = "legado: dentro do prazo de 7 dias"
        else:
            if not passou:
                acao = "no ar (dentro do prazo de 7 dias)"
            elif EXPIRAR_NOVAS and not DRY_RUN:
                substituir_por_pagina_expirada(d, meta, publicada, criada)
                acao = "SUBSTITUÍDA (fora da validade)"
                trocadas.append(d)
            else:
                acao = "substituiria por página de validade encerrada (dry-run)"
        linhas.append({
            "slug": d,
            "origem_data": "published.json" if publicada else "primeiro commit",
            "publicada_em": data.astimezone(BRT).strftime("%d/%m/%Y %H:%M") if data else "-",
            "idade_horas": round(idade, 1) if idade is not None else "",
            "passou_7d": "sim" if passou else "não",
            "classificacao": classe,
            "grupo": grupo,
            "acao": acao,
            "erro_published_json": (meta or {}).get("erro", "") if meta else "",
        })

    SAIDA.mkdir(parents=True, exist_ok=True)
    campos = list(linhas[0].keys()) if linhas else []
    with open(SAIDA / "relatorio.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)
    cab = (
        f"# Expiração de propostas ({HORAS:g}h, 7 dias)\n\n"
        f"Execução: {AGORA.astimezone(BRT).strftime('%d/%m/%Y %H:%M')} (America/Sao_Paulo). "
        f"EXPIRAR_NOVAS={str(EXPIRAR_NOVAS).lower()}, DRY_RUN={str(DRY_RUN).lower()}, "
        f"DELETE_LEGACY={str(DELETE_LEGACY).lower()}, DRY_RUN_LEGACY={str(DRY_RUN_LEGACY).lower()}, CORTE={CORTE.isoformat()}.\n\n"
        f"Pastas: {len(linhas)}. Substituídas nesta execução: {len(trocadas)}"
        + (f" ({', '.join(trocadas)})" if trocadas else "") + ".\n\n"
    )
    tab = (
        "| Pasta | Publicada em | Origem da data | Idade (h) | Passou de 7 dias | "
        "Classificação | Grupo | Ação |\n|---|---|---|---|---|---|---|---|\n"
    )
    tab += "".join(
        f"| {l['slug']} | {l['publicada_em']} | {l['origem_data']} | {l['idade_horas']} | "
        f"{l['passou_7d']} | {l['classificacao']} | {l['grupo']} | {l['acao']} |\n"
        for l in linhas
    )
    md = cab + tab
    (SAIDA / "relatorio.md").write_text(md, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md)
    print(cab.strip())
    propostas = [l for l in linhas if l["classificacao"] == "proposta"]
    vencidas = [l for l in propostas if l["passou_7d"] == "sim" and not l["acao"].startswith("já substituída")]
    print(f"Propostas: {len(propostas)}. Já passaram de 7 dias (ainda no conteúdo original): {len(vencidas)}"
          + (": " + ", ".join(l["slug"] for l in vencidas) if vencidas else "."))
    for l in propostas:
        print(f"  - {l['slug']}: {l['publicada_em']} ({l['origem_data']}, {l['idade_horas']}h, {l['acao']})")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"substituidas={' '.join(trocadas)}\n")


if __name__ == "__main__":
    sys.exit(main())
