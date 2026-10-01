# SPDX-License-Identifier: Unlicense
# Copyright (c) 2025 Mohamed Gaber
import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell
import re
import sys
import json
import yaml
from pathlib import Path
from congestion import get_congestion_scores

__file_dir__ = Path(__file__).parent

workbook = xlsxwriter.Workbook("results.xlsx")
worksheet = workbook.add_worksheet()

cols = [
    "Design",
    "Standard Cell Library",
    "Cell Count",
    "Scannable Elements",
    "Scannable Element Ratio",
]
for metric in [
    "Worst Slack",
    "Total Negative Slack",
    "Routing Time",
    "Congestion Score",
    "Scan Chain Routed WL",
    "Instance Area",
    "Power Total",
]:
    for strat in ["skip", "fault", "basic", "opt"]:
        cols.append(f"{metric} ({strat})")
    cols.append(f"{metric} Impact (opt vs basic)")
cols.append("Routing Threads")

col_by_name = {el: i for i, el in enumerate(cols)}

for el, i in col_by_name.items():
    worksheet.write(0, i, el)

row = 0


def get_elapsed_drt_time(path):
    rx = re.compile(r"elapsed time = ([\d:]+)")
    last = None
    for line in open(path):
        res = rx.search(line)
        if res is None:
            continue
        last = res[1]
    return last


def w(name, data, format=None):
    global row
    global worksheet
    global col_by_name
    worksheet.write(row, col_by_name[name], data, format)


def wf(name, data, format=None):
    global row
    global worksheet
    global col_by_name
    worksheet.write_formula(row, col_by_name[name], data, format)



percent_format = workbook.add_format({"num_format": "0.00%"})

for design_dir_raw in sys.argv[1:]:
    design_dir = Path(design_dir_raw)
    if not design_dir.is_dir():
        print(f"{design_dir} is not a valid directory", file=sys.stderr)
        exit(1)
    test_name = design_dir.stem
    final_dirs = list(design_dir.glob("runs/*/final"))
    if len(final_dirs) < 4:
        print(f"{test_name} may not be done.", file=sys.stderr)
    print(f"Processing {test_name}…", file=sys.stderr)
    row += 1
    for final_dir in sorted(final_dirs):
        strat = final_dir.parent.stem.removeprefix("benchmark_")  # older benchmarks
        if strat == "synth":
            # reusable synth dir, ignore
            continue
        try:
            synth_dir = next(final_dir.parent.glob("*-difetto-synthesis"))
        except:
            synth_run = final_dir.parents[1] / "synth"
            synth_dir = next(synth_run.glob("*-difetto-synthesis"))
        drt_dir = next(final_dir.parent.glob("*-openroad-detailedrouting"))
        sta_dir = next(final_dir.parent.glob("*-openroad-stapostpnr"), None)
        heatmap_dir = next(
            final_dir.parent.glob("*-openroad-dumpcongestionheatmap"),
            None,
        ) or next(
            final_dir.parent.glob("*-openroad-dumpheatmaps"),  # old step
            None,
        )
        with open(synth_dir / "state_out.json") as f:
            synth_metrics = json.load(f)["metrics"]
        with open(drt_dir / "state_out.json") as f:
            drt_metrics = json.load(f)["metrics"]
        with open(drt_dir / "config.json") as f:
            drt_conf = json.load(f)
        w("Design", test_name)
        if strat == "opt":
            dft_dir = next(final_dir.parent.glob("*-difetto-chain"))
            w("Standard Cell Library", drt_conf["STD_CELL_LIBRARY"])
            w("Cell Count", synth_metrics["design__instance__count"])
            w(
                "Scannable Elements",
                sum(
                    len(sl["insts"])
                    for chain in yaml.safe_load(next(dft_dir.glob("*.chain.yml")).read_text())
                    for part in chain["partitions"]
                    for sl in part["scan_lists"]
                ),
            )
            cells_ref = xl_rowcol_to_cell(row, col_by_name["Cell Count"])
            scannable_ref = xl_rowcol_to_cell(row, col_by_name["Scannable Elements"])
            wf("Scannable Element Ratio", f"={scannable_ref}/{cells_ref}")
            w("Routing Threads", drt_conf["DRT_THREADS"])
        w(
            f"Instance Area ({strat})",
            drt_metrics.get("design__instance__area__stdcell"),
        )
        if sta_dir is not None and (sta_dir / "state_out.json").exists():
            with open(sta_dir / "state_out.json") as f:
                sta_metrics = json.load(f)["metrics"]
            w(f"Worst Slack ({strat})", sta_metrics.get("timing__setup__wns"))
            w(f"Total Negative Slack ({strat})", sta_metrics.get("timing__setup__tns"))
            w(f"Power Total ({strat})", sta_metrics.get("power__total"))
        w(
            f"Routing Time ({strat})",
            get_elapsed_drt_time(drt_dir / "openroad-detailedrouting.log"),
        )
        if heatmap_dir is not None and (heatmap_dir / "congestion.csv").exists():
            _, _, congestion_score = get_congestion_scores(
                heatmap_dir / "congestion.csv"
            )
            w(f"Congestion Score ({strat})", congestion_score)
        scan_wl_dir = next(
            final_dir.parent.glob("*-openroad-reportscanchainwl"), None
        )
        if scan_wl_dir is not None and (scan_wl_dir / "state_out.json").exists():
            with open(scan_wl_dir / "state_out.json") as f:
                scan_wl_metrics = json.load(f)["metrics"]
            if "dft__scan_chain_routed_wl__um" in scan_wl_metrics:
                w(
                    f"Scan Chain Routed WL ({strat})",
                    scan_wl_metrics["dft__scan_chain_routed_wl__um"],
                )

