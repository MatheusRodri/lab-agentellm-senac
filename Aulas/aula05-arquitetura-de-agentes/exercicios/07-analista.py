"""Exercício 5 — solução curta. Execute: python 07-analista.py"""
import argparse, hashlib, json, os, sys, time
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIConnectionError, APIStatusError

PASTA=Path(__file__).parent; PROMPTS=PASTA/"prompts"; LOG=PASTA/"aula05-log.txt"
HOJE=date(2026,9,15); ALCADA=500.
POLITICA={"refeicao":{"artigo":"Art. 4","teto_por_pessoa":120.,"exige_nota":True},"transporte":{"artigo":"Art. 5","teto_unitario":90.,"exige_nota":False},"hospedagem":{"artigo":"Art. 6","teto_diaria":380.,"exige_nota":True},"material":{"artigo":"Art. 9","teto_unitario":50.,"exige_nota":True}}
FUNCIONARIOS={"F-088":{"nome":"Ana Souza"},"F-091":{"nome":"Bruno Lima"},"F-103":{"nome":"Célia Rocha"}}
DESPESAS={
"D-4471":{"funcionario":"F-088","categoria":"refeicao","valor":84.,"pessoas":1,"tem_nota":True,"descricao":"almoço em visita a cliente"},
"D-4472":{"funcionario":"F-091","categoria":"transporte","valor":45.,"pessoas":1,"tem_nota":False,"descricao":"táxi aeroporto-hotel"},
"D-4473":{"funcionario":"F-088","categoria":"refeicao","valor":312.,"pessoas":3,"tem_nota":True,"descricao":"jantar com equipe do cliente"},
"D-4474":{"funcionario":"F-103","categoria":"hospedagem","valor":1240.,"diarias":2,"tem_nota":True,"descricao":"hotel, congresso setorial"},
"D-4475":{"funcionario":"F-091","categoria":"refeicao","valor":96.,"pessoas":1,"tem_nota":True,"descricao":"jantar, viagem a trabalho"},
"D-4476":{"funcionario":"F-103","categoria":"material","valor":50.,"pessoas":1,"tem_nota":False,"descricao":"material de escritório"},
"D-4477":{"funcionario":"F-88","categoria":"transporte","valor":38.,"pessoas":1,"tem_nota":False,"descricao":"aplicativo, reunião externa"},
"D-4478":{"funcionario":"F-091","categoria":"transporte","valor":130.,"pessoas":1,"tem_nota":True,"descricao":"táxi, trajeto longo, madrugada"}}
RECIBOS={"D-4471":84.,"D-4472":45.,"D-4473":312.,"D-4474":1240.,"D-4475":196.,"D-4476":50.,"D-4477":38.,"D-4478":130.}
HISTORICO={"F-088":[{"despesa":"D-4102","veredito":"aprovado"}],"F-091":[{"despesa":"D-4210","veredito":"reprovado","motivo":"acima do teto"}],"F-103":[]}; PARECERES={}
load_dotenv(); MODELO=os.getenv("LLM_MODELO","mistral-small-latest")
client=OpenAI(base_url=os.getenv("LLM_BASE_URL","https://api.mistral.ai/v1"),api_key=os.getenv("OPENAI_API_KEY"),max_retries=0)

class Rota(str,Enum): REGRA="dentro_da_politica"; AGENTE="ambiguo"; HUMANO="acima_da_alcada"; FILA="nenhuma"
class Termino(str,Enum): RESPONDEU="RESPONDEU"; ORCAMENTO="ORCAMENTO"; ERRO_FATAL="ERRO_FATAL"; HUMANO="HUMANO"
@dataclass
class Passo: ferramenta:str|None; argumentos:dict; resultado:dict|None; erro:dict|None; tokens:int
@dataclass
class Estado:
    objetivo:str; passos:list[Passo]=field(default_factory=list); tokens_gastos:int=0; custo_estimado:float=0.; ferramentas_ativas:list[str]=field(default_factory=list); termino:Termino|None=None; motivo:str=""; resposta:str=""; contexto_por_passo:list[int]=field(default_factory=list); eventos:list[str]=field(default_factory=list); inicio:float=field(default_factory=time.monotonic)
