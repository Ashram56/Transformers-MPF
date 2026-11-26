# Global method: what changed with Transformers, and how a weaker agent runs it

Internal draft, 2026-11-26 (to complete when the QA thread ends). These are changes to the plan of
Stern-SAM-Decryption `agents/README.md` and to the agent files, learned between 2026-11-24 (strict rule) and
2026-11-26. Per item: what to change, and where it would go upstream.

## 1. The order that worked

The plan says A, then C. With the strict rule the real sequence on tf_180 was:

1. **Inventory and strict check first.** `docs/boards_inventory.md`, `tools/check_strict_rule.py`, every captured
   file declared (T23). The check's failure count is the progress bar (tf_180: 268, then 41, 40, 2, 1, 0).
2. **Build the code runner once** (T01), with a pilot effect that has a known capture.
3. **Lift by kind**: effects (T02), state variants (T03, T04), animation tables (T05), lamp shows, coil times
   (T16), formatters (T15), service menu (T20).
4. **Whole scenarios in code** (T11, T12): switch handlers and every spec line still "observed" re-cited from
   the run's result.
5. **Name every function** (T14), so the QA reviewers read names that say what the code does.
6. **QA**: independent review, then the conversion matrix, then the final table MPF against code (T27, T28).
   Each finding is fixed from the code with a regression test.

Upstream: SSD `agents/README.md` section 3 (order) and `rom_extraction.md` section 13 (suggested order).

## 2. Gates with numbers

A weaker agent must never decide "it looks right". Each step has a number to reach, and the step is not done
until it is reached and written in the progress report:

| Gate | Number |
|---|---|
| Strict check | failures do not go up; 0 at the end, or each remaining one has an owner decision |
| Tests | `pytest -q tests` all pass |
| Trace floor | the per-scenario comparison counts never go down (tf_180: 172 of 173 checks) |
| Lifts | runs that end / total; matches against old captures / total |
| Parsers | items read / items expected (T25) |
| Naming | `FUN_` left = 0 |
| QA | open rows each with a `rom_differences.md` row |

Upstream: SSD `rom_extraction.md` section 0 (new ground rule "every step ends on a number"), MGP `recreation.md`.

## 3. Facts and their tags

- **observed** is open work, not a source (owner, 2026-11-26). The only accepted exceptions are written owner
  decisions in `docs/pinmame_waivers.md` (tf_180: the flipper times until decoded, the tilt ball-save capture
  F15, the Xilinx CPLDs not decoded).
- **Running ROM code in Unicorn is decoding** (owner, 2026-11-25), because the values come from the ROM's
  instructions, not from a model of the machine. A PinMAME run is not.
- A value that cannot be in the code (the ball's travel, MPF device timing) is labelled as such and composed with
  the code part (T17); it is never called "decoded".

Upstream: SSD `rom_extraction.md` ground rules 0 and 2.

## 4. Two agents at once (A and C on stacked branches)

What worked on tf_180 (agent A on `claude/project-thread-4g3ggx`, the QA / recreation thread on
`claude/project-thread-y1zqep`, A's PRs based on the QA branch):

1. **Batched requests.** C sends A one message per need, with everything A needs: the effect ids, tables,
   offsets, the trace and time that show the gap, and what C will do itself (tf_180 SC6: one message, 9 deffs,
   their tables and the sound ranges).
2. **One owner per shared file.** Files both touch (`docs/boards_inventory.md`, `docs/qa/README.md`,
   `docs/pinmame_waivers.md`) have one owner; the other merges the owner's branch before editing and keeps the
   owner's wording.
3. **Merge, never rebase, the other's branch**, then run the tests and the strict check on the merge, and reply
   with the merge commit and the numbers.
4. **Disputes are settled by the code.** When C's game and A's data disagree (deff 92's length), A answers with
   the code's sum and the trace measured the right way (T08); the side that is wrong changes.

Upstream: SSD `agents/README.md` section 5 (rules every agent follows).

## 5. Writing for a weaker model

The agent files are read by models that will follow them literally. What to change in how they are written:

1. **Recipes, not essays.** Each method as numbered steps, a check with a number, the traps in the order they
   cost time, and the game's value as the example (the format of tricks.md part 2).
2. **Pilot then scale.** Every new tool runs first on one item with known independent evidence; scaling waits for
   the pilot's check.
3. **Name the addresses to find before the work starts** (T01 step 2) and how to find each (SSD 5.1 does this
   for the OS API; extend it to `task_current`, the bank register, the constructor table, the dedicated switch
   table, the request flag of the rule records).
4. **One tool per question, written to a file.** A finding lives in a CSV or JSON produced by a script in
   `rom/tools/`, rerunnable, never only in a chat message.
5. **Never weaken a check to pass.** A test that fails is a finding; a threshold is changed only with the owner's
   decision recorded.
6. **Never trust a name or a value carried from another game** until its body or its table is read in this ROM.

## 6. Escalation: defer what you cannot finish to a more capable agent

Owner request, 2026-11-26: an agent that is stuck on a task hands it to a more capable agent instead of guessing.

**Stuck means any of these:**
- the same check failed after **two** honest attempts with different hypotheses;
- a mismatch between the code and a trace (or a capture) that you cannot explain from the code within about
  **30 minutes** of work;
- the task needs a **new tool design** rather than running or extending an existing one: a new code runner,
  scheduler, FIQ or bank model, a new attribution rule (T01, T04, T11, T12 are of this kind);
- you would have to **guess** a value, an address or a name to go on;
- you are about to **weaken a check**, skip a test, or mark something "observed" to get past it.

**What to do:**
1. Stop that sub-task. Do not commit a guess.
2. Write a handoff note in the repository (`docs/handoff/<date>_<topic>.md`): the goal; what you tried, with the
   commands and their output; the evidence (addresses, files, trace and time); the exact failing check; what you
   think the next step is; what you did not touch.
3. Report it as a **blocker** in your progress report and to the coordinator, naming the note and asking for a
   more capable agent (a stronger model, or a thread with more effort). In a Claude project the coordinator starts
   that thread or switches the model; outside a project, tell the owner.
4. Go on with the rest of your checklist that does not depend on it.
5. The more capable agent works from the note, writes its finding back into the method (tricks.md style), so
   the next weaker agent no longer needs to escalate for that class of problem.

**What a weaker agent can do alone** (tf_180 experience): run an existing lift on new ids; extract a table whose
reader exists; port an op list or a decoded table into the game; fix a QA row whose ROM address and expected
value are given; add a regression test; update docs and the strict-check declarations.
**What to escalate by default:** writing or changing a code runner; anything in the OS scheduler, FIQ, bank
switching or the switch dispatcher; a code / trace disagreement; a decision that needs the owner (that one goes to
the owner, not to a stronger model).

Upstream: SSD `agents/README.md` section 5 (a new rule) and MGP `agents/README.md` (same rule).
