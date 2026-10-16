"""Executa o juiz da rubrica v1.0.0 contra rótulos manuais.

Usar com 30 respostas reais e rótulos registrados em rotulos-humanos.json.
Importa o cliente compartilhado da pasta pai da Aula 11.
"""

import json
import sys
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from cliente import MODELO, MODELO_JUIZ, PROVEDOR, juiz as modelo_juiz  # noqa: E402

LIMIAR = 0.85  # declarado em 2026-10-09, antes da coleta de resultados


class Veredito(BaseModel):
    adequada: bool = Field(description="A resposta atende à rubrica binária?")
    evidencia: str = Field(description="Trecho ou razão específica do veredito.")


RUBRICA = (ROOT / "rubrica-v1.0.0.md").read_text(encoding="utf-8")
JUIZ = modelo_juiz.with_structured_output(Veredito)


def julgar(item: dict) -> Veredito:
    entrada = (
        f"INTENÇÃO DO CLIENTE:\n{item['intencao']}\n\n"
        f"ESTADO E FONTES VERIFICADAS:\n{item['contexto']}\n\n"
        f"RESPOSTA FINAL:\n{item['resposta']}"
    )
    return JUIZ.invoke([
        {"role": "system", "content": RUBRICA},
        {"role": "user", "content": entrada},
    ])


def main() -> None:
    dados = json.loads((ROOT / "rotulos-humanos.json").read_text(encoding="utf-8"))
    casos = dados["casos"]
    if len(casos) < 30:
        raise SystemExit(f"São necessários 30 rótulos manuais; encontrados {len(casos)}.")
    if any(not isinstance(c.get("humano"), bool) or not c.get("nota_humana") for c in casos):
        raise SystemExit("Cada caso precisa de humano (booleano) e nota_humana antes da chamada ao juiz.")

    matriz = {"vp": 0, "fp": 0, "fn": 0, "vn": 0}
    desacordos = []
    for item in casos:
        try:
            veredito = julgar(item)
        except Exception as erro:
            print(f"SEM VEREDITO {item['id']}: {erro}")
            desacordos.append({"id": item["id"], "classe": "defeito do juiz", "motivo": "saída inválida/erro"})
            continue
        humano, juiz = item["humano"], veredito.adequada
        chave = ("v" if humano == juiz else "f") + ("p" if juiz else "n")
        matriz[chave] += 1
        print(json.dumps({"id": item["id"], "humano": humano, "juiz": juiz, "evidencia": veredito.evidencia}, ensure_ascii=False))
        if humano != juiz:
            desacordos.append({"id": item["id"], "classe": "PENDENTE DE LEITURA", "motivo": item["nota_humana"], "evidencia_juiz": veredito.evidencia})

    total = len(casos)
    concordancia = (matriz["vp"] + matriz["vn"]) / total
    print(f"MATRIZ humano(sim/não) x juiz(sim/não): {matriz}")
    print(f"Concordância: {concordancia:.1%}; limiar: {LIMIAR:.0%}; veredito: {'ADOTAR' if concordancia >= LIMIAR and not desacordos else 'NÃO ADOTAR AINDA'}")
    print("Desacordos precisam de classificação individual como defeito do juiz, da rubrica ou do rótulo humano antes da adoção.")
    (ROOT / "resultados-juiz.json").write_text(json.dumps({"provedor": PROVEDOR, "modelo_sistema": MODELO, "modelo_juiz": MODELO_JUIZ, "rubrica": "1.0.0", "limiar": LIMIAR, "matriz": matriz, "concordancia": concordancia, "desacordos": desacordos}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
