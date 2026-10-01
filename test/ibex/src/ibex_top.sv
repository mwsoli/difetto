// SPDX-License-Identifier: Apache-2.0
// Thin wrapper: instantiates ibex_core and adds dummy scan-enable/in/out
// ports so difetto's chain-insertion step has real top-level ports to
// hook into, matching the convention of test/spm/src/spm.v and the
// ISCAS-89 benchmark netlists (see bench/benchmark.py). These ports are
// intentionally left unconnected inside this module.
module ibex_top (
    input  logic        clk_i,
    input  logic        rst_ni,

    input  logic        test_en_i,

    input  logic [31:0] hart_id_i,
    input  logic [31:0] boot_addr_i,

    output logic        instr_req_o,
    input  logic        instr_gnt_i,
    input  logic        instr_rvalid_i,
    output logic [31:0] instr_addr_o,
    input  logic [31:0] instr_rdata_i,
    input  logic        instr_err_i,

    output logic        data_req_o,
    input  logic        data_gnt_i,
    input  logic        data_rvalid_i,
    output logic        data_we_o,
    output logic [3:0]  data_be_o,
    output logic [31:0] data_addr_o,
    output logic [31:0] data_wdata_o,
    input  logic [31:0] data_rdata_i,
    input  logic        data_err_i,

    input  logic        irq_software_i,
    input  logic        irq_timer_i,
    input  logic        irq_external_i,
    input  logic [14:0] irq_fast_i,
    input  logic        irq_nm_i,

    input  logic        debug_req_i,

    input  logic        fetch_enable_i,
    output logic        alert_minor_o,
    output logic        alert_major_o,
    output logic        core_sleep_o,

    // Dummy DFT scan ports (unconnected; difetto's Difetto.Chain step
    // hooks the inserted scan chain to top-level ports named by
    // DFT_SCAN_ENABLE_PATTERN/DFT_SCAN_IN_PATTERN/DFT_SCAN_OUT_PATTERN)
    input  logic        sce,
    input  logic        sci,
    output logic        sco
);

  ibex_core ibex_core_i (
      .clk_i           (clk_i),
      .rst_ni          (rst_ni),
      .test_en_i       (test_en_i),
      .hart_id_i       (hart_id_i),
      .boot_addr_i     (boot_addr_i),
      .instr_req_o     (instr_req_o),
      .instr_gnt_i     (instr_gnt_i),
      .instr_rvalid_i  (instr_rvalid_i),
      .instr_addr_o    (instr_addr_o),
      .instr_rdata_i   (instr_rdata_i),
      .instr_err_i     (instr_err_i),
      .data_req_o      (data_req_o),
      .data_gnt_i      (data_gnt_i),
      .data_rvalid_i   (data_rvalid_i),
      .data_we_o       (data_we_o),
      .data_be_o       (data_be_o),
      .data_addr_o     (data_addr_o),
      .data_wdata_o    (data_wdata_o),
      .data_rdata_i    (data_rdata_i),
      .data_err_i      (data_err_i),
      .irq_software_i  (irq_software_i),
      .irq_timer_i     (irq_timer_i),
      .irq_external_i  (irq_external_i),
      .irq_fast_i      (irq_fast_i),
      .irq_nm_i        (irq_nm_i),
      .debug_req_i     (debug_req_i),
      .fetch_enable_i  (fetch_enable_i),
      .alert_minor_o   (alert_minor_o),
      .alert_major_o   (alert_major_o),
      .core_sleep_o    (core_sleep_o)
  );

endmodule
