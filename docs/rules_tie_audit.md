# AC38 Challenger Tie Procedures & Rules Audit

**Document Reference**: `docs/rules_tie_audit.md`  
**Governing Documents**:
- *Protocol Governing the 38th America's Cup* (incorporating Amendments 1–10; `Protocol AC38.10`)
- *Conditions Governing The Louis Vuitton Cup and the 38th America's Cup Match* (`LVC/Match Conditions v0`)
- *Racing Rules of Sailing – America's Cup Edition* (`RRSAC v5.02`)

---

## 1. Executive Summary

This audit establishes the precise, governing tie-breaking rules and qualification structures for the 38th America's Cup (AC38), resolving ambiguity in tournament simulation and outer rule bounds:

1. **Round-Robin Tie Scope (RRSAC 102.1)**: Ties in the Louis Vuitton Cup (CSS) round-robin stage are **only broken to determine the 1st placed Challenger** (who selects their semi-final opponent) and the **last placed Challenger** (for repêchage seeding). Intermediate ties (e.g., 2nd vs. 3rd) do not alter advancement.
2. **Advancement Architecture (Conditions 4.5 & 4.6)**:
   - **Top 3 Challengers** from Group Stage 2 progress directly to the Semi-Finals.
   - **4th, 5th, and 6th Challengers** enter Group Stage 3 (Repêchage): 6th races 5th (5th starts at +1 score); the winner then races 4th (4th starts at +1 score). The winner becomes the 4th Semi-Finalist.
3. **Tie Resolution Ladder (RRSAC 102.1 & 102.3)**:
   - Primary: Scheduled sail-off race(s).
   - Secondary (if sail-off cannot be completed): Head-to-head match scores between tied competitors $\to$ most recent match winner $\to$ points against highest non-tied competitors $\to$ Preliminary Regatta standings $\to$ random draw.
4. **Feasible Slot Bounds (`feasible_slot_rule_bounds`)**: When a simulation trial encounters an unresolved tie branch, outer bounds must only attribute unresolved probability mass to teams that are mathematically and topologically feasible contenders for that tournament slot, eliminating uninformative $[0.0, 1.0]$ envelopes for eliminated or non-tied teams.

---

## 2. Tournament Progression & Carry-Over Scoring

### 2.1 Group Stage Structure (Conditions 4.1, 4.5, 4.6)
The Challenger Selection Series (CSS) consists of:
- **Group Stage 1**: Fleet Races (6 fleet races, scored under RRSAC 105.2 as `[10, 9, 8, 7, 6, 5, 4]` points for 7 boats).
- **Group Stage 2**: Up to 3 Round Robins (1 point per win against Challengers).
- **Group Stage 3**: Repêchage.
- **Semi-Finals & Final**: Knockout match racing (first-to-5, then first-to-7).

### 2.2 Carry-Over Points (Conditions 5.2)
Fleet racing finishing positions from Group Stage 1 carry forward into Group Stage 2:
- **Challengers-Only Carry (Protocol Article 7.3(b) / Conditions 5.2(a))**:
  - 1st Challenger: 2.5 pts
  - 2nd Challenger: 2.0 pts
  - 3rd Challenger: 1.5 pts
  - 4th Challenger: 1.0 pt
  - 5th Challenger: 0.5 pt
  - 6th Challenger: 0.0 pt
- **Overall Carry (including Defender; Conditions 5.2(b))**:
  - `[3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 0.0]`.

---

## 3. Official Tie-Breaking Procedures

### 3.1 RRSAC Rule 102.1: CSS Round-Robin Ties
> *"In the Challenger Selection Series, ties will only be broken when scoring the Challengers as Protocol Article 7.4(a). Ties will only be broken to determine the first and last placed Challenger. References to scores and tie breaking of the Final Preliminary Regatta will only include races between two Challengers (excluding all races between a Challenger and the Defender)."*

#### Step 1: Sail-Off (RRSAC 102.1(a))
- **Two Challengers tied**: Decided in favour of the winner of a single sail-off race.
- **Three Challengers tied for 1st**: Highest-placed Challenger from Final Preliminary Regatta advances to sail-off final (or winner of draw). Other two race; winner meets top seed.
- **Three Challengers tied for 3rd**: Lowest-placed Challenger from Final Preliminary Regatta advances to 2nd race (or loser of draw). Other two race; loser meets bottom seed.
- **Four Challengers tied**: Seeded bracket (1st vs 4th, 2nd vs 3rd) based on Final Preliminary Regatta.

#### Step 2: Algorithmic Resolution (RRSAC 102.1(b) $\to$ RRSAC 102.3)
If the Regatta Director determines it is impractical to complete the sail-off before the ACP agreed cutoff date, ties are broken via the 102.3 ladder:
1. **Head-to-head score (102.3(a))**: Highest score in matches between the tied competitors.
2. **Most recent match (102.3(b))**: If between two competitors, winner of the last match between them.
3. **Points against highest non-tied competitor (102.3(c))**: Most points against the boat placed highest in the round-robin stage (then second highest, etc.).
4. **Prior Preliminary Regattas standing (102.3(d))**: Overall standing in combined prior Preliminary Regattas.
5. **Final Preliminary Regatta standing (102.3(e))**: Highest overall standing in Final Preliminary Regatta.
6. **Lot / Draw (102.3(f))**: Winner of a random draw.

---

## 4. Knockout & Match Stage Ties

### 4.1 CSS Knockout Stages (RRSAC 102.2)
Ties between competitors in the Semi-Finals or Finals:
1. One-race sail-off if schedule permits.
2. Winner of the most recent match in that knockout stage.
3. Highest place (amongst Challengers) in the round-robin stage.

### 4.2 America's Cup Match (RRSAC 102.4)
> *"102.4 There is no tie break in the 38th America's Cup Match."*

---

## 5. Implementation in `cup.py` (`feasible_slot_rule_bounds`)

When a simulation trial encounters an unresolved tie or timing stoppage:
1. **Defender Contenders**: The Defender (NZL, index 0) can always feasibly win the Cup in any trial where the Challenger is unresolved.
2. **Challenger Contenders**:
   - Challengers mathematically eliminated before the tie cannot win under any resolution.
   - For round-robin ties, only teams participating in the tie or already advancing can occupy the top 4 semifinal spots.
   - In repêchage ties, only the 4th, 5th, and 6th Challengers are affected; teams that finished 1st–3rd remain locked into the semifinals.
3. **Tightened Rule Bounds**:
   $$\text{Lower}_i = \frac{1}{N}\sum_{t=1}^N \mathbf{1}(\text{resolved}_t \land \text{champion}_t = i)$$
   $$\text{Upper}_i = \frac{1}{N}\sum_{t=1}^N \mathbf{1}(\text{feasible\_champion}_{t, i})$$
   This guarantees that $\text{Lower}_i \le \text{Upper}_i \le 1.0$ and prevents eliminated teams from receiving uninformative mass.
