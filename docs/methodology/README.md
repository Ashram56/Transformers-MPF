# Methodology notes from Transformers Pro 1.80 (internal draft)

*Résumé (FR).* Ce dossier rassemble, pour un agent moins performant qui refait le travail sur un autre jeu, les
« astuces » qui ont demandé de la réflexion pendant le décodage de tf_180 depuis la ROM et sa conversion en MPF
(fils « Décoder les captures depuis la ROM » et « Appliquer les nouvelles règles QA », 2026-11-24 au 2026-11-26).
[tricks.md](tricks.md) : la liste des astuces (partie 1) et une méthode pas à pas par astuce (partie 2).
[global_method.md](global_method.md) : les changements de la méthode globale, dont la règle d'escalade vers un
agent plus capable. Brouillon interne : rien n'est encore proposé à Stern-SAM-Decryption ni à
MPF-Godot-Packaging. Une autre session a reçu la même demande ; après le feu vert de Vincent, on relit les deux
dépôts et on n'ouvre de PR que pour ce qui n'y est pas déjà (colonne « Upstream » de tricks.md).

**Status.** Draft complete as of 2026-11-26 15:45 UTC: it covers the QA thread up to its last commit `03df8fc7`
(QA final F064; the thread is waiting for review). 33 tricks. Nothing here is pushed to Stern-SAM-Decryption or
MPF-Godot-Packaging until the owner says so (owner, 2026-11-26).

**Sources.** PR #15, #17, #18, #19 (agent A, merged into PR #14), PR #14 (QA and recreation fixes, 120 commits on
`claude/project-thread-y1zqep`), `docs/qa/` (the 2026-11-25 review, the 2026-11-26 conversion matrix of 3,095
rows, the final table `docs/qa/final/mpf_vs_code.csv`), `rom/tools/` (the code runners), and what is already
upstream: Stern-SAM-Decryption `agents/rom_extraction.md` sections 0 and 3.3 (PR #84, merged 2026-11-26; PR #87
open), `knowledge/dmd_animation_durations.md` (PR #86), MPF-Godot-Packaging `agents/recreation.md` section 5b
(PR #109).

**How to use it later.** The "Upstream" column of [tricks.md](tricks.md) says, per trick, whether the method is
already in the shared repositories (then only a pointer or a missing step is to add) or not (then the whole
recipe goes there). Route: decoding (agents A and B) to Stern-SAM-Decryption, MPF side (C to G) to
MPF-Godot-Packaging. Game facts (addresses, values) stay here as the worked example.
