# Functional diagram: Transformers Pro 1.80 (`tf_180`), one ROM address per node

STRICT RULE item 5 ([CLAUDE.md](../CLAUDE.md)): the visual diagram of the game taken from the code, one ROM address
per node. Written 2026-11-25 by the QA pass ([docs/qa/README.md](qa/README.md)), **after** the game was coded,
from agent A's rule specs (`rom/rules/modes/*.md`); every address below is one those specs cite from
`rom/code/tf_decompiled.c`, and `tests/test_functional_diagram.py` checks that each one is a function start (or a
ROM table) in the decompile. Addresses below 0x00036000 are the SAM OS; game code starts at 0x01000000; ROM tables
at 0x040xxxxx. A node marked `?` is one the QA audit found wrong or unproven: see the QA report.

Each chart reads top to bottom: start condition, the shots' awards, completion, end. The game's code for each
part is the file named under the chart.

## 1. Game flow (OS)

```mermaid
flowchart TD
  A[Attract, gf_state 0x10] -->|START with credit| GS["Game start 0x00019c64<br/>event 0x2f veto, state 0x20, audit 17"]
  GS --> BS["Ball start 0x00019d30<br/>event 0x12, kill tasks 0x80"]
  BS -->|first ball of player| PI["Per-player init: event 0x26 hooks<br/>skill counters 0x010318cc"]
  BS --> PB["Per-ball init: event 0x11<br/>shot mult 0x01023418"]
  PI --> PB
  PB --> SV["serve_ball(3) 0x0103b39c<br/>deff 19 score display"]
  SV --> SK["Skill shots armed 0x01031518"]
  SK --> VP["Valid playfield 0x0000e264<br/>ball save 0x00017acc (adj 38)"]
  VP --> PLAY((Play: switch handlers, section 2))
  PLAY -->|tilt bob| TL["Tilt 0x0001da8c / 0x0001db40"]
  PLAY -->|drain, no ball save| EB["End of ball 0x00019e44<br/>bonus 0x01000ffc"]
  TL --> EB
  EB -->|shoot again| BS
  EB -->|next player / ball| RO["Rotation 0x0001abb4"] --> BS
  EB -->|last ball of last player| GO["Game over 0x0001a144"]
  GO --> HS["High score entry 0x00018d54"] --> MT["Match 0x00019668"] --> A
```

Game: `game/tf/os_layer.py`, `game/tf/features/skill_shot.py`, `game/tf/features/bonus.py`, `game/tf/features/game_over.py`.

## 2. Switches to features

```mermaid
flowchart LR
  S3["sw 3 Allspark eject 0x0100a788"] --> AS[Allspark, section 6]
  S3 --> MS
  S5["sw 5/6 left orbit 0x01033244"] --> MS["Mode-start shots 0x01020074"]
  S10["sw 10 left ramp 0x01033824"] --> MS
  S14["sw 14 right ramp 0x01033918"] --> MS
  S12["sw 12 right orbit 0x01033488"] --> MS
  S11["sw 11 center lane 0x01025de4"] --> OPA[Optimus access, section 4]
  S38["sw 38-41 Megatron lock 0x0100a3b8 (score at 0x0100a420)"] --> LK[Megatron lock, section 3]
  S51["sw 51 Optimus target 0x010262f0"] --> OPB[Optimus battle, section 4]
  SP["pops 0x01032f8c"] --> PO["Pop value 0x0102ca98 / 0x0102c8c8"]
  SP --> MV["Move lit battle 0x01022cf8"]
  SPIN["spinner 0x01033a08"] --> SPV["0x01032294 / 0x010320a4"]
  BB["Bumblebee target 0x01033adc"] --> DS["Double scoring 0x01001a70 / 0x010039a0"]
  BB --> MV
  TB["2-bank sw50 0x01033c00 / sw37 0x01033c40"] --> FS["Fast scoring 0x0102e9c0 / 0x01004394"]
  EN["Energon sw 2/49/46 0x010309a4"] --> ENC["Set complete: lock count, call at 0x01030b34 in 0x010309a4"]
  LN["Lanes 0x0102db28 / 0x0102e208"] --> SM["Shot multipliers 0x010236e8 / 0x010237ac"]
  MS --> CB["Combos 0x01002f0c / 0x01002be4 / 0x01002b5c, table 0x040c5c7c"]
```

Game: `game/tf/switches.py` and the feature files in `game/tf/features/`.

## 3. Megatron lock and multiball

```mermaid
flowchart TD
  L0["Game start: lock level = adj 68 0x0100ada4<br/>completions needed 0x0100acb4"]
  L0 --> GATE{"Lock may light? 0x0100ae6c<br/>no MB, mtl_lit 0, lit+locked < 4"}
  ENC["Energon set complete, call at 0x01030b34 in 0x010309a4"] --> GATE
  GATE -->|count down| CNT["mtl_count -1, 5,000 0x0100af0c"]
  GATE -->|last| LIT["Lock lit: deff 139, leff 167, 10,000 0x0100af0c"]
  LIT --> ENT{"Lock entry 0x0100b0b8<br/>lit and no MB"}
  ENT -->|ball 1-3| LCK["BALL n LOCKED, 25,000 0x0100b130"]
  ENT -->|4th| MB{side}
  MB -->|Autobot| MBA["Start A 0x0100c200: 250,000, deff 69"]
  MB -->|Decepticon| MBD["Start D 0x0100e0bc: 100,000, deff 75"]
  MBA --> RA["A rules 0x0100c430"]
  MBD --> RD["D rules 0x0100e29c"]
  RA --> END["One ball left 0x0100c814, grace, total deff 74/80 0x0100c790"]
  RD --> END
  END --> LV["level +1, relock state 0x0100ad70"]
  HOLD["Device keeps balls 0x0100a1f8"] -.-> ENT
```

