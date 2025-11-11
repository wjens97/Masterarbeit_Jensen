# -*- coding: utf-8 -*-
"""
MASTERARBEIT JENSEN - UNIVERSELLES OPTIMIERUNGSSYSTEM
KI-basierte Generierung mathematischer Modelle für praktische Optimierungsaufgaben
Mit CLAUDE 3.5 SONNET
"""

from amplpy import AMPL, modules
import anthropic
import subprocess
import tempfile
import time
import json
import datetime
import re
import os

# AMPL Module installieren
try:
    modules.install()
    print("✅ AMPL Module installiert")
except:
    print("⚠️ AMPL Module bereits vorhanden")

# ===== KONFIGURATION =====
API_KEY = "hier API-Key einfügen"
MAX_VERSUCHE = 3
TEMPERATURE = 1.0  # HIER ÄNDERN für verschiedene Experimente (0.0 - 1.0)

# ===== OPTIMIERUNGSAUFGABE =====
# HIER WIRD DAS PROBLEM DEFINIERT - EINZIGER ANPASSUNGSPUNKT
user_problem = """
Hier Optimierungsaufgabe einfügen
"""

def erstelle_gpt_prompt(problem):
    return f"""Löse diese Optimierungsaufgabe mit AMPL und Python:

{problem}

Erstelle vollständigen Python-Code mit:
- from amplpy import AMPL, modules
- modules.install() und ampl = AMPL()
- AMPL model_str mit Sets, Parameters, Variables, Objective, Constraints
- Daten mit ampl.set[] und ampl.param[] setzen
- ampl.setOption('solver', 'highs')
- ampl.solve() und Ergebnisse ausgeben
- model.mod und data.dat Dateien erstellen

Gib NUR Python-Code zurück!"""


def repariere_code(code):
    """
    Repariert häufige Probleme im generierten Code
    """
    reparaturen = []
    
    # Code aus Markdown-Blöcken extrahieren
    if "```python" in code:
        # Extrahiere Code zwischen ```python und ```
        start = code.find("```python") + len("```python")
        end = code.find("```", start)
        if end != -1:
            code = code[start:end].strip()
            reparaturen.append("Code aus Markdown extrahiert")
    elif "```" in code:
        # Extrahiere Code zwischen ``` und ```
        start = code.find("```") + 3
        end = code.find("```", start)
        if end != -1:
            code = code[start:end].strip()
            reparaturen.append("Code aus Markdown extrahiert")
    
    # UTF-8 Header hinzufügen
    if not code.startswith("# -*- coding: utf-8 -*-"):
        code = "# -*- coding: utf-8 -*-\n" + code
        reparaturen.append("UTF-8 Header")
    
    # Unicode-Pfeile ersetzen
    if "→" in code:
        code = code.replace("→", "->")
        reparaturen.append("Unicode-Pfeile durch ASCII ersetzt")
    
    # Wichtige Imports prüfen
    if "from amplpy import AMPL" not in code:
        if "import AMPL" in code:
            code = code.replace("import AMPL", "from amplpy import AMPL")
        else:
            code = "from amplpy import AMPL, modules\n" + code
        reparaturen.append("AMPL Import korrigiert")
    
    # Falsche AMPL-Initialisierung reparieren
    if "ampl = AMPL(modules=" in code:
        code = code.replace("ampl = AMPL(modules=[", "modules.install()\nampl = AMPL()\n# Removed modules=[")
        reparaturen.append("Falsche AMPL-Initialisierung korrigiert")
    
    # modules.install() prüfen
    if "modules.install()" not in code:
        ampl_line = "ampl = AMPL()"
        if ampl_line in code:
            code = code.replace(ampl_line, f"modules.install()\n{ampl_line}")
            reparaturen.append("modules.install() hinzugefügt")
    
    # Missing modules import reparieren
    if "NameError: name 'modules' is not defined" in code or "modules.install()" in code:
        if "from amplpy import AMPL, modules" not in code:
            code = code.replace("from amplpy import AMPL", "from amplpy import AMPL, modules")
            reparaturen.append("modules Import hinzugefügt")
    
    # Falsche Libraries entfernen
    wrong_libraries = ["pulp", "scipy", "gurobipy", "cvxpy", "ortools", "pyomo"]
    for lib in wrong_libraries:
        if f"import {lib}" in code.lower():
            lines = code.split('\n')
            lines = [line for line in lines if f"import {lib}" not in line.lower()]
            code = '\n'.join(lines)
            reparaturen.append(f"{lib} Import entfernt")
    
    return code, reparaturen

