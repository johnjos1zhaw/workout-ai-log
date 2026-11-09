# GymCoach AI – Projektdokumentation

Stand: 8. November 2026. Die Begriffe **geplant**, **implementiert**, **getestet** und **wissenschaftlich validiert** bezeichnen unterschiedliche Reifegrade. Es liegen noch keine wissenschaftlich validierten Prognosen vor.

## 1. Executive Summary

**Implementiert:** Der bestehende Notizparser, die Streamlit-Importansicht und deskriptive Kennzahlen sind erhalten. Die neue Service-Schicht für Übungen, Vorlagen, Einheiten und Sätze sowie Ansichten für deren Verwaltung, Historie, Fortschritt und KI-Erklärung sind eingebunden.

**Implementiert:** Eine vorläufige historische Gruppierung nach Datum und Workout-Text, eine zeitlich evaluierte Baseline für die nächste e1RM-Beobachtung, explizite Trendregeln und eine begrenzte LLM-Erklärung mit deterministischem Ersatz.

**Getestet:** Zwölf automatisierte Tests bestehen. Die Migration wurde zuerst auf einer Kopie geprüft. Vor der anschließenden Migration der Arbeitsdatenbank wurde eine byteweise verifizierte Sicherung unter `data/workout_log.pre_gymcoach_backup.duckdb` angelegt (SHA-256: `2faf0540c6799c8f566a8e273d7d3612768dbadda54b3e81e78c2c4237a68a79`). Alle 1.776 Originalzeilen blieben in `workout_sets`; 1.776 Zeilen wurden zugeordnet und 96 vorläufige Einheiten gebildet.

## 2. Problem Framing

Die Anwendung soll Trainingsdaten zuverlässig erfassen und individuelle Leistungstrends verständlich erklären. Eine Prognose bezeichnet eine erwartete zukünftige Messung, nicht ein medizinisch oder sportwissenschaftlich optimales Trainingsgewicht. Die Empfehlung muss durch den Nutzer überprüfbar und ablehnbar bleiben.

Die Architektur trennt Datenzugriff und fachliche Regeln in `src/training.py`, Prognose und Entscheidung in `src/progression.py`, Erklärung in `src/explanations.py` sowie die Streamlit-Ansichten. Physische Fremdschlüssel wurden nach einem fehlgeschlagenen Test im neuen Schema verworfen: DuckDB blockierte das Ändern einer referenzierten Vorlage. Beziehungen werden über stabile IDs und transaktionale Service-Funktionen geprüft. Das erhöht die Bedeutung von Service-Tests und Integritätsprüfungen. Diese Entscheidung muss bei einem späteren Wechsel des Datenbanksystems neu bewertet werden.

## 3. Data & Features

Die bestehende Tabelle `workout_sets` enthält 1.776 historische Zeilen. Sie besitzt keine stabilen Satz- oder Einheiten-IDs. 90 Trainingstage und 96 Kombinationen aus Datum und Workout-Bezeichnung sind beobachtbar. Drei Gruppen haben exakt identische Zeilen; 19 Kombinationen aus Datum, Workout, standardisierter Übung und Satznummer sind mehrfach belegt. Keine dieser Zeilen darf automatisch entfernt werden.

**Aktuell beobachtbar:** Datum, Workout-Bezeichnung, Übung, Satznummer, Wiederholungen und teilweise externes Gewicht oder Übungsdauer. **Für historische Daten nicht beobachtbar:** tatsächlicher Einheitenbeginn und -abschluss, Trainingsdauer, Körpergewicht, Satzpausen und RPE. Diese Werte bleiben bei einer Migration leer.

**Implementiert im neuen Schema:** Optionale Körpergewichts-, Satzpausen- und RPE-Felder sowie IDs für neue Daten. Neue Zeitstempel werden als UTC in `TIMESTAMP` gespeichert. Legacy-Einheiten haben bewusst keine erfundene Start- oder Endzeit. Die ursprünglichen Zeilen werden zusätzlich als JSON in `legacy_row_map` referenziert.