first_se_ratio = xl_rowcol_to_cell(1, col_by_name["Scannable Element Ratio"])
last_se_ratio = xl_rowcol_to_cell(row, col_by_name["Scannable Element Ratio"])
for metric in [
    "Worst Slack",
    "Total Negative Slack",
    "Routing Time",
    "Congestion Score",
    "Scan Chain Routed WL",
    "Instance Area",
    "Power Total",
]:
    base = f"{metric} (basic)"
    ref = f"{metric} (opt)"
    calculated = f"{metric} Impact (opt vs basic)"
    first = xl_rowcol_to_cell(1, col_by_name[calculated])
    for i in range(1, row + 1):
        base_cell = xl_rowcol_to_cell(i, col_by_name[base])
        strat_cell = xl_rowcol_to_cell(i, col_by_name[ref])
        impact_cell = xl_rowcol_to_cell(i, col_by_name[calculated])
        worksheet.write_formula(
            impact_cell,
            f'=IF({base_cell}=0, "", ({strat_cell}-{base_cell})/{base_cell})',
            percent_format,
        )
    last = xl_rowcol_to_cell(row, col_by_name[calculated])
    avg_cell = xl_rowcol_to_cell(row + 1, col_by_name[calculated])
    worksheet.write_formula(avg_cell, f"=AVERAGE({first}:{last})", percent_format)
    median_cell = xl_rowcol_to_cell(row + 2, col_by_name[calculated])
    worksheet.write_formula(median_cell, f"=MEDIAN({first}:{last})", percent_format)
    stdev_cell = xl_rowcol_to_cell(row + 3, col_by_name[calculated])
    worksheet.write_formula(stdev_cell, f"=STDEV({first}:{last})", percent_format)
    correlate_cell = xl_rowcol_to_cell(row + 4, col_by_name[calculated])
    worksheet.write_formula(
        correlate_cell, f"=CORREL({first}:{last},{first_se_ratio}:{last_se_ratio})"
    )  # r, not %

workbook.close()

print("Done", file=sys.stderr)