def fuehre_code_aus(code):
    """
    Führt generierten Code sicher aus
    """
    try:
        # Temporäre Datei erstellen
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        
        # Code ausführen
        result = subprocess.run(
            ['python', temp_file], 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='replace',
            timeout=120
        )
        
        # Temporäre Datei löschen
        os.unlink(temp_file)
        
        # Verbesserte Fehler-Erkennung für AMPL-Probleme
        ampl_errors = ['syntax error', 'no value for', 'Error executing', 'infeasible problem', 'unbounded', 'undefined']
        output_text = result.stdout + result.stderr
        
        has_ampl_error = any(error_msg in output_text for error_msg in ampl_errors)
        
        if result.returncode == 0 and not has_ampl_error:
            return {
                'erfolg': True,
                'ausgabe': result.stdout,
                'fehler': None
            }
        else:
            return {
                'erfolg': False,
                'ausgabe': result.stdout,
                'fehler': result.stderr if result.returncode != 0 else f"AMPL-Fehler erkannt: {output_text}"
            }
    
    except subprocess.TimeoutExpired:
        return {
            'erfolg': False,
            'ausgabe': '',
            'fehler': 'Timeout: Code lief länger als 2 Minuten'
        }
    except Exception as e:
        return {
            'erfolg': False,
            'ausgabe': '',
            'fehler': str(e)
        }