Game: `game/tf/features/megatron.py`.

## 4. Optimus battle and multiball

```mermaid
flowchart TD
  CL["Center lane x4, nothing running 0x01025de4"] --> OB["Optimus battle: target hits 0x010262f0"]
  OB -->|last hit, 2,000,000| SD{side}
  SD -->|Autobot| OA["Start A 0x01027994"] --> RA["A rules 0x01027b74"]
  SD -->|Decepticon| OD["Start D 0x01029a08"] --> RD["D rules 0x01029bf4"]
  RA --> E["One ball left, grace, total deff 62/68<br/>0x01027ec0 / 0x01029fa4"]
  RD --> E
```

Game: `game/tf/features/optimus.py`, `game/tf/features/optimus_mech.py`.

## 5. Character battles

```mermaid
flowchart TD
  R["Reset per player 0x0101fe98"] --> Q{"Qualifying allowed 0x0101fdac<br/>start allowed 0x01022ca8"}
  Q --> MSH["Flashing mode-start shot hit 0x01020074<br/>10,000 + 5,000 x hits"]
  MSH -->|4th| ST["Battle start 0x01022e08<br/>100,000, intro, wizard item 0x01035af0"]
  MSH -->|else| RL["Relight a random unlit shot 0x0101ffa0"]
  MV["Move lit battle 0x01022cf8 (pops, Bumblebee)"] -.-> ST
  ST --> B1["Starscream 0x0101795c"]
  ST --> B2["Shockwave 0x0101e400"]
  ST --> B3["Blackout 0x0101caa4"]
  ST --> B4["Devastator 0x01015dc0"]
  ST --> B5["Bumblebee 0x010142dc"]
  ST --> B6["Ironhide 0x0101adc8"]
  ST --> B7["Mudflap and Skids 0x01019150"]
  ST --> B8["Ratchet 0x01012318"]
  B1 & B2 & B3 & B4 & B5 & B6 & B7 & B8 --> EN{"End 0x010230d0"}
  EN -->|last shot| CP["Completed: wizard item 0x01035af0(item, 2), total deff"]
  EN -->|timer 0 / drain / tilt| KL["Killed 0x01023048 (hooks 0x010232d4), total deff"]
```

Records: ROM table 0x040c6e08 (8 x 0x28 bytes). Game: `game/tf/features/battles.py`.

## 6. Energon, Allspark, wizard modes

```mermaid
flowchart TD
  E["Energon hit 0x010309a4<br/>unlit 75,000 / lit 10,000 / MB 5,000"] -->|third lit| ES["Set: 250,000 + 25,000 x sets, Allspark banked"]
  ES --> LKC["Megatron lock count, call at 0x01030b34"]
  A["Allspark eject 0x0100a754 / 0x0100a788"] -->|Allspark banked| MY["Mystery award 0x010243b4"]
  MY --> AB["Add-a-ball 0x01024a60"]
  A -->|own side's 5 done, gate 0x0100ff80| SM["All Hail Megatron / Autobots Roll Out<br/>start 0x0100fff0, rules 0x01010174"]
  SM -->|super| SME["End 0x010103c0, total deff 85"]
  A -->|all 11 done, gate 0x010363b4| WZ["Wizard multiball start 0x010363ec<br/>rules 0x010365c4"]
  WZ --> WZE["One ball left 0x0103686c / 0x010367c4, total 0x01036814"]
  REQ["Requirements and extra ball 0x01035af0 (adj 83)"] -.-> SM
  REQ -.-> WZ
```

Game: `game/tf/features/energon.py`, `allspark.py`, `wizard.py`.

## 7. Scoring around the modes

```mermaid
flowchart TD
  SW["Any shot"] --> SMU["Shot multiplier 0x01023538 / 0x01023650"]
  LN["Lanes complete 0x0102db28"] -->|own side| SML["Light shot multipliers 0x010236e8"]
  LN -->|other side| BX["Bonus X +1 (cap 25)"]
  EOB["End of ball 0x00019e44"] --> BON["Bonus = (670 x switches + 125,000) x X<br/>0x01000ffc / 0x01000f38"]
  PO["Pop 0x01032f8c"] --> PV["value 3,000 +1,000 to 20,000, decay 0x0102c8c8"]
  SH["Shaker patterns, table 0x040c7620"]
```

Game: `game/tf/features/combos.py`, `lanes.py`, `bonus.py`, `pops.py`, `spinner.py`, `bumblebee.py`, `twobank.py`.

Last updated 2026-11-25.
