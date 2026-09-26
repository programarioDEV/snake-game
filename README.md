# Snake Arena - Adversarial AI Engine

![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![pygame-ce](https://img.shields.io/badge/pygame--ce-2.5-00A86B)
![pytest](https://img.shields.io/badge/pytest-105%2F105%20passing-2EA44F?logo=pytest&logoColor=white)
![mypy](https://img.shields.io/badge/mypy-strict-2A6DB2)

**English** · [Español](README.es.md)

A real-time asymmetric Snake: a human player against an AI that does not just eat and survive, but **attacks**. It squeezes the rival's space, cuts in on its route to food and seals chokepoints to trap it with fewer free cells than its own length. A **spectator mode** pits two autonomous agents against each other in self-restarting match series with a persistent scoreboard.

The core idea of the project is **algorithmic explainability**. Every tick, the AI publishes a `DecisionTrace` with what it perceived and what it intends to do. The view draws it as debug layers: Voronoi partition, A\* path, interception vector, articulation points and a HUD with the utility of each tactical mode.

![Full match recorded headless: the red AI seals a chokepoint and the video replays the lethal cut](assets/showcase.gif)

*Real match (seed 2) recorded headless with `snake-arena record --seed 2 --highlight-lethal --output assets/showcase.gif`. The red AI wins with a lethal cut at tick 310, and the video replays that moment before the final result.*

---

## Contents

1. [System architecture](#1-system-architecture)
2. [Algorithms and mathematical model](#2-algorithms-and-mathematical-model)
3. [Benchmarks and performance](#3-benchmarks-and-performance)
4. [Inspection layer: debug overlays](#4-inspection-layer-debug-overlays)
5. [Recording and exporting replays](#5-recording-and-exporting-replays)
6. [Trade-offs and design decisions](#6-trade-offs-and-design-decisions)
7. [Installation and reproducibility](#7-installation-and-reproducibility)

---

## 1. System architecture

### Layers and dependency direction

Dependencies always point toward the core. `core` imports nothing from the project. `pygame` only appears in `view/` and `record/`, which reuses the same `SceneRenderer` to draw off-screen frames. Pillow and imageio-ffmpeg are optional and only load when exporting.

```
+--------------------------------------------------------------------------------+
|                               snake_arena                                      |
|                                                                                |
|   +---------------------+        +----------------------+                      |
|   |   core/  (pure)     |<-------|  analysis/           |                      |
|   |---------------------|        |----------------------|                      |
|   | Grid  Snake         |        | release_times        |                      |
|   | GameState (frozen)  |        | reach_times  voronoi |                      |
|   | rules.step()        |        | astar  Tarjan        |                      |
|   | spawn_food(rng)     |        +----------------------+                      |
|   +---------------------+                   ^                                  |
|        ^          ^                         | features                         |
|        |          |                +----------------------+                    |
|        |          +----------------|  agents/ (Strategy)  |                    |
|        |           GameState       |----------------------|                    |
|        |           (read-only)     | BaseAgent            |                    |
|        |                           | AggressiveAI (Utility|                    |
|   +---------------------+          |   + perception)      |                    |
|   | engine/             |--------->| HumanController      |                    |
|   |---------------------| decide() | GreedyAgent          |                    |
|   | SimulationEngine    |<---------+----------------------+                    |
|   | deterministic tick  | Decision{direction, trace}                           |
|   | per-agent metrics   |                                                      |
|   | MatchSeries         |  chained rounds, re-seed, post-match pause           |
|   | SeriesStats         |  scoreboard (shared with the benchmark)              |
|   +---------------------+                                                      |
|        |                                                                       |
|        | TickRecord{state, decisions, compute_ms, tick_ms}   (read-only)       |
|        v                                                                       |
|   +------------------------------------------------------+                     |
|   | view/  (pygame-ce)                                   |                     |
|   | SceneRenderer: board + banner + HUD (+ series)       |<------+             |
|   | BoardRenderer: cached alpha layers + overlays        |       |             |
|   | HudPanel: focused agent's reasoning [1]/[2]          |       |             |
|   | SeriesPanel: score, tactics, recent results          |       |             |
|   | ArenaApp: window, fixed tick decoupled from FPS      |       |             |
|   +------------------------------------------------------+       |             |
|                                                                  |             |
|   +------------------------------------------------------+       |             |
|   | record/  (headless)                                  |-------+             |
|   | MatchRecorder: off-screen Surface -> bytes           |                     |
|   | FrameWriter: GifWriter (Pillow) | Mp4Writer (ffmpeg) |                     |
|   +------------------------------------------------------+                     |
+--------------------------------------------------------------------------------+
```

### Tick flow

```
GameState_t --+--> agent_i.decide(state_t, i) ----------> Decision_i {direction, DecisionTrace}
              |        (engine measures ms per agent)             |
              |                                                   v
              +--> rules.step(state_t, {i: direction_i}) --> TickResult {state', deaths, eaten}
                                                                  |
                         spawn_food(state', rng(seed)) <----------+
                                   |
                                   v
                              GameState_t+1 ---> TickRecord ---> View (renders, never writes)
```

### Why the core is headless and rendering-free

| Decision | Benefit |
|---|---|
| `GameState`, `Snake` and `Grid` are `@dataclass(frozen=True, slots=True)` | Neither the agents nor the view can corrupt the state. Snapshots are shared without defensive copies and are *hashable*, so they work as cache keys. |
| `rules.step(state, moves) -> TickResult` is a pure function | The same state and moves always give the same result. The collision rules are covered by 16 tests without opening a window. |
| The only randomness is `random.Random(seed)`, and it lives in the engine | Every match can be replayed from its seed. The benchmark yields identical wins, deaths and mode mix on every run; only timings vary. |
| `SimulationEngine` does not import `pygame` | Enables windowless benchmarks of thousands of ticks, CI without a display server and a view smoke test with `SDL_VIDEODRIVER=dummy`. |
| The engine clock is injectable (`clock=`) | Latency measurement is tested deterministically with a fake clock. |
| Cells are flat indices `Cell = NewType("Cell", int)`, with precomputed move and adjacency tables | BFS and A\* iterate over integers and precomputed tuples: no `(x, y)` tuples or bounds checks in the inner loop. |

### Tick semantics (combat rules)

- **Simultaneous movement.** Collisions are evaluated on the already-moved board, including the bodies of snakes that die on that same tick. The outcome does not depend on processing order.
- **Deferred growth.** Eating adds `pending_growth`, and the tail stays put on the following tick. At the start of every tick it is already known which tails will move.
- **Head-on collision (*head-to-head*).** The longer snake wins, judged by its length after the move. If both are equally long, both die. A head swap (A moves into B's cell and B into A's) also counts as a head-on collision.
- **180° turn.** Ignored; the snake keeps its direction.

### Repository layout

```
src/snake_arena/
  core/       grid.py  snake.py  state.py  rules.py           domain model and pure rules
  analysis/   occupancy.py  flood.py  astar.py  articulation.py  stateless graph algorithms
  agents/     base.py  perception.py  aggressive.py  human.py  baseline.py
  engine/     config.py  simulation.py  series.py  bench.py   deterministic loop, series and benchmark
  view/       theme.py  board.py  hud.py  series_panel.py  scene.py  app.py   pygame-ce
  record/     writers.py  gif.py  mp4.py  recorder.py        streaming GIF/MP4 export
  __main__.py                                                 CLI: play | watch | record | bench
tests/        105 tests (pytest) + support.py
docs/img/     screenshots of real matches
assets/       showcase.gif / showcase.mp4 generated with `snake-arena record`
```

---

## 2. Algorithms and mathematical model

Notation: $V$ is the set of open cells on the board and $E \le 2V$ the edges under 4-neighborhood. In the default arena (31×31 with cross-shaped walls), $V = 925$.

### 2.1 Time-aware release of body segments

A body is not a permanent wall: each segment frees its cell after a known number of ticks. For a snake of length $L$ with pending growth $g$, the segment at index $k$ ($k = 0$ is the head) frees its cell at:

```math
\tau(c) = L - k + g, \qquad \tau(\text{free}) = 0, \qquad \tau(\text{obstacle}) = \infty
```

A head can enter cell $c$ at time $t$ if and only if $t \ge \tau(c)$. A test checks that this model agrees with `rules.step` on every possible move of a snake chasing its own tail, with and without pending growth (`test_release_times_agree_with_the_rules`).

`reach_times` is a BFS over `collections.deque` that only relaxes an edge when the target cell is already free on arrival: $O(V + E)$. If a cell is still occupied, the BFS can reach it later through a detour, once the segment has left.

### 2.2 Territory partition: multi-source Voronoi BFS, $O(V + E)$

Both heads expand at the same time, layer by layer in time, over the same temporal model. If $d_i(c)$ is the arrival time of snake $i$ at cell $c$ (each source may start at a different time $s_i$):

```math
\text{owner}(c) =
\begin{cases}
i & \text{if } d_i(c) < d_j(c) \\
\arg\max_{\{i,j\}} L^{+} & \text{if } d_i(c) = d_j(c) \text{ and } L_i^{+} \ne L_j^{+} \\
\text{neutral} & \text{if } d_i(c) = d_j(c) \text{ and } L_i^{+} = L_j^{+}
\end{cases}
```

Here $L^{+}$ is `Snake.next_length`, the length after the next move. The tie-break mirrors the head-on rule: if both snakes reach a cell at the same time, the longer one would win the collision, so the cell is its own. The metric shown in the HUD is the control share $\rho = |V_{AI}| / (|V_{AI}| + |V_{rival}|)$.

### 2.3 Pathfinding: weighted A\* over the temporal graph

```math
f(n) = g(n) + w \cdot h(n), \qquad h = \text{Manhattan}, \qquad w = 1.25 \;\Rightarrow\; \text{cost} \le 1.25 \cdot \text{optimal}
```

- **Edge cost.** It is $1 + \text{penalty}(c)$. When the AI is **not** longer, the cells the rival can reach on the next tick cost $+12$, and the ring after that, where the rival could close a pincer, $+4$.
- **Reaching the goal.** The goal cell is entered only if $t \ge \tau(\text{goal})$. Chasing its own tail is therefore an ordinary A\* query.
- **Telemetry** (`PathResult`): path, accumulated cost and `nodes_expanded`, also when there is no path. An expansion limit bounds the worst case.
- **Heap tie-break.** Ordered by $(f, h, \text{counter})$: it prefers nodes closer to the goal and guarantees determinism.

### 2.4 Articulation points: iterative Tarjan, $O(V + E)$

On the graph of cells that are free right now ($\tau(c) = 0$), an **iterative** Tarjan DFS runs rooted at the rival's head. It is iterative to stay clear of CPython's recursion limit on large boards. For each articulation point $v$, the DFS accumulates the size of the subtrees that would be cut off from the root if $v$ were removed. The result is the space the rival would have left if the AI sealed $v$:

```math
\text{cut\_area}(v) = (n - 1) - \sum_{\substack{c \,\in\, \text{children}(v) \\ \text{low}(c) \,\ge\, \text{disc}(v)}} |\text{subtree}(c)|, \qquad n = |\text{root component}| - 1
```

Every cut comes out of **a single pass**, with no flood fill per candidate.

Why vertex cuts and not bridges? A body occupies cells (vertices), not edges. Besides, any bridge that separates more than one cell has at least one endpoint that is already an articulation point, so the vertex analysis covers the chokepoints that matter.

**Lethal cut** (what triggers `CONSTRICT` with utility 0.95). An articulation point $v$ is a lethal cut when all of the following hold:

```math
\text{cut\_area}(v) < L_{rival} \;\wedge\; t_{AI}(v) \le 10 \;\wedge\; \big(t_{AI}(v) < t_{rival}(v) \;\vee\; (t_{AI}(v) = t_{rival}(v) \wedge L^{+}_{AI} > L^{+}_{rival})\big) \;\wedge\; \text{space}_{AI}(v) \ge L_{AI}
```

The last condition keeps the AI from getting trapped along with the rival.

### 2.5 Predictive interception

1. **Rival's predicted goal.** The nearest reachable food according to $t_{rival}$. If there is none, the reachable cell closest to the center of the board: the rival is cut off from the center.
2. **Predicted route.** Rebuilt backwards from the BFS arrival times, without storing a parent table.
3. **Interception point.** The earliest cell on that route that the AI reaches first, with a lead $\text{lead}(c) = t_{rival}(c) - t_{AI}(c) \ge \lambda$, where $\lambda = 0$ if the AI is longer (it accepts the head-on collision, which it would win) and $\lambda = 1$ otherwise. Articulation points are preferred.

### 2.6 Decision making: utility system with hysteresis

Every tick, `perception.perceive()` computes all the metrics **exactly once**. They score the four tactical modes, and the mode with the highest utility wins.

**Notation.** $L$ and $L_{rival}$ are the lengths of the AI and the rival; $L^{+}$ is the length after the next move; $A$ is the space the AI can reach; $T_{rival}$ is the rival's Voronoi territory; and $\rho$ is the AI's control share (section 2.2). $\text{clamp}(x)$ clips $x$ to the interval $[0, 1]$, and $[P]$ is 1 if condition $P$ holds and 0 otherwise.

#### Auxiliary signals

```math
S = \text{clamp}\left(\frac{3L - A}{2L}\right) \qquad\qquad \text{calm} = 1 - S
```

$S$ is the survival urgency: it is 0 while the AI has at least $3L$ cells and reaches 1 when its space drops to $L$. The `calm` factor damps every offensive mode as danger grows.

```math
h = \text{clamp}\left(\frac{L_{rival} - L + 3}{6}\right) \qquad\qquad r = \begin{cases} 1 & \text{if the AI wins the race to that food} \\ 0.5 & \text{otherwise} \end{cases}
```

$h$ is hunger: it grows the shorter the AI is compared with the rival.

#### Utility of each mode

```math
U_{\text{FORAGE}} = (0.35 + 0.45\,h) \cdot r \cdot \text{calm}
```

```math
U_{\text{INTERCEPT}} = \big(0.45 + 0.3\,[\text{cut at an articulation point}] + 0.1\,[L^{+} > L^{+}_{rival}]\big) \cdot \text{calm}
```

```math
U_{\text{CONSTRICT}} = \begin{cases} 0.95 \cdot \text{calm} & \text{if a lethal cut exists} \\ 0.8 \cdot \text{clamp}\big(\max(\sigma,\ \delta)\big) \cdot \text{calm} & \text{otherwise} \end{cases}
```

```math
\sigma = \frac{4L_{rival} - T_{rival}}{3L_{rival}} \qquad\qquad \delta = \begin{cases} (\rho - 0.55) / 0.25 & \text{if } L^{+} > L^{+}_{rival} \\ 0 & \text{otherwise} \end{cases}
```

```math
U_{\text{SURVIVAL}} = \max(S,\ 0.1)
```

$\sigma$ measures how starved the rival is: 0 when its territory is $4L_{rival}$ cells and 1 when it drops to $L_{rival}$. $\delta$ measures dominance: it goes from 0 to 1 as the AI's control share rises from 55% to 80%, and it only counts when the AI is longer.

| Mode | High utility when… |
|---|---|
| `FORAGE` | the AI is shorter than the rival and reaches the food first |
| `INTERCEPT` | there is an interception point on the rival's predicted route, especially at a chokepoint |
| `CONSTRICT` | a lethal cut exists, the rival's territory is shrinking, or the AI is longer and dominates the board |
| `SURVIVAL` | the AI's space approaches its length; the 0.1 floor always leaves a fallback plan |

The outcome is an asymmetric personality: when **smaller, the AI eats**; when **bigger, it harasses**; when it spots a **lethal cut, it strangles**; and when its space shrinks, it **chases its own tail**.

- **Hysteresis.** The previous mode is kept while its gap to the best mode is below 0.08. This stops the mode from flipping every tick and the HUD from flickering.
- **Per-mode planning.**
  - `FORAGE`: A\* to the chosen food.
  - `INTERCEPT`: A\* to the interception point.
  - `CONSTRICT`: A\* to the lethal cut; without one, the move that minimizes the rival's space and territory.
  - `SURVIVAL`: A\* to its own tail; without a path, the move with the most space.
- **Layered safety filter.** It vetoes the mode's proposal when needed. The move pool is the first non-empty tier of this list:
  1. enough space and no losing head-on collision;
  2. enough space and not the cell the rival is predicted to take;
  3. enough space;
  4. any non-lethal move.

  "Enough space" means $A' \ge \min(L, \max A')$, so the AI never enters a pocket smaller than its body if there is an alternative. Every veto is logged in the `rationale` (`| safety -> DOWN`).

### 2.7 Cost per tick

| Step | Operation | Complexity |
|---|---|---|
| Temporal release | 1 pass over the bodies | $O(V)$ |
| Own and rival reach | 2 temporal BFS | $O(V + E)$ |
| Current Voronoi | 1 multi-source BFS | $O(V + E)$ |
| Chokepoints | 1 Tarjan DFS | $O(V + E)$ |
| Scoring up to 3 moves | 3 × (reach + Voronoi + rival reach) | $9 \cdot O(V + E)$ |
| Lethal-cut escape check | ≤ 3 BFS | $O(V + E)$ |
| Mode plan | 1 weighted A\* | $O(E \log V)$ |

In total, about 15 linear passes and one A\* per decision, over $V = 925$ cells.

---

## 3. Benchmarks and performance

Setup: 20 matches, `GreedyAgent` (blue) vs `Offensive AI` (red), 31×31 `cross` arena, seeds 0 to 19, 5,000-tick limit. Machine: AMD Ryzen 7 5700X, Windows 11, CPython 3.12.10, single thread.

The reference opponent (`GreedyAgent`) heads for the nearest food according to the temporal BFS, refuses pockets smaller than itself and avoids head-on collisions it would lose. In other words, it is not a trivial opponent.

### Results

| Metric | GreedyAgent | Offensive AI |
|---|---:|---:|
| **Wins** | 5 / 20 (25%) | **14 / 20 (70%)** |
| Draws | 1 / 20 (5%) | |
| Mean final length | 34.0 | 31.4 |
| Decision latency, mean | 0.53 – 0.59 ms | **3.10 – 3.45 ms** |
| Decision latency, max | 1.21 – 1.83 ms | 5.91 – 7.16 ms |
| A\* nodes per decision | — | 13.3 |
| Deaths WALL / SELF / BODY / HEAD_TO_HEAD | 4 / 4 / 3 / 3 | 1 / 1 / 2 / 2 |

Game outcomes (wins, deaths, modes) are **identical across runs** because they depend on the seed. Latencies are ranges over three full benchmark runs and depend on machine load.

A striking result: the AI wins 70% of the matches while **finishing shorter** on average. It does not win by eating more but by position: territorial control, route cuts and traps.

### Time budget per tick

| Rate | Budget per tick | Mean use (3.10 – 3.45 ms) | Worst case (5.91 – 7.16 ms) |
|---|---:|---:|---:|
| 10 ticks/s | 100 ms | **3.1 – 3.5%** | 5.9 – 7.2% |
| 15 ticks/s | 66.7 ms | **4.7 – 5.2%** | 8.9 – 10.7% |

On average the AI uses under 5% of the budget at 10 ticks/s and about 5% at 15 ticks/s. Even in the worst measured case it leaves more than 89% of the tick free. With the real video driver, the view renders at about 114 FPS (capped at 120) while the simulation holds its 15 ticks/s pace (37 ticks in 2.5 s).

### Empirical breakdown of tactical modes

| Mode | Share | Role |
|---|---:|---|
| `FORAGE` | 61% | Grow while it has no size advantage; deny the food whose race it wins. |
| `INTERCEPT` | 34% | Cut the rival's predicted route to its food or to the center. |
| `CONSTRICT` | 5% | Rare but decisive: seals lethal cuts and wraps around the rival when it dominates the territory. |
| `SURVIVAL` | < 0.5% | Safety net: it only kicks in during endgames, on a saturated board. |

### Mirror duel: the offensive AI against itself

`snake-arena bench --agent-1 aggressive --agent-2 aggressive`, same 20 seeds:

| Metric | #1 Offensive AI | #2 Offensive AI |
|---|---:|---:|
| Wins | 9 (45%) | 11 (55%) |
| Draws | 0 | |
| Mean final length | 35.8 | 36.1 |
| Mean / max decision latency | 3.26 / 8.71 ms | 3.25 / 8.87 ms |
| Deaths WALL / SELF / BODY / HEAD_TO_HEAD | 0 / 1 / 1 / 9 | 2 / 1 / 0 / 6 |
| Modes (F / I / C / S) | 84 / 4 / 12 / 0% | 86 / 4 / 9 / 1% |

Mean duration: 624 ticks.

- **Balance.** The 45/55 split fits a symmetric duel: the starting positions and the arena are symmetric under a 180° rotation, and only the random food breaks the symmetry.
- **Head-on collisions.** They decide 15 of the 20 matches. With two agents that compute identically, neither wins the interception race (`INTERCEPT` drops to 4%). The match is settled by competing for food, where a single cell of extra length decides the head-on collision.
- **`CONSTRICT`** rises to 9–12% (5% against the baseline), because a rival that also controls territory ends up more often in small regions that can be sealed.

### Benchmark-driven tuning

The utilities were not set by eye but by iterating on the same benchmark:

| Iteration | Change | AI wins | Modes (F / I / C) | Mean ticks | AI H2H deaths |
|---|---|---:|---|---:|---:|
| v1 | Initial utilities | 65% | 15 / 83 / 2% | 2,698 | 2 |
| v2 | Grow first; interception bonus only at articulation points; territorial dominance pressure | 70% | 61 / 34 / 5% | 789 | 4 |
| v3 | A\* penalizes the pincer ring; the safety veto avoids the cell predicted for the rival | 70% | 61 / 34 / 5% | 772 | **2** |

v1 spent 83% of the time intercepting and finished as long as the rival, so it could not exploit the head-on rule. v2 made matches 3.4 times shorter but exposed a weakness: the AI let itself get caught in pincers. Diagnosing each death (`perceive()` on the previous state) showed that it approached the head of an equal or longer rival diagonally. v3 fixes that.

---

## 4. Inspection layer: debug overlays

| Key | Overlay | What it shows | `DecisionTrace` field |
|---|---|---|---|
| `[V]` | Voronoi | Translucent tint per owner and a border line between territories | `territory`, `territory_ratio` |
| `[P]` | A\* path | Polyline from the AI's head to its goal | `planned_path`, `path_cost`, `nodes_expanded` |
| `[I]` | Interception | Rival's predicted route (dots), its goal (ring) and a dashed vector to the cut point (crosshair) | `opponent_path`, `opponent_goal`, `intercept_point` |
| `[C]` | Chokepoints | Diamonds on articulation points; magenta fill if the cut is lethal (space < rival's length) | `chokepoints`, `lethal_cut` |
| `[TAB]` | All | Toggles every overlay at once | |

The overlays and the HUD always show the trace of the **focused agent**, selected with `[1]` and `[2]`. By default the focus is on the first offensive agent.

**Tactical HUD** (side panel):

- Both snakes with their lengths; an arrow marks the focused one.
- Active mode (with a color badge) and `rationale`, the textual explanation of the decision, for example `seal chokepoint (3,14): opp room 21 < len 43`.
- Utility bars for the four modes, with the chosen mode highlighted.
- Performance: ms of the last decision, mean and max; ms of the full tick; A\* nodes; path length and cost.
- Territory: control bar of the focused agent against the rival, cell counts, detected chokepoints and how many of them are lethal.
- Legend of symbols and controls.

If the focus is on an agent that publishes no trace (`GreedyAgent` or the human player), the HUD says so and suggests switching focus.

**Debug controls:** `[1]/[2]` switch focus, `[SPACE]` pauses, `[N]` steps one tick while paused, `[R]` restarts the match with the same seed (in spectator mode, once the match is over, it skips the pause and starts the next round), `[+]/[-]` change the simulation speed (2 to 60 ticks/s), `[ESC]` quits. In `play`, the player moves with the arrow keys or WASD, and the input buffer spreads two quick turns over two consecutive ticks.

**Rendering techniques:**

- The base board (background, grid and walls) is drawn once.
- Voronoi tints are precomputed `SRCALPHA` tiles per owner, composited with `Surface.fblits`.
- The territory layer is only rebuilt when the trace changes (once per tick, not per frame).
- The HUD is only redrawn when its data changes.
- The simulation advances with a fixed-timestep accumulator, capped at 5 catch-up ticks per frame to avoid the spiral of death.

### Spectator mode: AI vs AI

`snake-arena watch` pits two autonomous agents (`aggressive` or `greedy`, including the `aggressive` vs `aggressive` mirror duel) against each other in a series of matches with no human input.

- **Automatic restart.** When a match ends, `MatchSeries` records the result, waits for the configured pause (`--delay-restart`, 1 to 2 s) and resets the board with the next seed (`seed + round`). With `--rounds N` it stops after N matches; by default the series never ends.
- **Persistent scoreboard** (third column): current round and countdown, wins and win rate of each agent, draws, mean duration in ticks, tactic mix of each offensive agent (including the match in progress) and the last 12 results.
- **Switching focus without losing the map.** Two offensive AIs publish exactly the same Voronoi partition, because the algorithm is symmetric with respect to the order of the sources (checked by `test_mirror_agents_publish_the_same_voronoi_partition`). That is why the territory tint does not change when switching focus; what changes are the A\* path, the rival's predicted goal, the interception vector and the chokepoints, which belong to the focused agent. If the focus is on an agent without a trace, the map comes from the other agent's trace.
- **Decoupling.** `MatchSeries` lives in `engine/`, does not import `pygame` and is tested without a window. The engine never assumes there is a keyboard: the view only passes it the elapsed time and pause or restart commands.

![Mirror duel in spectator mode](docs/img/watch-mirror.png)

*Mirror duel (seed 3, tick 228 of round 4): the focus is on #2, which cuts #1's predicted route at (6,21) with a 2-tick lead. The right column shows the 1-2 score and each AI's tactic mix.*

### Screenshots from real matches

Both screenshots come from real matches against `GreedyAgent` and were generated with SDL's `dummy` driver.

**Lethal cut (seed 4, tick 701).** The AI (red) seals the corridor at (3,14). The rival, of length 43, is trapped with 21 cells. The HUD shows 3 lethal cuts and 98% territorial control.

![Lethal cut](docs/img/lethal-cut-tick701.png)

**`INTERCEPT` mode (seed 0, tick 110).** The dashed vector joins the AI's head to the cut point (16,18), which lies on the rival's predicted route (blue dots) to the food marked with the ring. The lead is 0 because the AI is longer and would win the head-on collision.

![INTERCEPT mode](docs/img/intercept-mode.png)

---

## 5. Recording and exporting replays

`snake-arena record` plays a full match without opening any window and exports it to GIF or MP4 with the same overlays and HUD as the interactive view.

```bash
snake-arena record --agent-1 aggressive --agent-2 greedy --output assets/showcase.gif
snake-arena record --seed 2 --highlight-lethal --output assets/showcase.mp4
snake-arena record --overlays voronoi --cell 14 --tick-rate 12 --output clips/voronoi.gif
```

### Streaming pipeline

```
engine.tick() --> SceneRenderer.draw(off-screen Surface, same size as the view)
              --> pygame.image.tobytes(surface, "RGB")          a single w·h·3-byte buffer
              --> FrameWriter.write(bytes, repeat=n)
                    |-- GifWriter: global palette -> delta with transparent index -> GifImagePlugin.getdata() -> disk
                    +-- Mp4Writer: pipe to ffmpeg (libx264, yuv420p) through imageio-ffmpeg
```

- **No display.** The CLI sets `SDL_VIDEODRIVER=dummy` before loading Pygame, and the recorder only initializes `pygame.font`, never `pygame.display`. It needs no display server: it is meant for Linux CI, although so far it has only been verified on Windows with the `dummy` driver.
- **Same frame as the view.** `SceneRenderer` composes the board, banner and HUD both for the window (`ArenaApp`) and for the off-screen Surface (`MatchRecorder`), so there are no two render implementations that could drift apart. The size is rounded up to even dimensions, which H.264 requires.
- **Constant memory.** Memory only holds one working Surface, the buffer of the current frame and, for GIF, the previous frame already indexed (one byte per pixel) to compute the delta. Peak process memory measured on Windows: **82 MB** for a 53-frame GIF and **82 MB** for a 593-frame one; 67 MB for the 593-frame MP4. Keeping those 593 frames in RGB would take about 1.2 GB.

### Why the GIF does not use `imageio`

The `pillow` plugin of `imageio` stores every frame in `self.images_to_write` and only writes the file when it is closed. Pillow's `Image.save(save_all=True)` also collects every frame in `im_frames` before encoding. Both options break the streaming requirement.

`GifWriter` writes the GIF89a frame by frame with two public Pillow primitives:

- `GifImagePlugin.getheader()`: header, global palette and NETSCAPE loop;
- `GifImagePlugin.getdata()`: LZW compression of each frame.

The MP4 uses `imageio-ffmpeg` directly, which is `imageio`'s own video backend. It accepts `bytes` without needing `numpy`. The optional dependencies come down to `pillow` and `imageio-ffmpeg` (the `[record]` extra).

### GIF palette and size

**Global palette** of 255 colors plus index 255, reserved for transparency. It is computed once from a sample:

- the first frame with traces;
- that same frame under the veil of the result banner;
- that same frame with the replay marker;
- a strip with every theme color (solid, veiled and as antialiased text).

This way the palette covers colors that have not appeared yet, such as the dead snake or the final veil.

**Quantization method chosen by measurement** on real frames (ticks 0, 1 and 400 and the final frame):

| Method | Max error per channel (0–255) | Pixels with error > 16 at tick 400 |
|---|---:|---:|
| `MEDIANCUT` | 26 – 32 | 0.444% |
| **`MAXCOVERAGE`** (chosen) | **10 – 16** | **0%** |

**No dithering.** On flat graphics, dithering only adds noise and hurts LZW compression.

**Delta frames.** Each frame is compared with the previous one at the palette-index level. Unchanged pixels become the transparent index (*disposal* 1), and the frame is cropped to the rectangle that changed. Identical consecutive frames are merged into one with the summed delay: in the showcase video, 373 logical frames become 315 encoded ones.

**Exact delays.** GIF measures delays in hundredths of a second. They are rounded cumulatively: at 15 fps the frames last 7, 6 and 7 cs, and the average is exact. Browsers force any delay under 2 cs up to 10 cs, which is why the CLI limits the rate to 1–50 fps.

### Full determinism

- The only non-deterministic content of a frame was the milliseconds measured with the real clock. In recordings, the HUD replaces them with `timing: omitted: bit-exact replay`.
- **GIF:** the same seed and agents produce a byte-for-byte identical file. Both runs of the showcase have the same SHA-256, `d48df97599c34bfa…`, and a test checks it at a small scale.
- **MP4:** with `-fflags +bitexact -flags:v +bitexact -map_metadata -1`, two encodings are also byte-for-byte identical (test included).
- `test_same_seed_and_agents_render_identical_frames` compares the SHA-256 of every frame between two recordings.

### Lethal-cut replay (`--highlight-lethal`)

1. On every tick, the recorder checks whether an agent is in `CONSTRICT` with a `DecisionTrace.lethal_cut` and copies that frame into a reserved Surface, one per agent. Memory stays constant.
2. At the end, the match **was decided by a lethal cut** if three conditions hold: the winner had a lethal seal, the loser died against a wall, a body or itself (not in a head-on collision), and it died at most 150 ticks after the seal.
3. In that case, the video freezes the decisive frame for 2.5 s, with rings around the chokepoint and a `REPLAY LETHAL CUT` ribbon showing the AI's `rationale`. It then shows the final result for 1.5 s.
4. Without the flag, the CLI reports that the match ended with a lethal cut and suggests using it.

### Measured results

| Recording | Frames | Duration | GIF | MP4 | Render GIF / MP4 |
|---|---:|---:|---:|---:|---:|
| Showcase (seed 2, with replay) | 373 | 24.9 s | 1.86 MB | 0.89 MB | 5.3 s / 3.4 s |
| Long mirror duel (seed 0, 570 ticks) | 593 | 39.5 s | 3.10 MB | 1.43 MB | 10.5 s / 7.6 s |
| Short match (30 ticks) | 53 | 3.5 s | 0.19 MB | — | 0.7 s / — |

1022×682 resolution at 15 fps, on the same machine as the benchmark (Ryzen 7 5700X, Windows 11).

---

## 6. Trade-offs and design decisions

### 1-tick overlay lag vs input latency

The trace drawn on frame $t$ was computed on state $t-1$: it is the decision that produced the visible state. Showing the decision for the current state would require calling `decide()` right after every tick. For the human, that means reading the keyboard before the player can react to the new state, which adds one tick of latency to their input. The other option, treating the human as a special case, breaks the uniformity of the Strategy pattern.

**Decision:** keep the player's input free of added latency. The A\* path is re-anchored to the current head (`planned_path[0]` is skipped when it matches it), so the lag only shows in the Voronoi partition, one tick behind. At 10 ticks/s that is 100 ms.

### Static lethal cut vs tail chasing

`cut_area` is computed on the cells that are free right now ($\tau = 0$), and the criterion is the one in the specification: space < length. It ignores that the rival's body frees cells as it moves. A snake trapped in a pocket that contains a cycle could survive by chasing its tail even though its space is smaller than its length.

- **Cost of a false positive:** a few ticks in `CONSTRICT` without a kill. The AI takes no risk, because the cut also requires *the AI itself* to have space $\ge L_{AI}$ from the cut point.
- **Discarded alternative:** simulating the pocket with the temporal model for each candidate. It would cost one temporal BFS per articulation point, versus Tarjan's single pass. With a mean budget use of 3 – 5% it would be affordable, so it remains a future improvement.

### Other decisions

| Decision | Alternative | Reason |
|---|---|---|
| Body as an immutable `tuple` (advancing is $O(L)$) | Mutable `deque` ($O(1)$) | Determinism and shared snapshots are worth more. $O(L)$ per tick is negligible next to the AI's ~15 $O(V)$ passes. `deque` is used where it matters: the BFS queue and the input buffer. |
| Deferred growth (as in Battlesnake) | Growing on the same tick the food is eaten | At the start of every tick it is already known which tails will move, regardless of who eats. This is what makes the $\tau(c)$ model possible. |
| Voronoi ties go to the longer snake | Always marking them neutral | It is consistent with the head-on rule: the cell belongs to whoever would win the collision. |
| A\* with $w = 1.25$ | Optimal A\* ($w = 1$) | Fewer expanded nodes in exchange for paths at most 25% longer. A test checks the suboptimality bound $\text{cost} \le w \cdot \text{optimal}$ (with $w = 2$). |
| The engine measures latency, not the agent | Agents report their own time | An agent cannot fake its metrics, and every agent is measured the same way. |
| Iterative Tarjan | Recursive Tarjan | The DFS can be as deep as there are cells; with 925 it brushes against CPython's recursion limit (1,000 by default). |
| GIF streamed with Pillow's `getheader`/`getdata` | `imageio` or `Image.save(save_all=True)` | Both keep every frame until closing. Streaming keeps memory constant (82 MB with either 53 or 593 frames). |
| Global `MAXCOVERAGE` palette without dithering | Per-frame palette or `MEDIANCUT` with dithering | A shared palette enables index-level deltas and transparency; `MAXCOVERAGE` gave the lowest measured maximum error. |
| Latencies hidden in the recording HUD | Showing the real ms | They are the only non-deterministic content of the frame; hiding them makes the video reproducible byte for byte. |
| Replay of the decisive frame at the end | Slowing down the last frames live | While streaming, there is no way to know in advance which seal will be decisive; keeping only that frame costs one Surface. |

### Future work

- Tail chasing along the **longest** path (endgame survival, where the AI's remaining deaths happen).
- Cut analysis with the temporal model (see above).
- Shallow minimax or MCTS lookahead, using the pure `rules.step` as the transition model.

---

## 7. Installation and reproducibility

Requirements: Python ≥ 3.11 (developed and measured with 3.12.10). The only runtime dependency is `pygame-ce` ≥ 2.5. Exporting video requires the `[record]` extra (`pillow` and `imageio-ffmpeg`, which ships an ffmpeg binary). Without it, `snake-arena record` exits with code 2 and prints the install command.

### Virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,record]"
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,record]"
```

Without `record`, the export tests that need Pillow or ffmpeg are reported as skipped (`pytest.importorskip`) instead of failing.

### Verification

```bash
pytest          # 105 tests; the view and the recorder are tested with SDL_VIDEODRIVER=dummy
mypy            # --strict mode over src/ and tests/ (configured in pyproject.toml)
```

| File | Tests | What it covers |
|---|---:|---|
| `test_rules.py` | 16 | Collisions: wall, self, body, head-on, head swap, freed tail, deferred growth, simultaneity |
| `test_flood.py` | 7 | Temporal BFS, detours, path reconstruction, Voronoi (neutral band, length tie-break, late start, blocking bodies) |
| `test_astar.py` | 6 | Optimality, obstacles, telemetry without a path, penalties, temporal goal, weighted A\* bound |
| `test_cli.py` | 11 | `watch` (defaults, mirror duel, pauses outside 1–2 s, rounds ≤ 0, invalid agents), `record` (flags, unknown format, end-to-end GIF, missing dependency with code 2), mirror `bench` |
| `test_record_export.py` | 11 | Format from the extension or forced, missing dependencies with the install command, decodable MP4 with every frame and byte-for-byte identical, odd sizes rejected |
| `test_gif_writer.py` | 8 | Exact pixel round trip, minimal delta regions, merging of identical frames, delays at 15 fps (7/6/7 cs), byte-for-byte identical GIF, palette without spurious colors, mandatory calibration, out-of-range fps |
| `test_recorder.py` | 7 | Mock writer that only stores the SHA-256 of each frame: one RGB frame per tick, final hold, frame-by-frame determinism, overlay presets, lethal-cut replay (with and without the flag), `--max-ticks` |
| `test_ai.py` | 6 | Sealing a lethal cut, refusing a losing head-on collision, no suicides, complete trace, identical Voronoi in the mirror duel, determinism |
| `test_series.py` | 6 | One record per match, pause before restarting, next seed, stop after N rounds, manual restart, live tactic mix without double counting |
| `test_engine.py` | 5 | Reproducibility by seed, injected clock, tick limit, `reset`, benchmark report |
| `test_articulation.py` | 4 | Corridors, open grid, door between rooms, occupied root |
| `test_occupancy.py` | 4 | $\tau(c)$ against `rules.step`, cells threatened by the rival |
| `test_view_smoke.py` | 3 | `play` mode with overlays and pause, 2-round series with automatic restart, focus switch that keeps the Voronoi map |
| `test_snake.py`, `test_grid.py`, `test_human.py`, `test_agents.py` | 11 | Domain model, input buffer, Strategy pattern |

### Headless benchmark

```bash
snake-arena bench --games 20 --seed 0                                # baseline (#1) vs the AI (#2)
snake-arena bench --games 20 --agent-1 aggressive --agent-2 aggressive  # mirror duel
```

The same seed always produces the same wins, deaths and mode mix; only the latencies change.

### Interactive match

```bash
snake-arena play                                   # you (blue) vs the AI (red)
snake-arena play --arena open --size 25 --seed 7
```

### Spectator mode

```bash
snake-arena watch                                              # greedy vs aggressive, endless series
snake-arena watch --agent-1 aggressive --agent-2 aggressive   # mirror duel
snake-arena watch --rounds 10 --delay-restart 2 --tick-rate 20
```

### Headless recording

```bash
snake-arena record --seed 2 --highlight-lethal --output assets/showcase.gif
snake-arena record --seed 2 --highlight-lethal --output assets/showcase.mp4
snake-arena record --format gif --overlays chokepoints --max-ticks 600 --output clips/cuts.bin
```

| Option | Commands | Values | Default |
|---|---|---|---|
| `--agent-1`, `--agent-2` | `watch`, `record`, `bench` | `aggressive`, `greedy` | `greedy`, `aggressive` |
| `--rounds` | `watch` | number of matches ≥ 1 | endless |
| `--delay-restart` | `watch` | pause after a match ends, 1 to 2 s | `1.5` |
| `--output` | `record` | output file (missing directories are created) | required |
| `--format` | `record` | `gif`, `mp4` | from the extension |
| `--max-ticks` | `record` | safety limit on the match length | `1500` |
| `--overlays` | `record` | `all`, `voronoi`, `chokepoints`, `none` | `all` |
| `--highlight-lethal` | `record` | replays the lethal cut if it decided the match | off |
| `--games` | `bench` | number of matches ≥ 1 | `20` |
| `--tick-rate` | `play`, `watch`, `record` | ticks per second; in `record`, the video fps (1–50) | `10` (`play`), `15` (`watch`, `record`) |
| `--cell` | `play`, `watch`, `record` | cell size in pixels | `22` |
| `--arena` | all | `cross`, `open` | `cross` |
| `--size` | all | board side in cells | `31` |
| `--food` | all | food items on the board at the same time | `3` |
| `--seed` | all | food seed (in `watch` and `bench`, the seed of the first round) | `0` |