def analysiere_fehler_detailliert(fehler, ausgabe="", code=""):
    """
    Detaillierte Fehleranalyse mit Lösungsstrategien und Berichtserstellung
    """
    fehler_lower = fehler.lower()
    ausgabe_lower = ausgabe.lower()
    
    fehler_bericht = {
        'fehler_kategorie': '',
        'fehler_beschreibung': '',
        'ursache_analyse': '',
        'loesungsstrategie': '',
        'praevention': '',
        'technische_details': fehler,
        'code_analyse': ''
    }
    
    if "invalid subscript" in fehler_lower or "not defined" in fehler_lower:
        fehler_bericht.update({
            'fehler_kategorie': 'SET_PARAMETER_INCONSISTENZ',
            'fehler_beschreibung': 'Parameter-Index existiert nicht im definierten Set',
            'ursache_analyse': 'AMPL erwartet alle Parameter-Indizes in entsprechenden Sets definiert',
            'loesungsstrategie': 'Sets vor Parametern definieren, String-Konsistenz prüfen',
            'praevention': 'Template-basierte Set/Parameter-Definition verwenden',
            'code_analyse': 'Prüfe ampl.set[] und ampl.param[] Konsistenz'
        })
        korrektur_anweisung = """
KRITISCHER FEHLER: Parameter-Index existiert nicht im Set!
DETAILLIERTE LÖSUNG:
1. Alle ampl.param[name] Indizes MÜSSEN in entsprechenden Sets definiert sein
2. Beispiel: Wenn ampl.param['price'] = {'H': 50}, dann MUSS 'H' in set PRODUCTS sein
3. Für 2D-Parameter: Beide Tupel-Elemente müssen in entsprechenden Sets existieren
4. REIHENFOLGE: IMMER zuerst Sets definieren, dann Parameter
5. STRING-INDIZES: Verwende IMMER Strings für Set-Elemente: {'R1': wert} nicht {1: wert}
6. DEBUGGING: Drucke alle Sets vor Parameter-Zuweisung aus
"""
    
    elif "already defined" in fehler_lower:
        fehler_bericht.update({
            'fehler_kategorie': 'DOPPELDEFINITION',
            'fehler_beschreibung': 'Doppelte Definition von AMPL-Elementen durch falschen eval() Aufruf',
            'ursache_analyse': 'ampl.eval() wurde für Daten verwendet statt nur für Modell',
            'loesungsstrategie': 'Strikte Trennung: ampl.eval() nur für Modell, ampl.set[]/param[] für Daten',
            'praevention': 'Template-basierte Modell/Daten-Trennung befolgen',
            'code_analyse': 'Suche nach mehrfachen ampl.eval() Aufrufen mit Daten'
        })
        korrektur_anweisung = """
KRITISCHER FEHLER: Doppelte Definition durch ampl.eval() mit Daten!
DETAILLIERTE LÖSUNG:
1. NIEMALS ampl.eval() für Daten verwenden - nur für das Modell!
2. Daten IMMER mit ampl.set[] und ampl.param[] setzen
3. Modell als String definieren, dann nur einmal ampl.eval(model_str)
4. DEBUGGING: Entferne alle Data-Statements aus model_str
"""
    
    elif "syntax error" in fehler_lower or "invalid syntax" in fehler_lower:
        fehler_bericht.update({
            'fehler_kategorie': 'AMPL_SYNTAX',
            'fehler_beschreibung': 'Syntaxfehler in AMPL-Modell oder Python-Code',
            'ursache_analyse': 'Falsche AMPL-Syntax oder Python-Strukturfehler',
            'loesungsstrategie': 'Template-Syntax verwenden, Semikolons/Doppelpunkte prüfen',
            'praevention': 'Vordefinierte AMPL-Templates verwenden',
            'code_analyse': 'Syntax-Validierung vor Ausführung'
        })
        korrektur_anweisung = """
KRITISCHER FEHLER: AMPL-Syntax-Problem!
DETAILLIERTE LÖSUNG:
1. Korrekte AMPL-Syntax: subject to name: constraint;
2. Sets vor Parametern definieren im model_str
3. Parameter-Definition: param name {SET};
4. Variablen-Definition: var name {SET} >= 0;
5. DEBUGGING: Validiere model_str vor ampl.eval()
"""
    
    elif "infeasible" in fehler_lower:
        fehler_bericht.update({
            'fehler_kategorie': 'UNLÖSBAR',
            'fehler_beschreibung': 'Problem ist mathematisch unlösbar - keine feasible Lösung',
            'ursache_analyse': 'Widersprüchliche Constraints oder unausgewogene Angebot/Nachfrage',
            'loesungsstrategie': 'Constraint-Relaxierung, Balance-Prüfung, Slack-Variablen',
            'praevention': 'Vorab-Validierung von Angebot/Nachfrage-Balance',
            'code_analyse': 'Mathematische Modell-Konsistenz prüfen'
        })
        korrektur_anweisung = """
KRITISCHER FEHLER: Problem ist mathematisch unlösbar!
DETAILLIERTE LÖSUNG:
1. Überprüfe Nebenbedingungskonsistenz
2. Kontrolliere Angebot vs. Nachfrage Balance
3. Erwäge Relaxierung von Constraints (>= statt =)
4. Prüfe Kapazitätsgrenzen vs. Anforderungen
5. DEBUGGING: Füge Slack-Variablen für Constraint-Analyse hinzu
"""
    
    elif "unbounded" in fehler_lower:
        fehler_bericht.update({
            'fehler_kategorie': 'UNBESCHRÄNKT',
            'fehler_beschreibung': 'Problem ist unbeschränkt - Zielfunktion kann unendlich werden',
            'ursache_analyse': 'Fehlende Obergrenzen oder falsche Zielfunktionsrichtung',
            'loesungsstrategie': 'Realistische Obergrenzen hinzufügen, Zielfunktion validieren',
            'praevention': 'Immer Kapazitätsgrenzen definieren',
            'code_analyse': 'Constraint-Vollständigkeit prüfen'
        })
        korrektur_anweisung = """
KRITISCHER FEHLER: Problem ist unbeschränkt!
DETAILLIERTE LÖSUNG:
1. Füge angemessene Obergrenzen für Variablen hinzu
2. Überprüfe Zielfunktionsformulierung (minimize/maximize)
3. Prüfe fehlende Kapazitätsbeschränkungen
4. DEBUGGING: Analysiere alle Variablen auf fehlende Obergrenzen
"""
    
    elif "timeout" in fehler_lower:
        fehler_bericht.update({
            'fehler_kategorie': 'PERFORMANCE',
            'fehler_beschreibung': 'Code-Ausführung überschreitet Zeitlimit',
            'ursache_analyse': 'Zu komplexes Problem oder ineffiziente Implementierung',
            'loesungsstrategie': 'Problem-Vereinfachung, Solver-Optimierung',
            'praevention': 'Komplexitäts-Analyse vor Implementierung',
            'code_analyse': 'Performance-Bottlenecks identifizieren'
        })
        korrektur_anweisung = """
PERFORMANCE-PROBLEM: Code läuft zu lange!
DETAILLIERTE LÖSUNG:
1. Vereinfache das Problem (weniger Variablen/Constraints)
2. Reduziere Anzahl Variablen/Constraints
3. Verwende effizientere Solver-Einstellungen
4. DEBUGGING: Messe Ausführungszeit einzelner Komponenten
"""
    
    else:
        fehler_bericht.update({
            'fehler_kategorie': 'ALLGEMEIN',
            'fehler_beschreibung': 'Unspezifischer Fehler - weitere Analyse erforderlich',
            'ursache_analyse': 'Fehlerursache nicht eindeutig klassifizierbar',
            'loesungsstrategie': 'Systematische Debugging-Schritte durchführen',
            'praevention': 'Template-basierte Entwicklung verwenden',
            'code_analyse': 'Vollständige Code-Review erforderlich'
        })
        korrektur_anweisung = """
ALLGEMEINER FEHLER erkannt.
DETAILLIERTE LÖSUNGSANSÄTZE:
1. Prüfe Import-Statements (amplpy, modules)
2. Validiere Set-Parameter-Konsistenz
3. Verwende nur ASCII-Zeichen in Ausgaben
4. Trenne Modell-Definition von Daten-Zuweisung
5. DEBUGGING: Schritt-für-Schritt Code-Validierung
"""
    
    return fehler_bericht, korrektur_anweisung

def analysiere_fehler_typ(fehler, ausgabe=""):
    """
    Wrapper-Funktion für Rückwärtskompatibilität
    """
    fehler_bericht, korrektur_anweisung = analysiere_fehler_detailliert(fehler, ausgabe, "")
    return fehler_bericht['fehler_kategorie'], korrektur_anweisung