@dataclass
class Orcamento:
    max_passos:int; max_tokens:int; max_reais:float; max_segundos:float; preco_entrada:float; preco_saida:float
    def excedido(self,e):
        if len(e.passos)>=self.max_passos:return "teto de passos"
        if e.tokens_gastos>=self.max_tokens:return "teto de tokens"
        if e.custo_estimado>=self.max_reais:return "teto de reais"
        if time.monotonic()-e.inicio>=self.max_segundos:return "teto de tempo"

# Carimbo: arquitetura também é versão, junto com prompt/modelo/parâmetros.
CONFIG={"triagem":("regra_em_codigo","—"),"ambiguo":("agente_react","analise-v3"),"lote":("orq_trabalhador","orquestra-v1"),"parecer":("avaliador_otim","avaliador-v2")}
def carregar(nome,**vs):
    t=(PROMPTS/f"{nome}.md").read_text(encoding="utf-8")
    for k,v in vs.items():t=t.replace("{{"+k+"}}",str(v))
    return t
def teto(d):
    p=POLITICA[d["categoria"]]
    return p.get("teto_por_pessoa",p.get("teto_diaria",p.get("teto_unitario")))*d.get("pessoas",d.get("diarias",1))
def rotear(id):
    d=DESPESAS[id]
    # A regra basta para valores, notas e cadastro; só ambiguidades usam LLM.
    if d["valor"]>ALCADA:return Rota.HUMANO,"acima da alçada"
    if d["categoria"] not in POLITICA:return Rota.FILA,"sem política"
    if d["funcionario"] not in FUNCIONARIOS:return Rota.AGENTE,"cadastro inválido"
    p=POLITICA[d["categoria"]]
    if RECIBOS[id]!=d["valor"] or (p["exige_nota"] and not d["tem_nota"]):return Rota.AGENTE,"divergência documental"
    if d.get("pessoas",1)>1 or d.get("diarias",1)>1 or d["valor"]>teto(d):return Rota.AGENTE,"análise contextual"
    return Rota.REGRA,"regra suficiente"

class Recuperavel(Exception):
    def __init__(self,erro,esperado,proximo_passo):self.d={"erro":erro,"esperado":esperado,"proximo_passo":proximo_passo}
def buscar_despesa(id):
    if id not in DESPESAS:raise Recuperavel("despesa não encontrada","D-XXXX","confira o id")
    return {"id":id,**DESPESAS[id]}
def consultar_politica(categoria):return POLITICA[categoria]
def consultar_historico(funcionario):
    if funcionario not in FUNCIONARIOS:raise Recuperavel("funcionário não encontrado","F-XXX, ex.: F-088","corrija F-88 para F-088")
    return {"funcionario":funcionario,"historico":HISTORICO[funcionario]}
def ler_recibo(despesa_id):return {"valor_recibo":RECIBOS[despesa_id]}
def registrar_parecer(despesa_id,veredito,justificativa,artigo,valores):
    chave=hashlib.sha256(json.dumps([despesa_id,veredito,justificativa,artigo,valores],ensure_ascii=False).encode()).hexdigest()[:16]
    if chave in PARECERES:return {**PARECERES[chave],"ja_existia":True}
    PARECERES[chave]={"id":despesa_id,"veredito":veredito,"justificativa":justificativa,"artigo":artigo,"valores":valores,"chave":chave}
    return {**PARECERES[chave],"ja_existia":False}
FUNCOES={"buscar_despesa":buscar_despesa,"consultar_politica":consultar_politica,"consultar_historico":consultar_historico,"ler_recibo":ler_recibo,"registrar_parecer":registrar_parecer}; LEITURA=list(FUNCOES)[:-1]
def declaracao(nome):
    ps={"buscar_despesa":{"id":{"type":"string"}},"consultar_politica":{"categoria":{"type":"string"}},"consultar_historico":{"funcionario":{"type":"string"}},"ler_recibo":{"despesa_id":{"type":"string"}},"registrar_parecer":{"despesa_id":{"type":"string"},"veredito":{"type":"string","enum":["aprovado","reprovado","revisao"]},"justificativa":{"type":"string"},"artigo":{"type":"string"},"valores":{"type":"string"}}}[nome]
    return {"type":"function","function":{"name":nome,"description":("ESCRITA idempotente." if nome=="registrar_parecer" else "Consulta de leitura."),"parameters":{"type":"object","properties":ps,"required":list(ps),"additionalProperties":False}}}
