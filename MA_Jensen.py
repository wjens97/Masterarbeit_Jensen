from amplpy import AMPL, modules
modules.install()
ampl = AMPL()
import openai
import subprocess
import tempfile
import os
import re
import time
# 1. OpenAI API-Key
openai.api_key = "hier API-Key einfügen"
# 2. Optimierungs-Aufgabe als Freitext
user_problem = """
Aufgabe hier einfügen
"""

# 3. GPT Prompt – KI soll AMPLpy-Kompatiblen Code liefern
gpt_prompt = f"""
Formuliere folgendes Optimierungsproblem als lauffähigen Python-Code mit amplpy:
- Das AMPL-Modell enthält ausschließlich Variablen, Zielfunktion und Nebenbedingungen.
- Mengen und Parameter WERDEN im AMPL-Modell **definiert** (z.B. 'set PRODUCTS;'), aber NICHT mit Daten befüllt!
- ALLE Daten (Mengen/Parameter/Werte) werden AUSSCHLIESSLICH im Python-Teil per ampl.set[...] und ampl.param[...] gesetzt.
- KEINE AMPL-Funktionen wie ord(), prev(), next(), first(), last() verwenden.
- Setze die Lagerbilanz explizit für jede Periode, z.B. durch einzelne Constraints für jede Periode.
- Initialisiere amplpy so: from amplpy import AMPL, modules; modules.install(); ampl = AMPL()
- Die Entscheidungsvariablen im Modell sollen als ganzzahlig (integer) deklariert werden, z.B.: `var x {{A, S}} integer >= 0;`.
- Nach dem Lösen sollen die Variablenwerte und das Ziel im Terminal ausgegeben werden.
- Die Ausgabe aller Variablenwerte erfolgt durch Schleifen über die Indexmengen im Python-Teil, z.B. for i in ampl.getSet('...'): for j in ampl.getSet('...'): print(...).
- Die Entscheidungsvariablen im Modell sollen als ganzzahlig (integer) deklariert werden, z.B.: var x {{A, S}} integer >= 0; .
- Verwende im Python-Teil vor ampl.solve() die Zeile ampl.setOption('solver', 'highs') oder ampl.setOption('solver', 'cbc').
- **Füge im Python-Code vor und nach ampl.solve() eine Zeitmessung mit time ein und gib die Solver-Laufzeit nach dem Lösen im Terminal aus.**
{user_problem}
"""
# 4. GPT-Aufruf
start_gen = time.time() 
client = openai.OpenAI(api_key=openai.api_key)
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": gpt_prompt}],
    temperature=0,
)
end_gen = time.time()
print(f"Laufzeit Modellgenerierung: {end_gen - start_gen:.2f} Sekunden")

content = response.choices[0].message.content
code_match = re.search(r"```python(.*?)```", content, re.DOTALL)
code = code_match.group(1).strip() if code_match else ""

# 5. Problematische AMPL-Konstrukte filtern
def is_ampl_code_problematic(code):
    forbidden = [
        'data;', ':=', 'set ',  # keine Mengen-/Parameterzuweisung im Modell selbst
        'ord(', 'prev(', 'next(', 'first(', 'last(',
        'ampl.eval("set', 'ampl.eval(\'set'
    ]
    # Ausnahme: set ...; ist im Modell ok, set ... := ... nicht!
    return any(x in code for x in forbidden if not x == 'set ' or ':=' in code or 'set ' in code and ':=' in code)

# 6. UTF-8-Encoding-Header
header = "# -*- coding: utf-8 -*-\n"
code = header + code
# 7. Speichern & Ausführen 
with tempfile.NamedTemporaryFile("w", delete=False, suffix=".py", encoding="utf-8") as f:
    f.write(code)
    filename = f.name
print(f"Generierter Code gespeichert unter: {filename}")
print("Starte Ausführung...\n---\n")
subprocess.run(["python", filename])