def soll_reprompting_erfolgen(fehler, versuch_nr, max_versuche):
    """
    Intelligente Entscheidung ob Reprompting sinnvoll ist
    """
    if versuch_nr >= max_versuche:
        return False, "Maximale Versuche erreicht"
    
    fehler_bericht, _ = analysiere_fehler_detailliert(fehler, "", "")
    kategorie = fehler_bericht['fehler_kategorie']
    
    # Kategorien, die durch Reprompting lösbar sind
    loesbare_kategorien = [
        'SET_PARAMETER_INCONSISTENZ',
        'DOPPELDEFINITION', 
        'AMPL_SYNTAX',
        'ALLGEMEIN'
    ]
    
    if kategorie in loesbare_kategorien:
        return True, f"Reprompting sinnvoll für {kategorie}"
    elif kategorie == 'UNLÖSBAR':
        return True, "Versuche Problem-Relaxierung durch Reprompting"
    elif kategorie == 'UNBESCHRÄNKT':
        return True, "Versuche Constraint-Ergänzung durch Reprompting"
    else:
        return False, f"Reprompting nicht sinnvoll für {kategorie}"

def erstelle_intelligenten_reprompt(fehler, original_problem, alter_code, versuch_nr):
    """
    Erstellt intelligenten, fehler-spezifischen Reprompt mit Chain-of-Thought und Lernfähigkeit
    """
    fehler_bericht, spezifische_anweisung = analysiere_fehler_detailliert(fehler, "", alter_code)
    fehler_typ = fehler_bericht['fehler_kategorie']
    
    base_prompt = f"""
INTELLIGENTES CHAIN-OF-THOUGHT REPROMPTING - VERSUCH {versuch_nr}

FEHLERANALYSE UND LERNSCHRITT:
Der vorherige Code (Versuch {versuch_nr-1}) hatte einen Fehler:
FEHLER-KATEGORIE: {fehler_typ}
FEHLER-BESCHREIBUNG: {fehler_bericht['fehler_beschreibung']}
URSACHEN-ANALYSE: {fehler_bericht['ursache_analyse']}

DETAILIERTE KORREKTUR-STRATEGIE:
{spezifische_anweisung}

ERWEITERTE CHAIN-OF-THOUGHT KORREKTUR-ANALYSE:

1. FEHLERMUSTER-ERKENNUNG:
   - Was genau ist beim vorherigen Versuch schiefgelaufen?
   - Welche Annahmen waren falsch?
   - Welche AMPL-Syntax war fehlerhaft?

2. LÖSUNGSANSATZ-ÜBERARBEITUNG:
   - Wie kann die Modellstruktur verbessert werden?
   - Welche alternativen Implementierungsstrategien gibt es?
   - Welche Validierungsschritte sind notwendig?

3. QUALITÄTSSICHERUNG:
   - Überprüfe alle Set-Parameter-Konsistenzen
   - Validiere AMPL-Syntax vor der Implementierung
   - Stelle sicher, dass alle Daten korrekt zugewiesen werden

ORIGINAL-AUFGABE: {original_problem}

ADAPTIVE LERN-STRATEGIEN basierend auf Versuch {versuch_nr}:
"""
    
    if fehler_typ == "SET_PARAMETER_INCONSISTENZ":
        base_prompt += """
SPEZIELLE SET-PARAMETER-KORREKTUR:
1. Definiere ALLE Sets ZUERST im model_str
2. Verwende EXAKT dieselben String-Namen in Sets und Parametern
3. Für 2D-Parameter: ampl.param['name'] = {('set1_element', 'set2_element'): value}
4. Beispiel-Template:
   ampl.set['PRODUCTS'] = ['A', 'B', 'C']
   ampl.param['price'] = {'A': 10, 'B': 15, 'C': 20}  # Alle Keys müssen in PRODUCTS sein!
"""
    
    elif fehler_typ == "DOPPELDEFINITION":
        base_prompt += """
SPEZIELLE DOPPELDEFINITION-KORREKTUR:
1. NUR model_str mit ampl.eval() verwenden
2. ALLE Daten mit ampl.set[] und ampl.param[] setzen
3. NIEMALS Data-Statements in model_str einbauen
4. Template:
   model_str = "set ITEMS; param cost {ITEMS}; var x {ITEMS};"
   ampl.eval(model_str)  # NUR EINMAL!
   ampl.set['ITEMS'] = ['item1', 'item2']
   ampl.param['cost'] = {'item1': 5, 'item2': 8}
"""
    
    elif fehler_typ == "UNLÖSBAR":
        base_prompt += """
SPEZIELLE UNLÖSBARKEIT-KORREKTUR:
1. Prüfe Balance: Gesamt-Angebot >= Gesamt-Nachfrage
2. Relaxiere kritische Constraints
3. Füge Slack-Variablen hinzu für infeasible Constraints
4. Verwende <= statt = für strenge Gleichungen wo möglich
"""
    
    base_prompt += f"""

WICHTIG: Verwende AUSSCHLIESSLICH AMPL mit amplpy! 
KEINE anderen Libraries wie PuLP, scipy, gurobipy, cvxpy oder ortools!

STRIKTE ANFORDERUNGEN für Versuch {versuch_nr}:
1. NUR amplpy verwenden: from amplpy import AMPL, modules
2. KEINE Unicode-Zeichen in print-Statements (nur ASCII: ->, nicht →)
3. Korrekte AMPL-Syntax für den jeweiligen Optimierungstyp
4. Vollständige Dateninitialisierung im Python-Teil
5. Fehlerfreie Solver-Aufrufe mit ampl.setOption('solver', 'highs')
6. Generierung von .mod und .dat Dateien
7. Encoding-sichere Ausgabe ohne Sonderzeichen

ZWINGEND: STRIKTE DATEN-TRENNUNG:
- Modell: NUR als String definieren, dann ampl.eval(model_str)
- Daten: NUR mit ampl.set[] und ampl.param[] setzen
- NIEMALS ampl.eval() mit Daten verwenden (verursacht "already defined" Fehler)
- Variable-Zugriff: IMMER .getValues().toDict()

AUSGABE-REGELN:
- Verwende nur ASCII-sichere Ausgaben
- Bei solve_result == 'solved': print("Optimale Lösung gefunden")
- Für ALLE Variablen: verwende .getValues().toDict() statt direkten Zugriff
- Beispiel: var_dict = ampl.getVariable('var_name').getValues().toDict()
- Dann: for key, val in var_dict.items(): print(key, val)

**UNIVERSELLES TEMPLATE für alle Optimierungstypen:**
Für alle Variablen-Ausgaben verwende:
- values_dict = ampl.getVariable('var_name').getValues().toDict()
- for key, val in values_dict.items(): print(key, val)
- Das funktioniert für binäre, ganzzahlige und kontinuierliche Variablen

Generiere AUSSCHLIESSLICH AMPL-basierten Python-Code ohne andere Optimierungs-Libraries!
"""
    
    return base_prompt