## 4. Validation Plan

Die Zuordnung nach Datum und Workout-Text wurde vom Nutzer ausdrücklich freigegeben und bleibt als **vorläufig** gekennzeichnet. Ohne Uhrzeit kann eine zweite Einheit mit gleichem Namen am selben Tag nicht ausgeschlossen werden. Die Tests vergleichen Originalwerte und Herkunftsabbildung als Multimengen und prüfen einen zweiten, wirkungslosen Migrationslauf. Weitere manuelle Stichproben und mobile Bedienung sind noch offen.

Das Prognoseziel ist der höchste gültige Epley-e1RM-Wert der **nächsten** Einheit derselben Kraftübung. Es ist ein Leistungsindex, keine sichere Vorhersage des trainierbaren Gewichts. Pro Einheit wird aus bereits erfassten positiven Gewichten und Wiederholungen ein Wert gebildet. Für jede historische Ein-Schritt-Prognose verwendet die Baseline ausschließlich den letzten davor bekannten Wert. Die letzten 20 % der Einheiten dienen als zeitlicher Testabschnitt; ein davor liegender Abschnitt ist als Validierungsbereich reserviert.

## 5. Metrics & Baselines

### Phase 2A: Technologieentscheidung

Die größte beobachtete Reihe gültiger Kraftübungen umfasst 43 Einheiten (Hacksquat), die zweitgrößte 38 (Leg Extension). Häufig gibt es weniger als 20. Die Einheiten liegen unregelmäßig über mehrere Jahre. Eine vorab festgelegte, konservative Projektschwelle von 60 vergleichbaren Einheiten je Übung wurde für einen Modellversuch gewählt; sie ist eine methodische Vorsichtsregel, keine universelle statistische Mindestzahl.

| Ansatz | Eignung hier | Aufwand/Interpretierbarkeit | Entscheidung |
|---|---|---|---|
| Einfaches scikit-learn-Modell | Mit höchstens 43 Einheiten je Übung nur schwach zeitlich evaluierbar | Geringer Aufwand; lineares Modell gut interpretierbar | Vorläufig zurückgestellt |
| AutoML (FLAML, AutoGluon) | Erfordert noch sorgfältigere zeitliche Validierung; unregelmäßige kleine Reihen und wenige Testpunkte | Mehr Abhängigkeiten und Suchraum; schwerer reproduzierbar | Zurückgestellt |
| Vortrainiertes Modell (TabPFN-TS) | Technisch prüfbare Zero-Shot-Option, aber keine bekannte Evidenz für diese persönlichen Trainingsreihen | Zusätzliche Modellabhängigkeit, Lizenz- und Betriebsklärung | Zurückgestellt |
| Regelbasierte Analyse + Fortschreibungs-Baseline + LLM-Erklärung | Direkte, überprüfbare Aussage trotz begrenzter Daten | Geringer Aufwand, vollständig nachvollziehbar | **Gewählt** |

