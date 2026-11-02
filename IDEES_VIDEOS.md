# Idées pour le screener tirées de la playlist YouTube (31/10/2026)

État au 02/11/2026 : **[codé]**, **[déjà là]** ou **[non codé]**, avec la raison. Réglages dans `screener/config.py`. Sources détaillées : `bibliotheque-technique/youtube/notes/`.

## OPR (vidéo OPR 3.0, ZmEib0PNTvo)
- **[déjà là]** **Flux « bâtard »** (`flux_label` classe ce cas en neutre) : exiger aussi une clôture H1 du bon côté de l'EMA50 (sinon pas d'OPR) [13:11].
- **[codé]** **Annuler l'ordre limite** si l'équivalent de R1 est touché avant exécution (backtest et alertes) [29:18].
- **[déjà là]** **Première cassure du jour seulement** [29:18].
- **[non codé]** (réintégrations non alertées, décision du 30/10/2026) **Réintégration** : exiger R ≥ 2 jusqu'à la borne opposée [28:17].
- **[codé]** (sans calendrier : la bougie de 10h New York est ignorée tous les jours) **Horaires** : rien autour de 16h (news), rien après ≈ 19h30 [30:20].
- **[non codé]** (il faudrait le VIX dans le screener) **Stop** : ATR H1 si VIX > 20, sinon stop vol ; comparer les deux [24:17-28:17].

## Bulles (QPEL3pUjqPo, fjMm8MQmMoQ)
- **[codé]** La **mèche de la bulle doit être l'extrême du mouvement** (sinon pas de signal) [33:49].
- **[codé]** Ignorer une bulle si 2-3 bougies précédentes ont déjà clôturé hors des bandes (accélération) [30:29].
- **[codé]** Contre-argument : bulle H4 opposée → bloquer l'OPR dans l'autre sens ce jour-là (checklist _BuKVJt_uxQ [12:12]).

## Divergences (2d43oh-_Tzg, UO__mWR8IhM)
- **[non codé]** (nouveau signal, pas un filtre) Seconde entrée sur **pullback du bruit** (RSI qui revient tester le bruit).
- **[non codé]** (mesuré : 16 trades seulement, rien à conclure) Tester l'asymétrie haussière / baissière (Lefort : les baissières échouent) et un time stop (6 bougies).
- **[non codé]** (pas de score dans le screener ; mesure sans valeur sur 16 trades) Bonus de score si la divergence est sur une zone (VAL/VAH, polarité).

## Sweeps / volume (6AQjcrKBloU, zTQAqwdiIDc, H-MmWKC5H68)
- **[non codé]** (sweeps en journalier seulement, définition à préciser) Ajouter les LVN de la veille et les POC de séance alignés avec un HVN comme zones candidates.
