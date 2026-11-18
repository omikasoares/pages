#!/usr/bin/env python3
"""Garante <meta name="robots" content="noindex,nofollow"> em toda página HTML do pages.

Uso: python3 .github/scripts/noindex.py [--checar]
  --checar só lista o que mudaria, sem gravar.
Não mexe no conteúdo visível: só acrescenta (ou corrige) a meta no <head>.
Se a página já tem meta robots com noindex e nofollow, fica como está; se tem
outra combinação, o content vira noindex,nofollow; meta robots repetida é removida.
"""
import pathlib, re, sys

META = '<meta name="robots" content="noindex,nofollow">'
RE_ROBOTS = re.compile(r'<meta\b[^>]*\bname\s*=\s*["\']robots["\'][^>]*>', re.I)


def ajustar(txt):
    nl = "\r\n" if "\r\n" in txt else "\n"
    achadas = list(RE_ROBOTS.finditer(txt))
    if achadas:
        primeira = achadas[0]
        tag = primeira.group(0)
        m = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag, re.I)
        valores = {v.strip().lower() for v in (m.group(1) if m else "").split(",")}
        nova = tag if {"noindex", "nofollow"} <= valores else META
        # remove as repetidas de trás para frente, depois troca a primeira se precisar
        for x in reversed(achadas[1:]):
            ini, fim = x.span()
            if txt[fim:fim + len(nl)] == nl:
                fim += len(nl)
            txt = txt[:ini] + txt[fim:]
        return txt[:primeira.start()] + nova + txt[primeira.end():]
    m = re.search(r'<head\b[^>]*>', txt, re.I)
    if m:
        return txt[:m.end()] + nl + META + txt[m.end():]
    # página sem <head>: entra antes da primeira tag de cabeçalho (o navegador trata como head)
    m = re.search(r'<(meta|title|link|style|base)\b', txt, re.I)
    if m:
        return txt[:m.start()] + META + nl + txt[m.start():]
    m = re.search(r'<html\b[^>]*>', txt, re.I)
    pos = m.end() if m else 0
    return txt[:pos] + (nl if m else "") + META + nl + txt[pos:]


def main():
    so_checar = "--checar" in sys.argv
    alterados = []
    for p in sorted(pathlib.Path(".").rglob("*.html")):
        if any(parte.startswith(".") for parte in p.parts):
            continue
        # newline="" preserva CRLF/LF de cada arquivo
        with open(p, encoding="utf-8", errors="surrogateescape", newline="") as f:
            txt = f.read()
        novo = ajustar(txt)
        if novo != txt:
            alterados.append(p.as_posix())
            if not so_checar:
                with open(p, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
                    f.write(novo)
    print(f"{len(alterados)} página(s) {'a ajustar' if so_checar else 'ajustada(s)'} com noindex:")
    print("\n".join(alterados))
    return alterados


if __name__ == "__main__":
    main()