def erstelle_detaillierten_fehlerbericht(statistiken):
    """
    Erstellt umfassenden Fehlerbericht mit Lösungsstrategien
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bericht_datei = f"fehleranalyse_bericht_{timestamp}.txt"
    
    bericht = []
    bericht.append("=" * 80)
    bericht.append("DETAILLIERTER FEHLERANALYSEBERICHT")
    bericht.append("KI-basiertes Optimierungssystem - Masterarbeit Jensen")
    bericht.append("=" * 80)
    bericht.append(f"Erstellt: {datetime.datetime.now().isoformat()}")
    bericht.append(f"Experiment: {statistiken['timestamp']}")
    bericht.append("")
    
    # Überblick über alle Versuche
    bericht.append("VERSUCHSÜBERSICHT:")
    bericht.append("-" * 50)
    for i, versuch in enumerate(statistiken['versuche'], 1):
        status = "✅ ERFOLG" if versuch['erfolg'] else "❌ FEHLER"
        bericht.append(f"Versuch {i}: {status} (GPT-Zeit: {versuch['gpt_zeit']:.1f}s)")
        if versuch['reparaturen']:
            bericht.append(f"  Reparaturen: {', '.join(versuch['reparaturen'])}")
    bericht.append("")
    
    # Detaillierte Fehleranalyse für jeden fehlgeschlagenen Versuch
    fehlgeschlagene_versuche = [v for v in statistiken['versuche'] if not v['erfolg']]
    
    if fehlgeschlagene_versuche:
        bericht.append("DETAILLIERTE FEHLERANALYSE:")
        bericht.append("=" * 50)
        
        for versuch in fehlgeschlagene_versuche:
            if versuch['fehler_analyse']:
                fa = versuch['fehler_analyse']
                bericht.append(f"\nVERSUCH {versuch['versuch_nr']} - FEHLERANALYSE:")
                bericht.append("-" * 30)
                bericht.append(f"Kategorie: {fa['fehler_kategorie']}")
                bericht.append(f"Beschreibung: {fa['fehler_beschreibung']}")
                bericht.append(f"Ursache: {fa['ursache_analyse']}")
                bericht.append(f"Lösungsstrategie: {fa['loesungsstrategie']}")
                bericht.append(f"Prävention: {fa['praevention']}")
                bericht.append(f"Code-Analyse: {fa['code_analyse']}")
                bericht.append("")
                bericht.append("TECHNISCHE DETAILS:")
                for line in fa['technische_details'].split('\n')[:5]:  # Erste 5 Zeilen
                    bericht.append(f"  {line}")
                if len(fa['technische_details'].split('\n')) > 5:
                    bericht.append("  [...weitere Details in JSON-Bericht...]")
                bericht.append("")
    
    # Lerneffekte und Empfehlungen
    bericht.append("LERNEFFEKTE UND EMPFEHLUNGEN:")
    bericht.append("=" * 40)
    
    fehler_kategorien = {}
    for versuch in fehlgeschlagene_versuche:
        if versuch['fehler_analyse']:
            kategorie = versuch['fehler_analyse']['fehler_kategorie']
            fehler_kategorien[kategorie] = fehler_kategorien.get(kategorie, 0) + 1
    
    if fehler_kategorien:
        bericht.append("Häufigste Fehlertypen:")
        for kategorie, anzahl in sorted(fehler_kategorien.items(), key=lambda x: x[1], reverse=True):
            bericht.append(f"  - {kategorie}: {anzahl}x aufgetreten")
        bericht.append("")
        
        bericht.append("EMPFEHLUNGEN FÜR ZUKÜNFTIGE ENTWICKLUNG:")
        if "SET_PARAMETER_INCONSISTENZ" in fehler_kategorien:
            bericht.append("  ⚠️  Implementiere automatische Set-Parameter-Validierung")
        if "DOPPELDEFINITION" in fehler_kategorien:
            bericht.append("  ⚠️  Verwende strikte Modell/Daten-Trennung-Templates")
        if "AMPL_SYNTAX" in fehler_kategorien:
            bericht.append("  ⚠️  Integriere AMPL-Syntax-Prüfung vor Ausführung")
        if "UNLÖSBAR" in fehler_kategorien:
            bericht.append("  ⚠️  Implementiere Feasibility-Checks vor Optimierung")
    else:
        bericht.append("✅ Keine Fehler aufgetreten - System funktioniert optimal!")
    
    bericht.append("")
    bericht.append("SYSTEMLEISTUNG:")
    bericht.append(f"  Erfolgsrate: {(len([v for v in statistiken['versuche'] if v['erfolg']]) / len(statistiken['versuche']) * 100):.1f}%")
    bericht.append(f"  Durchschnittliche GPT-Zeit: {sum(v['gpt_zeit'] for v in statistiken['versuche']) / len(statistiken['versuche']):.1f}s")
    bericht.append(f"  Reprompting-Aktivierungen: {statistiken['statistiken'].get('reprompts', 0)}")
    
    # Datei speichern
    with open(bericht_datei, 'w', encoding='utf-8') as f:
        f.write('\n'.join(bericht))
    
    print(f"📊 Detaillierter Fehlerbericht: {bericht_datei}")
    return bericht_datei

def speichere_finale_dateien(erfolgreicher_code=""):
    """
    Speichert finale Lösung und Nachweis-Dateien
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_str = f"T{str(TEMPERATURE).replace('.', '')}"
    api_name = "CLAUDE"  # API-Bezeichner für Claude
    
    # Finale Python-Lösung speichern
    finale_datei = f"finale_loesung_{api_name}_{temp_str}_{timestamp}.py"
    with open(finale_datei, 'w', encoding='utf-8', errors='replace') as f:
        f.write("# Finale Lösung - Universelles Optimierungssystem\n")
        f.write("# Erstellt durch KI-basierte Modellgenerierung\n")
        f.write(f"# Temperature: {TEMPERATURE}\n\n")
        if erfolgreicher_code:
            f.write(erfolgreicher_code)
        else:
            f.write("# Kein erfolgreicher Code verfügbar\n")
    
    print(f"📁 Finale Lösung: {finale_datei}")
    
    return timestamp