Die Produktdokumentationen zeigen, dass [FLAML Zeitreihenprognosen und zeitliche Splits unterstützt](https://microsoft.github.io/FLAML/docs/Use-Cases/Task-Oriented-AutoML/), [AutoGluon probabilistische Zeitreihenmodelle anbietet](https://auto.gluon.ai/stable/api/autogluon.timeseries.TimeSeriesPredictor.html) und [TabPFN-TS eine Zero-Shot-Implementierung besitzt](https://github.com/PriorLabs/tabpfn-time-series). Die Ablehnung für **diesen** Datensatz ist eine Schlussfolgerung aus den gemessenen Reihenlängen, kein allgemeines Urteil über diese Verfahren.

**Implementiert:** Die Fortschreibungs-Baseline sagt den letzten beobachteten e1RM-Wert erneut voraus. Der Test-MAE ist der Mittelwert absoluter Fehler im letzten chronologischen Fünftel. Bei Hacksquat: 43 Einheiten, 9 Testeinheiten, **1,48 kg MAE**. Bei Leg Extension: 38 Einheiten, 8 Testeinheiten, **5,67 kg MAE**. Dies sind tatsächlich ausgeführte Berechnungen aus `python -B -m db.evaluate_progression`, keine modellierten Unsicherheitsintervalle und keine wissenschaftliche Validierung. Nullfehler bei einzelnen weiteren Reihen bedeuten möglicherweise nur konstante protokollierte Werte.

**Entscheidungsregel:** Bei weniger als sechs Einheiten „beibehalten“ mit Datenhinweis. Sonst werden die Mediane der letzten drei und der davorliegenden drei e1RM-Werte verglichen: mehr als +3 % → „erhöhen“, weniger als −5 % → „reduzieren/überprüfen“, dazwischen „beibehalten“. Dies ist ein zu prüfendes Signal, keine Anweisung zu einem konkreten Trainingsgewicht. Die Schwellen sind fachliche Startannahmen und nicht wissenschaftlich kalibriert.

**Nicht implementiert:** Ein trainiertes Modell und dessen Vergleich mit der Baseline. Dies ist eine dokumentierte datenbedingte Einschränkung; eine Modellgüte wird nicht behauptet. Bei mehr Daten soll ein kleiner, zeitlich validierter Modellversuch gegen dieselbe Baseline geprüft werden.

## 6. Fairness, Risk & Human-in-the-Loop

Historische Lücken, variierende Übungsnamen und wenige vergleichbare Beobachtungen können Trends verzerren. Die Empfehlung ist in der UI als Signal mit Abweichungsmöglichkeit gekennzeichnet.

**Implementiert:** Das LLM erhält nur Übung, festgelegte Kategorie, Trendgrund, Prognose und Testumfang. Die gesamte Historie wird nicht übertragen. Das Ausgabeformat hat feste Felder; bei abweichender Kategorie, fehlenden Feldern, neuen Ziffern oder API-Fehler wird die deterministische Erklärung angezeigt. Die Kategorie in der UI stammt immer aus der Entscheidungslogik.
Handlungsformulierungen in der generierten Zusammenfassung oder Trendbeschreibung lösen ebenfalls den Ersatztext aus. Die angezeigte Begründung und der Unsicherheitshinweis stammen stets aus der deterministischen Analyse.

**Getestet:** Simulierte API-Ausfälle und eine LLM-Antwort mit geänderter Kategorie lösen den Ersatztext aus. Eine echte API-Antwort wurde nicht systematisch auf Verständlichkeit oder semantische Faktentreue evaluiert. Die formale Prüfung kann widersprüchliche freie Formulierungen nicht vollständig erkennen; deshalb bleiben die berechneten Fakten getrennt sichtbar.

**Live-Test:** Der erste Test fiel in der Sandbox wegen `APIConnectionError` zurück. Mit Netzwerkzugriff trat zunächst `AuthenticationError` auf. Die Ursache war ein bereits gesetzter Prozesswert für `OPENAI_API_KEY`, der den abweichenden Wert in `.env` überlagerte. `src/parser.py` lädt die lokale `.env` nun ausdrücklich mit Vorrang; ohne Datei bleibt ein Bereitstellungswert aus der Umgebung nutzbar. Der anschließende Live-Test `python -B -m db.smoke_explanation` lieferte `source: llm` bei unveränderter Entscheidungskategorie. Es wurden keine Schlüssel ausgegeben. Dies prüft den technischen API-Pfad, nicht die wissenschaftliche Qualität der Erklärung.

`python -B -m db.smoke_parser` verarbeitete eine synthetische Notiz zu genau einer strukturierten Satzzeile mit den zwölf erwarteten Spalten. Dieser Test schrieb keine Datenbankeinträge.

## 7. Limits & Next Steps

### Vier Grundvorlagen

Am 8. November 2026 wurden die vier Grundvorlagen aus den häufigen Übungen der letzten Einheiten erstellt. Schreibvarianten der Workout-Namen wurden bei der Auswertung gemeinsam betrachtet; seltene Varianten und frühere EMOM-Warmups wurden nicht automatisch übernommen. Die Auswahl ist eine bearbeitbare Ausgangsbasis, keine Behauptung über einen optimalen Trainingsplan.

| Vorlage | Übungen in Reihenfolge |
|---|---|
| Leg 1 | Leg Extension; Hacksquat; Romanian Deadlift; Bulgarian Split Squat; Waden Excentric Smith Machine; Hipthrust Maschine |
| Upper Body 1 | Bench Press; Row Machine; Shoulder Press Db; Seitheben Kzh; Face Pulls; Reverse Fly Maschine |
| Leg 2 | Leg Curl; Leg Extension; Hacksquat; Bulg Split Squat; Hip Thrust; Waden Smith Machine |
| Upper Body 2 | Incline Bench; Cable Row Shoulderwide-Grip; Lat Pulldowns; Bizeps Sz Curl Seated; Dumbell Bizeps Curls Seated; Triceps Rope Pushdown; Reverse Fly Maschine |

Vorher wurde eine Kopie mit `python -B -m db.seed_core_templates --test-copy` geprüft. Vor dem Live-Lauf wurde der aktuelle Datenbestand nach `data/workout_log.before_core_templates.duckdb` gesichert. Die spätere Verifikation ergab 1.841 aktuelle Legacy-Zeilen, 1.841 Herkunftsabbildungen und 1.841 normalisierte Sätze; die ursprünglichen 1.776 Zeilen blieben enthalten. Die Typen von Leg Extension und Triceps Rope Pushdown wurden im Katalog für neue Einheiten als `external` festgelegt; historische Satz- und Typ-Momentaufnahmen blieben unverändert.

Die vorläufige Gruppierung ist freigegeben und umgesetzt. Sie kann historische Mehrfacheinheiten am selben Tag zusammenfassen. Der ursprüngliche Datenbestand und die Zeilenherkunft bleiben erhalten.

Offen bleiben eine manuelle Prüfung verdächtiger historischer Gruppen, Bedienungstests auf echten Mobilgeräten, eine qualitative Evaluation echter LLM-Erklärungen durch Menschen und ein erneuter Modellvergleich bei längeren Zeitreihen. Neue Parser- und Tabellenimporte werden in einer Transaktion sowohl in die bisherige Dashboard-Tabelle als auch in die neue Historie geschrieben; ein Test prüft die Synchronität. Nach dem Import zeigt die Oberfläche die aus DuckDB erneut gelesenen Sätze als Speicherbestätigung. Das Dashboard liest die aktuellen normalisierten Sätze, damit nachträgliche Korrekturen auch seine Kennzahlen verändern. Die ursprünglichen Legacy-Zeilen bleiben als Sicherungsquelle bestehen.

### Tatsächlich ausgeführte Tests

`python -B -m unittest discover -s tests -v`: sechzehn Tests erfolgreich. Geprüft wurden Katalog und Archivierung, die vier Grundvorlagen auf einer Kopie samt wiederholbarem Lauf, Satz-Tracking, Wiederherstellung einer laufenden Einheit aus der Datenbank, Korrektur mit Änderungsprotokoll, Validierung der Satztypen, unveränderte Legacy-Altzeilen, Migration auf einer Kopie der realen Datenbank, synchroner Neuimport, Parservertrag, sichtbare Parser-Vorschau und Speicherbestätigung, zeitliche Baseline, Trendregeln, LLM-Ersatz, Ausgabeformat und Streamlit-Rendering aller fünf Tabs einschließlich der Verwaltungsansichten. UI-Interaktion auf echten Geräten und Live-LLM-Qualität sind **nicht getestet**.

`streamlit run app.py --server.headless true --server.port 8502` startete erfolgreich; der lokale Health-Endpunkt antwortete mit HTTP 200. Der Testserver wurde anschließend beendet.