def chamar(msgs,orc,estado=None,ferramentas=None,schema=None,obrigatorio=False):
    try:
        kw={"model":MODELO,"messages":msgs,"temperature":0,"max_tokens":600}
        if ferramentas:kw["tools"]=[declaracao(x) for x in ferramentas]
        if obrigatorio:kw["tool_choice"]="required"
        if schema:kw["response_format"]={"type":"json_schema","json_schema":{"name":"saida","strict":True,"schema":schema}}
        r=client.chat.completions.create(**kw)
    except RateLimitError:raise RuntimeError("429: limite da API")
    except APIConnectionError:raise RuntimeError("falha de conexão")
    except APIStatusError as x:raise RuntimeError(f"API {x.status_code}")
    if estado:
        u=r.usage; estado.tokens_gastos+=u.total_tokens;estado.contexto_por_passo.append(u.prompt_tokens);estado.custo_estimado+=(u.prompt_tokens*orc.preco_entrada+u.completion_tokens*orc.preco_saida)/1_000_000
    return r
def agente(id,orc,limite):
    e=Estado(f"Analise {id}",ferramentas_ativas=LEITURA[:]); msgs=[{"role":"system","content":carregar("analise-v3",hoje=HOJE)},{"role":"user","content":e.objetivo}]; fase="analise"; ultima=""; vezes=0
    while True:
        if m:=orc.excedido(e):e.termino,e.motivo=Termino.ORCAMENTO,m;return e
        try:r=chamar(msgs,orc,e,e.ferramentas_ativas,obrigatorio=(fase=="registro"))
        except RuntimeError as x:e.termino,e.motivo=Termino.ERRO_FATAL,str(x);return e
        msg=r.choices[0].message
        if not msg.tool_calls:
            if fase=="analise":
                # Exposição por fase: a escrita não existia antes deste ponto.
                fase="registro";e.ferramentas_ativas=["registrar_parecer"];msgs += [{"role":"assistant","content":msg.content or ""},{"role":"user","content":"Agora use registrar_parecer para gravar sua conclusão."}];continue
            e.termino,e.motivo,e.resposta=Termino.RESPONDEU,"concluído",msg.content or "";return e
        msgs.append(msg.model_dump(exclude_none=True))
        for c in msg.tool_calls:
            try:args=json.loads(c.function.arguments);res=FUNCOES[c.function.name](**args);erro=None
            except Recuperavel as x:res=erro=x.d
            except Exception as x:res=erro={"erro":str(x),"proximo_passo":"corrija os argumentos"}
            e.passos.append(Passo(c.function.name,args,res,erro,r.usage.total_tokens));ass=c.function.name+json.dumps(args,sort_keys=True);vezes=vezes+1 if ass==ultima else 1;ultima=ass
            if vezes==limite:e.eventos.append("repetição detectada: observação injetada");msgs.append({"role":"user","content":"Você repetiu a chamada; escolha outro passo ou conclua."})
            if vezes>limite:e.termino,e.motivo=Termino.ERRO_FATAL,"repetição após intervenção";return e
            msgs.append({"role":"tool","tool_call_id":c.id,"name":c.function.name,"content":json.dumps(res,ensure_ascii=False)})
            if c.function.name=="registrar_parecer" and not erro:fase="final";e.ferramentas_ativas=[]

PLANO={"type":"object","properties":{"subtarefas":{"type":"array","items":{"type":"object","properties":{"nome":{"type":"string"},"instrucao":{"type":"string"},"justificativa":{"type":"string"}},"required":["nome","instrucao","justificativa"],"additionalProperties":False}}},"required":["subtarefas"],"additionalProperties":False}
AVAL={"type":"object","properties":{"cita_artigo":{"type":"boolean"},"cita_valores":{"type":"boolean"},"conclui":{"type":"boolean"},"o_que_corrigir":{"type":"string"}},"required":["cita_artigo","cita_valores","conclui","o_que_corrigir"],"additionalProperties":False}
def texto(p,o):return (chamar([{"role":"user","content":p}],o).choices[0].message.content or "").strip()
def parecer_lote(rs,o,max_sub):
    dados=json.dumps(rs,ensure_ascii=False);p=json.loads(chamar([{"role":"user","content":carregar("orquestra-v1",hoje=HOJE,teto=max_sub,lote=dados,historico=json.dumps(HISTORICO))}],o,schema=PLANO).choices[0].message.content)
    if len(p["subtarefas"])>max_sub:raise RuntimeError("plano excedeu teto de subtarefas")
    a=[texto(carregar("trabalhador-v1",hoje=HOJE,instrucao=x["instrucao"],lote=dados,politica=json.dumps(POLITICA),historico=json.dumps(HISTORICO)),o) for x in p["subtarefas"]]
    return texto(carregar("sintese-v1",lote=dados,politica=json.dumps(POLITICA),analises=json.dumps(a,ensure_ascii=False)),o)
