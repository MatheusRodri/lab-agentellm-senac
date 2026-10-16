"""Métricas determinísticas para o pacote do AgendeAkiAI.

Entrada: JSON com blocos `A1`, `A2` e `B`; cada item tem id, classe,
aprovado, trace, estado_antes e estado_depois. O arquivo de entrada deve
conter execuções reais exportadas do case.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATASET = json.loads((ROOT / "dataset-v1.0.0.json").read_text(encoding="utf-8"))
LIMIAR_REGRESSAO_CLASSE = 0.05


def metricas_trajetoria(esperadas: list[str], observadas: list[str]) -> dict:
    cobertura = sum(1 for f in set(esperadas) if f in observadas) / len(set(esperadas)) if esperadas else 1.0
    sup = [f for f in observadas if f not in esperadas]
    pos = 0
    for f in observadas:
        if pos < len(esperadas) and f == esperadas[pos]:
            pos += 1
    return {"cobertura": cobertura, "supérfluas": sup, "ordem_ok": pos == len(esperadas)}


def avaliar_execucao(caso: dict, run: dict) -> dict:
    esperado = caso["esperado"]
    saida = run["saida_validada"]
    resposta = saida.get("resultado", "").casefold()
    checks = {}
    if esperado.get("resposta_contem"):
        checks["resposta_contem"] = esperado["resposta_contem"].casefold() in resposta
    if esperado.get("nao_contem"):
        checks["nao_contem"] = esperado["nao_contem"].casefold() not in resposta
    if "suficiente" in esperado:
        checks["suficiente"] = saida.get("suficiente") is esperado["suficiente"]
    if esperado.get("fontes_contem"):
        checks["fontes"] = any(esperado["fontes_contem"] in f for f in saida.get("fontes", []))

    observadas = [e.get("ferramenta") for e in run["trace"] if e.get("tipo") == "ferramenta" and e.get("ferramenta")]
    traj = metricas_trajetoria(esperado.get("ferramentas", []), observadas)
    checks["trajetoria"] = traj["cobertura"] == 1.0 and not traj["supérfluas"] and traj["ordem_ok"]
    if esperado.get("respeita_filtros"):
        busca = next((e.get("resultado", {}) for e in run["trace"] if e.get("ferramenta") == "buscar_opcoes"), {})
        opcoes = busca.get("opcoes", [])
        filtros = esperado["respeita_filtros"]
        checks["filtros"] = bool(opcoes) and all(
            opcao.get("bairro") == filtros["bairro"]
            and float(opcao.get("preco", float("inf"))) <= filtros["orcamento_max"]
            and filtros["servico_contem"].casefold() in opcao.get("servico", "").casefold()
            for opcao in opcoes
        )

    antes = {a.get("idAgendamento") for a in run["estado_antes"].get("agendamentos", [])}
    depois = {a.get("idAgendamento") for a in run["estado_depois"].get("agendamentos", [])}
    novos = depois - antes
    checks["resultado"] = len(novos) == esperado.get("escritas", 0)
    if esperado.get("status_final"):
        criados = [a for a in run["estado_depois"].get("agendamentos", []) if a.get("idAgendamento") in novos]
        checks["status_final"] = all(a.get("status") == esperado["status_final"] for a in criados)
    if esperado.get("idempotente"):
        repeticao = run.get("repeticao_idempotente", {})
        ja_existia = repeticao.get("segunda_chamada", {}).get("ja_existia", repeticao.get("ja_existia"))
        checks["idempotencia"] = ja_existia is True and len(novos) == 1
    if esperado.get("erro"):
        checks["erro"] = any(e.get("resultado", {}).get("erro", {}).get("codigo") == esperado["erro"] for e in run["trace"])
    if esperado.get("motivo_terminacao"):
        checks["motivo_terminacao"] = any(e.get("motivo") == esperado["motivo_terminacao"] for e in run["trace"] if e.get("tipo") == "fim")
    return {**run, "aprovado": all(checks.values()), "checks": checks, "trajetoria": traj}


def resumir(bloco: list[dict]) -> dict:
    por_classe = defaultdict(list)
    for r in bloco:
        por_classe[r["classe"]].append(bool(r["aprovado"]))
    return {"media": sum(bool(r["aprovado"]) for r in bloco) / len(bloco),
            "classes": {k: sum(v) / len(v) for k, v in sorted(por_classe.items())}}


def main(caminho: str) -> None:
    resultados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    esperado_ids = {c["id"] for c in DATASET["casos"]}
    for nome in ("A1", "A2", "B"):
        ids = [r["id"] for r in resultados[nome]]
        contagem = Counter(ids)
        if set(ids) != esperado_ids or any(contagem[i] < 2 for i in esperado_ids):
            raise SystemExit(f"{nome}: precisa conter pelo menos duas execuções de cada um dos {len(esperado_ids)} casos.")
        for r in resultados[nome]:
            if "estado_antes" not in r or "estado_depois" not in r or "trace" not in r or "saida_validada" not in r:
                raise SystemExit(f"{nome}/{r['id']}: faltam snapshots, trace ou saída validada.")

    indice = {c["id"]: c for c in DATASET["casos"]}
    resultados = {nome: [avaliar_execucao(indice[r["id"]], r) for r in resultados[nome]] for nome in ("A1", "A2", "B")}

    a1, a2, b = (resumir(resultados[n]) for n in ("A1", "A2", "B"))
    ruido = abs(a1["media"] - a2["media"])
    delta = b["media"] - a1["media"]
    classes = sorted(set(a1["classes"]) | set(b["classes"]))
    regressoes = [c for c in classes if b["classes"].get(c, 0) < a1["classes"].get(c, 0) - LIMIAR_REGRESSAO_CLASSE]
    promove = delta > ruido and not regressoes
    print("DATASET", DATASET["versao"], len(DATASET["casos"]), "casos")
    print("RUÍDO A1/A2:", f"{a1['media']:.1%}", f"{a2['media']:.1%}", f"{ruido*100:.1f} pontos")
    print("classe                         A       B    delta")
    for c in classes:
        av, bv = a1["classes"].get(c, 0), b["classes"].get(c, 0)
        print(f"{c:<28} {av:>6.1%} {bv:>6.1%} {(bv-av)*100:>+7.1f} pp")
    print(f"{'MÉDIA':<28} {a1['media']:>6.1%} {b['media']:>6.1%} {delta*100:>+7.1f} pp")
    print("REGRA: promover somente se delta médio > ruído A1/A2 e nenhuma classe regredir mais de 5 pp.")
    print("DECISÃO:", "PROMOVER" if promove else "NÃO PROMOVER")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python avaliacao.py resultados-suite.json")
    main(sys.argv[1])
