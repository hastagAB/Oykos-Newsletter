# Linee guida editoriali - L'Essenziale in Pediatria

**Versione 2.0 | 7 agosto 2026**

This is the canonical editorial specification. Version 1.0 is superseded and has
been removed; where any other document in this repository disagrees with this
one, this one wins.

Enforcement lives in `llm/synthesis.py` (writing), `llm/editorial_qa.py`
(auditing), `newsletter/template.py` (labels) and `newsletter/subject.py`
(subject and preheader).

---

## 1. Scopo

La newsletter seleziona le novità che meritano l'attenzione del Pediatra di
Libera Scelta e ne chiarisce la rilevanza per la pratica.

**Non ogni novità richiede un cambiamento.** Per ogni contenuto il lettore deve
capire se:

1. cambia concretamente qualcosa nella pratica;
2. aggiunge un elemento utile al ragionamento clinico;
3. suggerisce particolare attenzione in alcune situazioni;
4. non modifica al momento la pratica;
5. non consente ancora conclusioni sufficientemente solide.

Oykos non sostituisce il giudizio clinico e non trasforma automaticamente una
nuova evidenza in una raccomandazione.

> Implemented as `ImplicationKind`: `changes_practice`, `worth_attention`,
> `may_consider`, `no_change`, `insufficient`.

## 2. Tono di voce

Competente, collegiale, contestuale, sintetico, **proporzionato**, trasparente,
sobrio. Non imita un medico e non assume un'autorità superiore a quella
consentita dalla fonte.

## 3. Principio fondamentale

La sequenza NON è "nuova evidenza, quindi il pediatra deve fare qualcosa".

È: **cosa emerge, quanto è rilevante per il PLS, che cosa cambia se cambia
qualcosa.**

L'assenza di un'azione immediata è una conclusione editoriale perfettamente
valida.

> `compose_newsletter` requires only a headline. Requiring an action would
> delete exactly these conclusions, which it did until 2026-08-08.

## 5. Struttura di ogni contenuto

Titolo, cosa emerge, perché può contare per il PLS, implicazione pratica **solo
quando esiste**, fonte e limiti.

La sezione non deve necessariamente chiamarsi "Cosa fare ora".

> Labels come from `IMPLICATION_LABELS` and `NO_CHANGE_NOTES`.

## 6. Regole di scrittura

- Un solo concetto principale per contenuto.
- Non creare obbligatoriamente una raccomandazione.
- Evitare imperativi clinici non sostenuti dalla fonte. `ricontrolla`, `invia`,
  `modifica`, `mantieni`, `monitora`, `prescrivi` richiedono particolare cautela.
- Con studi osservazionali preferire formulazioni che mantengano l'incertezza.
- **Vietata** la formula automatica "In pratica, questo significa".
- Separare ciò che mostra la fonte, ciò che può essere rilevante e ciò che ne
  consegue.
- Non usare un tono più sicuro della fonte.

## 7. Gerarchia delle evidenze e del linguaggio

| Fonte | Linguaggio consentito |
|-------|----------------------|
| Linea guida o indicazione istituzionale | Formulazione operativa diretta, **attribuita alla fonte** |
| Revisione sistematica o evidenza consolidata | Implicazioni cliniche, con limiti e popolazione |
| Studio osservazionale | Associazioni e possibile rilevanza. Mai indicazioni cliniche |
| Studio preliminare o singolo lavoro | Informazione da conoscere o seguire |
| Documento incompleto o non accessibile | Nessuna raccomandazione |

> Enforced in code: `DIRECTIVE_DOCUMENT_TYPES` and `INSTITUTIONAL_RELIABILITY`
> decide who may direct the reader. A study is capped at `may_consider`.

## 8. Gerarchia editoriale

Priorità della settimana, clinica del territorio, normativa e organizzazione,
segnalazione. **Nessun contenuto deve essere allungato per riempire una
struttura grafica.**

> No section minimums, no geography quota. Two strong items beat three average
> ones.

## 9. Titoli

Informativi prima che accattivanti. Mai un titolo che incorpora una
raccomandazione non contenuta nella fonte.

Da evitare: *"Ex very preterm: spirometria da considerare se sintomatici."*
Preferire: *"Ex very preterm: frequenti alterazioni spirometriche in età
prescolare."*

### 9.1 Oggetto e anteprima

Oggetto e anteprima coprono l'intero numero, quindi non possono generalizzare la
conclusione di un singolo item. Se una comunicazione istituzionale modifica la
pratica mentre gli altri item sono osservazionali, il cambiamento va **attribuito
alla fonte** (*"Nuove indicazioni AIFA su..."*) e non usato come cornice del
fascicolo: *"Cosa cambia questa settimana"* travisa gli item che non cambiano
nulla.

Enforced in `newsletter/subject.py`, which tells the writer which sources change
practice and how many items do not, and audited as check 8 in `llm/editorial_qa.py`.

## 10. Formule editoriali

Da evitare come schema automatico: *Cosa cambia. Perché conta. Cosa fare
adesso.*

Formula raccomandata: *Cosa emerge. Quanto conta per il PLS. Che cosa cambia, se
cambia qualcosa.*

**Conclusioni ammesse** (whitelist enforced in `_SANCTIONED_OPENING`):

- "Questo aggiornamento modifica..."
- "Il dato rafforza l'attenzione verso..."
- "Può essere utile tenerne conto quando..."
- "È un elemento da considerare soprattutto in..."
- "Il dato è interessante, ma non modifica da solo la pratica."
- "Al momento non emergono indicazioni operative."
- "L'evidenza non è sufficiente per modificare la gestione."

A blacklist of imperatives was tried first and failed: the model moved to
impersonal steering such as *"Da tenere presente nel follow-up"*, which has no
verb aimed at anyone. The whitelist is the enforceable form.

## 11. Affidabilità delle fonti

L'interesse editoriale non deve mai superare la qualità dell'evidenza. Non
attribuire alla fonte raccomandazioni che non contiene. Non trasformare
associazioni in causalità. Non trasformare una prudenza editoriale di Oykos in
una raccomandazione clinica.

## 12. Checklist prima dell'invio

Run automatically on every compose by `oykos.llm.editorial_qa`, and on demand
with `oykos qa [WEEK]`. It reports; it does not gate, because the last item on
the checklist is a human one.

The auditor is an LLM and its verdict varies between runs. Treat it as a
demanding first reader, not as a certificate.

---

## DECISIONE EDITORIALE

Una voce da **curatore affidabile dell'informazione clinica**, non da medico che
impartisce indicazioni.

## PRINCIPIO FINALE

Una buona newsletter clinica non trasforma ogni novità in un'azione. Distingue
ciò che cambia la pratica da ciò che semplicemente merita di essere conosciuto.
