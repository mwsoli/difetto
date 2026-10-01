# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Difetto — DFT scan-opt benchmarking against a custom OpenROAD fork

Difetto is a WIP DFT (design-for-test) flow built on LibreLane — a complete rewrite of [Fault](https://github.com/aucohl/fault). See [Readme.md](Readme.md) for the project's own intro and the three-flow architecture diagram (`difetto_simple.svg`). The `librelane.help <Flow|Step>` CLI lists every config variable.

**Goal of the user's current work:** evaluate a custom `Dft::scanOpt` (k-means spatial pre-clustering + per-chain wirelength NN/2-Opt + RestitchChain) implemented in `~/work/my_openroad_fork`, by running difetto's benchmark grid (`bench/benchmark.py`) over the ISCAS-89 designs and comparing strategies (`basic` / `opt` / `skip` / `fault`).

## Layout

- `librelane_plugin_difetto/` — LibreLane plugin (DifettoPNR / DifettoATPG / DifettoTest flows). Custom steps in `steps.py`, Tcl in `scripts/openroad/`.
- `yosys-plugin/` — `difetto.so` (built with `make` inside `nix develop`).
- `test/` — small integration designs (`spm`, `picorv32`, `aes128`, `aes256`, `4bitadder`, `lofty_chess`) for `pytest test/`. **Distinct from `bench/tests/`** which is auto-populated by benchmark.py from ISCAS-89 RTL.
- `bench/` — benchmark harness:
  - `benchmark.py`: curses TUI driving DifettoPNR over `yosys-plugin/test/iscas_89/rtl/*.v`, 4 strategies per design.
  - `collect_results.py`: scrapes `tests/<design>/runs/<strat>/<step-dirs>/state_out.json` into `results.xlsx`.
  - `congestion.py`, `compare_congestion_scores.py`, `get_runtime.py`: helpers.
  - `sky130_fd_sc_hd.yaml`, `gf180mcu_fd_sc_mcu7t5v0.yaml`, `sg13g2_stdcell.yaml`: per-SCL config bundles (clock, area, power-net names) loaded by `benchmark.py` based on `STD_CELL_LIBRARY` env var.
- `build/with_venv/openroad`: wrapper that LibreLane invokes; execs the fork's binary with `PYTHONPATH` set so OpenROAD's embedded python can `import click` etc.
- `tech/<scl>_mapping.json`: scan-cell mappings (one per SCL: sky130, gf180, sg13g2).
- `nix/ord-scan_opt.patch`: difetto's reference OpenROAD patch. **Not used** — the user has their own scanOpt code in their fork; we only ported the patch's `writeToOdb()` / `dbDft::reset()` interface pieces.
- `flake.nix`: dev shell. `nix develop` provides yosys+difetto-plugin, librelane, librelane-plugin-difetto. PDKs are **not** baked in — see PDK section.
- `Makefile`: `make venv` builds a poetry-managed venv at `./venv/` (used by the `volare` PDK install step).

## How to run benchmark.py

```bash
nix develop                                            # in difetto root
export PDK_ROOT=$HOME/.volare                          # required; nix shell does NOT set this
export PATH=$PWD/build/with_venv:$PATH                 # so the fork binary shadows the nix-built openroad
which openroad                                         # confirm it's the wrapper

# memory-safe defaults (16 GB host):
BENCH_CORES=2 python3 bench/benchmark.py               # full grid; lower -> safer
python3 bench/benchmark.py 's27'                       # glob to limit designs

# Then aggregate (substitute sky130_fd_sc_hd or other SCL):
cd bench && python3 collect_results.py tests/sky130_fd_sc_hd/*/
```

`benchmark.py` uses curses — must run from a real terminal. `--overwrite` is hardcoded inside `run_test`, so each invocation regenerates run dirs.

Curses TUI status codes: `N` = not started, `P` = pending/running, `S` = success, `F` = FlowError, `E` = other exception. Errors written to `bench/tests/<scl>/<design>/out_<strat>.log`.

Design exclusions: `s1488` (broken RTL, skipped in `benchmark.py:136`) and all `*a`/`*b` variant files (duplicates, excluded at `benchmark.py:139`).

`collect_results.py` writes `results.xlsx` to the **calling directory** (not `bench/`). Run from `bench/` to keep artifacts co-located with test dirs.

For non-curses single-design debugging: `/tmp/run_one_design.py` (created earlier) drives one `(test, strat)` pair without curses. Useful for testing flow changes quickly. Calls `f.start(to="openroad.stapostpnr")` so it stops at STA-post-PnR (post-detailed-routing).

### Strategies (benchmark.py:56-65)

| strat | RUN_PL_CHAIN | RUN_NL_CHAIN | DFT_SCAN_OPT | what it tests |
|---|---|---|---|---|
| skip | F | F | — | no DFT (baseline; used as the (skip) reference for "Impact" columns in collect_results.py) |
| fault | F | T | — | netlist-order chain via Difetto.TopologicalChain (old Fault-tool style, no placement awareness) |
| basic | T | F | F | placement-aware chain via Difetto.Chain, no scan_opt |
| opt | T | F | T | basic + the user's scanOpt (this is the experimental arm) |

scan_opt fires only when both `RUN_PL_CHAIN=True` and `DFT_SCAN_OPT=True`. It runs **after detailed placement, before CTS** (substitution `("-OpenROAD.CTS", "Difetto.Chain")` in `flows.py:20` puts Difetto.Chain right before CTS; chain.tcl inside that step calls `scan_opt` if `DFT_SCAN_OPT` is set).

### `RUN_DUMP_CONGESTION_HEATMAP`

Currently, `True` in `bench/benchmark.py:91` but `False` in the `DifettoPNR` flow default (`flows.py:46`). The fork was built with `BUILD_GUI=OFF`, so `OpenROAD.DumpCongestionHeatmap` crashes with `[ERROR] This code was compiled with the GUI disabled` if re-enabled. To re-enable, install Qt deps (`sudo dnf install qt5-qtbase-devel qt5-qtcharts-devel`), reconfigure the fork with `-DBUILD_GUI=ON`, rebuild — `congestion.csv` is the artifact that `collect_results.py` looks for.

## Standalone (non-benchmark) flow invocation

For driving the three flows directly on a single design (canonical pattern from [Readme.md](Readme.md)):

```bash
python3 -m librelane ./test/spm/config.yaml --run-tag pnr --flow DifettoPNR --overwrite
python3 -m librelane ./test/spm/config.yaml --run-tag atpg --flow DifettoATPG --overwrite \
  --with-initial-state ./test/spm/runs/pnr/*-difetto-cut/state_out.json
python3 -m librelane ./test/spm/config.yaml --run-tag test --flow DifettoTest --overwrite \
  --with-initial-state ./test/spm/runs/atpg/*-difetto-quaighsim/state_out.json \
  --with-initial-state ./test/spm/runs/pnr/*-difetto-chain/state_out.json
```

Order of `--with-initial-state` flags matters for `DifettoTest`. For non-curses single-design debugging in the bench style, see `/tmp/run_one_design.py`.

## Pytest

`pytest test/` runs LibreLane integration tests (configured in `pyproject.toml`); `pytest -m large` adds the heavy ones (>~5 min). These exercise real designs through the flow — useful for catching plumbing breakage after editing `steps.py` / `flows.py`.

## OpenROAD fork build

Recipe is in user-memory: `project_openroad_fork_build.md`. tl;dr: must use **CMake** (Bazel build at `~/work/install/OpenROAD/bin/openroad` lacks the `-python` CLI flag LibreLane requires for `Odb.SetPowerConnections`). Configure inside `nix develop` with these flags (full list in the memory file):

- `-DBUILD_PYTHON=ON -DBUILD_GUI=OFF -DENABLE_TESTS=OFF -DUSE_SYSTEM_BOOST=ON -DABC_USE_STDINT_H=1`
- `-DLEMON_DIR=/nix/store/.../lemon-graph-1.3.1/share/lemon/cmake`
- `-Dortools_ROOT=$HOME/.local/or-tools` (Fedora-42 prebuilt tarball from Google)
- `-Dabsl_DIR=$HOME/.local/or-tools/lib64/cmake/absl` (must match or-tools' bundled abseil — system absl causes ODR at startup)
- `-DCUDD_LIB=/nix/store/.../cudd-3.0.0/lib/libcudd.a`
- `-DTCL_LIBRARY=/nix/store/.../tcl-8.6.16/lib/libtcl8.6.so` (Fedora 42's TCL 9 has incompatible `Tcl_Size` API)
- `-DTCL_HEADER=/nix/store/.../tcl-8.6.16/include/tcl.h`
- linker flags: `-Wl,-rpath-link=/usr/lib64 -Wl,--copy-dt-needed-entries` (for system Boost transitive deps under nix's binutils)

Binary lands at `~/work/my_openroad_fork/build/bin/openroad`. **Build serially or with `--parallel 2`** on 16 GB hosts — heavy translation units (SWIG bindings, ABC) can hit ~2 GB per `g++`.

### Source patches in the fork (already applied; don't redo)

- `src/dft/include/dft/Dft.hh` — declared `writeToOdb()`, added `scan_chains_` member.
- `src/dft/src/Dft.cpp` — split `executeDftPlan` so it stores chains in `scan_chains_` and calls `writeToOdb()`. **Did NOT touch `scanOpt`** — user's existing implementation (k-means + NN + `RestitchChain`) is intact.
- `src/odb/include/odb/db.h` + `src/odb/src/db/dbDft.cpp` — added `dbDft::reset()` (clears `scan_pins_`, `scan_chains_`, sets `scan_inserted_=false`).
- `src/dft/src/optimizer/CMakeLists.txt` — added `dft_utils_scan_pin_lib` to `target_link_libraries` so `ScanPin.hh` is on include path.
- `src/dft/src/optimizer/Opt.cpp` — DFT message ID 10 → **14** (was duplicating architect/Opt.cpp's 10).
- `src/dft/src/dft.tcl` — line 120's `utl::error DFT 13` → `DFT 17` (was duplicating line 110's 13).

The `scanOpt` member uses `db_dft->getScanChains()` directly (works on odb objects, not `scan_chains_`), so my `writeToOdb` plumbing is independent of their optimizer logic.

## PDK setup (one-time)

Fedora has no nix-baked PDK. Use volare:

```bash
# Outside nix develop:
source ~/work/difetto/venv/bin/activate
pip install volare
volare enable --pdk sky130 8afc8346a57fe1ab7934ba5a6056ea8b43078e71   # LibreLane-pinned hash
deactivate
```

LibreLane's pinned hash: `from librelane.common import get_pdk_hash; get_pdk_hash("sky130")` → `8afc8346…`. PDK lands in `~/.volare/sky130A/`. **Always export `PDK_ROOT=$HOME/.volare` inside the dev shell** — the dev shell does NOT set it.

## `OpenROAD.ReportScanChainWL` step

- reads `cell_sci` from `DFT_JSON_MAPPING` (sky130/sg13g2 = `SCD`, gf180 = `SI`) and passes as `SCAN_IN_PIN_NAME` env var to TCL
- collects all nets connected to those scan-in iterm pins
- calls `report_wire_length -net <list> -detailed_route -file …`
- sums `drt: <net> <wl>` lines, emits metric `dft__scan_chain_routed_wl__um` via `puts "%OL_METRIC_F …"`
- runs **after** `OpenROAD.DetailedRouting` (`flows.py:26`)

## collect_results.py — what it now reads

- `tests/<scl>/<design>/runs/<strat>/*-difetto-synthesis/state_out.json` → cell count
- `tests/<scl>/<design>/runs/<strat>/*-difetto-chain/<DESIGN>.chain.yml` → scannable element count (only for opt strategy; sums `insts` across all chains/partitions/scan_lists, not just chain_0)
- `tests/<scl>/<design>/runs/<strat>/*-openroad-detailedrouting/state_out.json` + `config.json` → `design__instance__area__stdcell` (Instance Area), routing-thread config
- `tests/<scl>/<design>/runs/<strat>/*-openroad-stapostpnr/state_out.json` (optional) → `timing__setup__wns` (Worst Slack), `timing__setup__tns` (Total Negative Slack), `power__total` (Power Total)
- `tests/<scl>/<design>/runs/<strat>/*-openroad-detailedrouting/openroad-detailedrouting.log` → routing time (regex `elapsed time = ([\d:]+)`)
- `tests/<scl>/<design>/runs/<strat>/*-openroad-dumpcongestionheatmap/congestion.csv` (optional, falls back to old `*-openroad-dumpheatmaps` step name) → congestion score
- `tests/<scl>/<design>/runs/<strat>/*-openroad-reportscanchainwl/state_out.json` (optional) → `dft__scan_chain_routed_wl__um` metric

Metrics block: Worst Slack, Total Negative Slack, Routing Time, Congestion Score, Scan Chain Routed WL, Instance Area, Power Total — each gets a 4-column block (skip/fault/basic/opt) plus a single `Impact (opt vs basic)` column, i.e. `(opt-basic)/basic`.

**TWL columns deliberately removed** — the user's scanOpt does not emit `dft__chain_twl_internal__init__chain:*` / `…__post_opt__chain:*` / `dft__chain_twl__init__chain:*` / `…__post_opt__chain:*` metrics. If they decide to add those, the difetto reference patch (`nix/ord-scan_opt.patch`) shows the `logger_->metric(fmt::format("dft__chain_twl_internal__init__chain:{}", chain->getName()), twl_internal)` style around the 2-Opt loop in scanOpt.

## Gotcha: untracked plugin assets are invisible to nix develop

The flake builds `librelane-plugin-difetto` from `src = self`. With a git working tree as a flake input, Nix copies **only `git ls-files`-tracked content** into the store source — so any **untracked** non-Python asset (e.g. a new `.tcl` under `librelane_plugin_difetto/scripts/`) gets silently dropped from the rebuilt package, while modifications to *already-tracked* `steps.py` / `flows.py` are picked up. Symptom: a new step's class loads fine but `OpenROADStep.get_script_path()` resolves to a nix-store path missing the file (`[STA-0340] cannot open '/nix/store/.../report_scan_wl.tcl'`). Fix: `git add` the new file (no need to commit), then exit and re-enter `nix develop`.

## Don't touch

- The user's `scanOpt` / chain-optimizer logic in `~/work/my_openroad_fork/src/dft/src/Dft.cpp` (and `optimizer/`, `architect/Opt.cpp`). Explicit "no chain optimizer logic changes" from the user. Pure interface plumbing (writeToOdb, dbDft::reset, message-ID renumbering, CMake link deps) is fine.
