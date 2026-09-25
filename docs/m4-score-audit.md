# Auditoria do Risk Score (M4) — 25/09/2026

Medido sobre as 158 propostas da base. Decisão no fim.

## O que cada componente separa de fato

| componente | peso | nota cheia | o que mede |
|---|---|---|---|
| Conflict of Interest | 20 | **100%** | nada — nenhuma checagem roda |
| Scope Clarity | 20 | **97%** | se título, abstract, motivation e rationale existem e passam de 50–100 caracteres |
| Documentation Quality | 10 | **87%** | contagem de palavras acima de 500 |
| Treasury Value | 15 | 65% | % do Net Change Limit — discrimina |
| Proposer Track Record | 25 | 22% | taxa de entrega de propostas **semanticamente similares** |
| Historical Precedent | 10 | 22% | **a mesma taxa, de novo** |

## Conclusão

**50 dos 100 pontos são quase constantes.** Conflito dá 20 a todos, Scope Clarity
a 97% e Documentação a 87%. Não distinguem proposta boa de ruim; engordam o número.

A variação real vem de **dois sinais**: a taxa de entrega de similares — contada
duas vezes, somando 35 pontos — e o tamanho do saque (15 pontos).

Distribuição: scores de **50 a 100**, média 82,7, desvio 11,6. Metade da escala
nunca é usada e nenhuma proposta jamais atingiu HIGH RISK (< 45). Um "76/100"
aparenta julgamento fino; na prática diz "não é das maiores e tem histórico
mediano".

**O nome mais forte é o que menos se cumpre:** "Proposer Track Record" não olha
o proponente. Olha propostas de assunto parecido, de qualquer autor.

## Caminhos

1. **Manter e documentar.** A página já exibe a evidência de cada componente.
   Custo zero, honestidade média.
2. **Cortar para o que mede algo.** Três sinais reais — histórico de entrega
   (uma vez, não duas), tamanho do saque, clareza — com pesos redistribuídos, e
   o componente renomeado para descrever o cálculo. O score passa a variar de
   verdade.
3. **Abandonar a nota única.** Mostrar os sinais lado a lado, sem somar. Mais
   honesto e mais radical: um número redondo dá conforto que os dados não
   sustentam.

Recomendação: **2**. A 3 é intelectualmente melhor, mas um registro público sem
nota perde a função de alertar rápido.

## Decisão — caminho 2, com dois sinais (método 1.2.0)

O caminho 2 listava "clareza" entre os sinais reais, mas Scope Clarity é um dos
que dão nota cheia a 97% — então sobram **dois**:

| componente | pontos |
|---|---|
| Delivery of Similar Proposals | 60 — ou 100 quando o saque não se aplica |
| Treasury Withdrawal Size | 40 — só em saque de tesouro |

Sinal que não se aplica sai da conta em vez de dar pontos de graça, e sem
amostra o sinal fica no meio da escala: uma proposta sobre a qual não há nada a
dizer cai em MEDIUM. Simulado sobre os sinais gravados das 158 propostas:

| | faixa | média | desvio | LOW / MEDIUM / HIGH |
|---|---|---|---|---|
| 1.1.0 | 50–100 | 82,7 | 11,6 | 135 / 23 / 0 |
| 1.2.0 | 0–100 | 61,4 | 22,0 | 54 / 75 / 29 |

(As 154 ancoradas não mudam; a tabela mostra só como o método novo as veria.)

## Restrição que vale para qualquer caminho

As 154 análises ancoradas **não são recalculadas** — o documento no bloco é o
registro. Método novo vale para análise nova, com `PIL_VERSION` subindo e a
página declarando qual versão produziu cada número (ver "Armadilhas conhecidas"
no CLAUDE.md).
