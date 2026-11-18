# Publicação no pages.autz.com.br

Uma pasta por projeto na raiz, com `index.html`. O endereço fica `https://pages.autz.com.br/<slug>/`.

## Toda página nova

1. No `<head>` do `index.html`: `<meta name="robots" content="noindex,nofollow">`. O `robots.txt` da raiz também pede para os buscadores não indexarem o site. O workflow `Expirar propostas (7 dias)` confere a meta de hora em hora quando a troca automática estiver ligada; até lá, coloque a meta na publicação.
2. Na mesma pasta, `published.json` com a data de publicação em ISO 8601, no fuso de São Paulo:

```json
{
  "published_at": "2026-11-18T14:30:00-03:00",
  "tipo": "proposta",
  "expira": true,
  "publicado_por": "Claude (processo AUTZ)"
}
```

`tipo`: `proposta`, `diagnostico`, `reuniao`, `email` ou `outro`.
Em proposta, `expira` fica `true` (salvo se o Mika pedir para manter no ar). Nos demais tipos, use `"expira": false`.

## Expiração em 7 dias (168 horas)

- A regra vale só para proposta: slug `proposta-*`, slugs equivalentes (`adz-demarchi-target-rdstation`, `zummo-app-fase1`) ou `tipo` `proposta` no `published.json`. Um playbook que só cita "proposta" no título (ex.: `delav-roadmap`) não entra.
- Depois de 7 dias, a pasta não é apagada e a URL continua a mesma. O conteúdo publicado é trocado pela página `.github/templates/proposta-expirada.html` (mensagem "Esta proposta está fora da validade. Fale com a AUTZ.", contato `contato@autz.com.br` e link para https://autz.com.br, com noindex). O `published.json` ganha `"status": "expirada"`.
- Isso só acontece sozinho na pasta com `published.json` de `tipo` `proposta`, criada depois de 18/11/2026 14:00 (CORTE no workflow), 7 dias depois de `published_at`, e só quando o dry-run estiver desligado. O workflow grava a troca num commit normal (sem force-push).
- Até o Mika confirmar, o workflow roda em dry-run (`DRY_RUN: 'true'`): lista o que seria trocado e não altera nada no site.
- Para uma proposta não expirar: `"expira": false`.
- Diagnóstico, reunião, e-mail e outro não expiram (e-mail precisa ficar no ar porque as imagens são usadas no RD).
- Pastas antigas (sem `published.json` ou criadas antes do CORTE) ficam com o conteúdo original. A troca do legado está desligada (`DELETE_LEGACY: 'false'`, `DRY_RUN_LEGACY: 'true'`) até o Mika confirmar.
- `assets/`, `.github/` e arquivos soltos da raiz nunca são alterados por esta regra.
- Cada execução grava o relatório (resumo da execução no Actions e artifact `relatorio-expiracao`) com pasta, data, idade, se passou de 7 dias e classificação.
- O conteúdo original da proposta sai do site, mas permanece no histórico do Git (o repositório é público). Avise no texto da proposta que o link fica no ar por 7 dias.

## Ligar e desligar

No `.github/workflows/expirar-paginas.yml`:

- `DRY_RUN: 'true'` (estado atual): só lista, não altera o site, inclusive nas execuções agendadas. Só mude isso com OK do Mika.
- `EXPIRAR_NOVAS: 'false'` desliga a expiração das propostas novas.
- `DELETE_LEGACY: 'true'` e `DRY_RUN_LEGACY: 'false'` ligariam a troca das propostas antigas com mais de 7 dias pela página de validade encerrada. Só com OK do Mika.