def avaliar(candidato,rs,o,max_rodadas):
    dados=json.dumps(rs,ensure_ascii=False)
    for n in range(1,max_rodadas+1):
        a=json.loads(chamar([{"role":"user","content":carregar("avaliador-v2",lote=dados,parecer=candidato)}],o,schema=AVAL).choices[0].message.content)
        if a["cita_artigo"] and a["cita_valores"] and a["conclui"]:return candidato,"APROVADO",n
        if n<max_rodadas:candidato=texto(carregar("otimizador-v1",lote=dados,parecer=candidato,critica=a["o_que_corrigir"],ausentes=""),o)
    return candidato,"TETO_DE_RODADAS",max_rodadas
def args():
    p=argparse.ArgumentParser();p.add_argument("--max-passos",type=int,default=12);p.add_argument("--max-tokens",type=int,default=24000);p.add_argument("--max-reais",type=float,default=.08);p.add_argument("--max-segundos",type=float,default=120);p.add_argument("--preco-entrada",type=float,default=1.);p.add_argument("--preco-saida",type=float,default=3.);p.add_argument("--limite-repeticao",type=int,default=3);p.add_argument("--max-subtarefas",type=int,default=3);p.add_argument("--max-rodadas",type=int,default=3);return p.parse_args()
class Tee:
 def __init__(s,*d):s.d=d
 def write(s,x):[d.write(x) for d in s.d];return len(x)
 def flush(s):[d.flush() for d in s.d]
def main():
 a=args();o=Orcamento(a.max_passos,a.max_tokens,a.max_reais,a.max_segundos,a.preco_entrada,a.preco_saida);original=sys.stdout
 with LOG.open("w",encoding="utf-8") as f:
  sys.stdout=Tee(original,f)
  try:
   print("CARIMBO");[print(f"etapa={k} arquitetura={v[0]} prompt={v[1]} modelo={MODELO} temp=0") for k,v in CONFIG.items()];rs=[];c={x:0 for x in Rota}
   for id,d in DESPESAS.items():
    r,m=rotear(id);c[r]+=1
    if r==Rota.REGRA:
     p=POLITICA[d["categoria"]];x=registrar_parecer(id,"aprovado","dentro do teto",p["artigo"],f"R$ {d['valor']:.2f}");z={**x,"rota":r.value,"termino":"RESPONDEU"};print(id,"regra, 0 chamadas")
    elif r==Rota.HUMANO:z={"id":id,"rota":r.value,"veredito":"HUMANO","artigo":"alçada","valores":f"R$ {d['valor']:.2f}","termino":"HUMANO"};print(id,"humano")
    else:
     e=agente(id,o,a.limite_repeticao) if r==Rota.AGENTE else Estado(id,termino=Termino.HUMANO,motivo="fila")
     reg=[p.resultado for p in e.passos if p.ferramenta=="registrar_parecer" and not p.erro];z={**(reg[-1] if reg else {"id":id,"veredito":"FILA/inconclusivo","artigo":"—","valores":"—"}),"rota":r.value,"termino":e.termino.value,"motivo":e.motivo};print(id,r.value,len(e.passos),"passos",e.tokens_gastos,"tokens",e.termino.value);print(" curva",e.contexto_por_passo,"eventos",e.eventos)
    rs.append(z)
   candidato=parecer_lote(rs,o,a.max_subtarefas);final,saida,n=avaliar(candidato,rs,o,a.max_rodadas);print("PARECER FINAL",final);print("avaliador",saida,"rodadas",n);print("RESUMO",{x.value:c[x] for x in Rota})
  except RuntimeError as x:print("EXECUÇÃO ABORTADA:",x)
  finally:sys.stdout=original
 print("Log gravado em",LOG)
if __name__=="__main__":main()