def gpt_anfrage(prompt, temperature=None):
    """
    Sendet Anfrage an Claude Sonnet und gibt Antwort zurück
    """
    if temperature is None:
        temperature = TEMPERATURE
    
    client = anthropic.Anthropic(api_key=API_KEY)
    
    try:
        start_time = time.time()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        end_time = time.time()
        
        return {
            'erfolg': True,
            'antwort': response.content[0].text,
            'zeit': end_time - start_time
        }
    except Exception as e:
        return {
            'erfolg': False,
            'antwort': None,
            'fehler': str(e),
            'zeit': 0
        }

def main():
    """
    Hauptfunktion - Universelles Optimierungssystem
    """
    print("✅ AMPL Module installiert")
    print("=" * 70)
    print(" MASTERARBEIT - UNIVERSELLES OPTIMIERUNGSSYSTEM")
    print("=" * 70)
    
    # Problem anzeigen
    print(f"Aufgabe:\n{user_problem[:100]}...")
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
    print(f"Timestamp: {timestamp}")
    print("=" * 70)
    
    statistiken = {
        'timestamp': timestamp,
        'problem': user_problem,
        'temperature': TEMPERATURE,  # Temperature-Parameter für Nachvollziehbarkeit
        'model': 'claude-sonnet-4-20250514',
        'erfolg': False,
        'versuche': [],
        'statistiken': {}
    }
    
    gesamt_gpt_zeit = 0
    reprompts = 0
    letzter_fehler = ""
    letzter_code = ""
    erfolgreicher_code = ""  # Speichert den erfolgreichen Code
    
    for versuch_nr in range(1, MAX_VERSUCHE + 1):
        print(f"\n--- VERSUCH {versuch_nr} ---")
        
        # Intelligente Reprompting-Entscheidung
        if versuch_nr > 1:
            soll_reprompt, grund = soll_reprompting_erfolgen(letzter_fehler, versuch_nr, MAX_VERSUCHE)
            if not soll_reprompt:
                print(f"🚫 KI-Entscheidung: {grund}")
                print(f"⏹️  Stoppe weitere Versuche - Reprompting nicht erfolgversprechend")
                break

        # GPT-Prompt erstellen
        if versuch_nr == 1:
            prompt = erstelle_gpt_prompt(user_problem)
            print(f"🤖 Erstelle Standard-Prompt für ersten Versuch")
        else:
            prompt = erstelle_intelligenten_reprompt(letzter_fehler, user_problem, letzter_code, versuch_nr)
            reprompts += 1
            print(f"🧠 KI erstellt intelligenten Reprompt basierend auf Fehleranalyse von Versuch {versuch_nr-1}")
            print(f"🔄 Automatisches Reprompting aktiviert - Versuch {versuch_nr}")
        
        # GPT anfragen
        print("🤖 Frage GPT...")
        gpt_result = gpt_anfrage(prompt)
        
        if not gpt_result['erfolg']:
            print(f"❌ GPT-Fehler: {gpt_result['fehler']}")
            continue
        
        gpt_zeit = gpt_result['zeit']
        gesamt_gpt_zeit += gpt_zeit
        print(f"⏱️ GPT-Zeit: {gpt_zeit:.1f}s")
        
        # Code reparieren
        code = gpt_result['antwort']
        code, reparaturen = repariere_code(code)
        
        if reparaturen:
            print(f"🔧 Reparaturen: {', '.join(reparaturen)}")
        
        # Code ausführen
        temp_file = f"temp_versuch_{versuch_nr}.py"
        print(f"🔄 Führe Code aus: {temp_file}")
        
        exec_result = fuehre_code_aus(code)
        
        # Detaillierte Fehleranalyse für Dokumentation
        fehler_analyse = None
        if not exec_result['erfolg'] and exec_result['fehler']:
            fehler_bericht, _ = analysiere_fehler_detailliert(
                exec_result['fehler'], 
                exec_result['ausgabe'], 
                code
            )
            fehler_analyse = fehler_bericht

        # Versuch dokumentieren
        versuch_info = {
            'versuch_nr': versuch_nr,
            'gpt_zeit': gpt_zeit,
            'code': code,
            'reparaturen': reparaturen,
            'erfolg': exec_result['erfolg'],
            'ausgabe': exec_result['ausgabe'],
            'fehler': exec_result['fehler'],
            'fehler_analyse': fehler_analyse
        }
        statistiken['versuche'].append(versuch_info)
        
        if exec_result['erfolg']:
            print("✅ ERFOLGREICH!")
            print(f"\n📊 ERGEBNIS:")
            print(exec_result['ausgabe'])
            
            statistiken['erfolg'] = True
            erfolgreicher_code = code  # Speichere den erfolgreichen Code
            break
        else:
            print("❌ FEHLER:")
            print(f"Fehler: {exec_result['fehler']}")
            if exec_result['ausgabe']:
                print(f"Ausgabe: {exec_result['ausgabe']}")
            
            # Intelligente Fehleranalyse mit detailliertem Bericht
            fehler_bericht, korrektur_anweisung = analysiere_fehler_detailliert(
                exec_result['fehler'], 
                exec_result['ausgabe'], 
                code
            )
            print(f"🔍 Fehlertyp identifiziert: {fehler_bericht['fehler_kategorie']}")
            print(f"📋 Ursache: {fehler_bericht['ursache_analyse']}")
            print(f"🔧 Lösungsstrategie: {fehler_bericht['loesungsstrategie']}")
            
            # Detaillierte Fehleranalyse in versuch_info ist bereits gespeichert
            
            letzter_fehler = exec_result['fehler']
            letzter_code = code
            
            # Intelligente Reprompting-Entscheidung
            if versuch_nr < MAX_VERSUCHE:
                soll_reprompt, grund = soll_reprompting_erfolgen(exec_result['fehler'], versuch_nr, MAX_VERSUCHE)
                if soll_reprompt:
                    print(f"🧠 Intelligente Analyse: {grund}")
                    print(f"🔄 KI bereitet automatischen Reprompt für Versuch {versuch_nr + 1} vor...")
                else:
                    print(f"⚠️  Analyse: {grund}")
                    print(f"⏭️  Überspringe verbleibende Versuche - Reprompting nicht sinnvoll")
    
    # Finale Statistiken
    print("\n" + "=" * 70)
    print("📈 FINALE STATISTIKEN")
    print("=" * 70)
    print(f"Gesamte Versuche: {len(statistiken['versuche'])}")
    print(f"Reprompts: {reprompts}")
    print(f"Gesamte GPT-Zeit: {gesamt_gpt_zeit:.1f}s")
    
    if statistiken['erfolg']:
        print("Status: ✅ PROBLEM GELÖST")
        
        # Dateien speichern
        print(f"\n📁 Speichere Nachweis-Dateien...")
        timestamp_save = speichere_finale_dateien(erfolgreicher_code)
        
        # Temperature-String für Dateinamen (z.B. "T06" für 0.6)
        temp_str = f"T{str(TEMPERATURE).replace('.', '')}"
        api_name = "CLAUDE"  # API-Bezeichner für Claude
        
        # Modell und Daten-Dateien suchen und umbenennen
        if os.path.exists('model.mod'):
            new_model = f"model_{api_name}_{temp_str}_{timestamp_save.replace(':', '').replace('-', '').replace('.', '')[:14]}.mod"
            os.rename('model.mod', new_model)
            print(f"📁 Datei gespeichert: {new_model}")
        
        if os.path.exists('data.dat'):
            new_data = f"data_{api_name}_{temp_str}_{timestamp_save.replace(':', '').replace('-', '').replace('.', '')[:14]}.dat"
            os.rename('data.dat', new_data)
            print(f"📁 Datei gespeichert: {new_data}")
        
        print(f"\n🎓 NACHWEIS FÜR PROFESSOR:")
        print(f"- Python-Code: finale_loesung_{api_name}_{temp_str}_{timestamp_save.replace(':', '').replace('-', '').replace('.', '')[:14]}.py")
        if os.path.exists(f"model_{api_name}_{temp_str}_{timestamp_save.replace(':', '').replace('-', '').replace('.', '')[:14]}.mod"):
            print(f"- model_{api_name}_{temp_str}_{timestamp_save.replace(':', '').replace('-', '').replace('.', '')[:14]}.mod")
        if os.path.exists(f"data_{api_name}_{temp_str}_{timestamp_save.replace(':', '').replace('-', '').replace('.', '')[:14]}.dat"):
            print(f"- data_{api_name}_{temp_str}_{timestamp_save.replace(':', '').replace('-', '').replace('.', '')[:14]}.dat")
    else:
        print("Status: ❌ PROBLEM NICHT GELÖST")
        if statistiken['versuche']:
            letzter_versuch = statistiken['versuche'][-1]
            print(f"Letzter Fehler: {letzter_versuch['fehler']}")
    
    # Erweiterte Statistiken mit Fehleranalyse
    fehler_typen = {}
    for versuch in statistiken['versuche']:
        if not versuch['erfolg'] and versuch['fehler']:
            fehler_typ, _ = analysiere_fehler_typ(versuch['fehler'])
            fehler_typen[fehler_typ] = fehler_typen.get(fehler_typ, 0) + 1
    
    statistiken['statistiken'] = {
        'anzahl_versuche': len(statistiken['versuche']),
        'reprompts': reprompts,
        'gesamt_gpt_zeit': gesamt_gpt_zeit,
        'fehler_typen': fehler_typen,
        'lerneffekt': 'Intelligentes Reprompting aktiviert' if reprompts > 0 else 'Erfolg beim ersten Versuch'
    }
    
    api_name = "CLAUDE"  # API-Bezeichner für Claude
    bericht_datei = f"bericht_{api_name}_T{str(TEMPERATURE).replace('.', '')}_{timestamp.replace(':', '').replace('-', '').replace('.', '')[:14]}.json"
    with open(bericht_datei, 'w', encoding='utf-8') as f:
        json.dump(statistiken, f, indent=2, ensure_ascii=False)
    
    print(f"📊 Detaillierter Bericht: {bericht_datei}")
    
    # Umfassende Fehlerberichterstattung
    if len([v for v in statistiken['versuche'] if not v['erfolg']]) > 0:
        print(f"\n📋 ERSTELLE DETAILLIERTEN FEHLERBERICHT...")
        fehlerbericht_datei = erstelle_detaillierten_fehlerbericht(statistiken)
        print(f"🔍 Umfassende Fehleranalyse: {fehlerbericht_datei}")
    
    # Intelligente Lernanalyse anzeigen
    if fehler_typen:
        print(f"\n🧠 INTELLIGENTE FEHLERANALYSE:")
        for fehler_typ, anzahl in fehler_typen.items():
            print(f"   - {fehler_typ}: {anzahl}x aufgetreten")
        print(f"   - Reprompting-System: {'AKTIVIERT' if reprompts > 0 else 'NICHT BENÖTIGT'}")
        print(f"   - Lerneffekt: Fehler-spezifische Korrekturen implementiert")
    
    print("=" * 70)

if __name__ == "__main__":
    main()