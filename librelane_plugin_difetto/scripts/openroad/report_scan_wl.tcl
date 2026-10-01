source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
read_current_odb

puts "=== Total routed wirelength calculation is enabled ==="

# Collect all nets connected to scan-in cell pins — one net per scan chain edge.
# Nets are gathered as odb dbNet objects (not name strings): scan/boundary-scan
# nets end up with hierarchical, escaped-bracket names (e.g.
# 'boot_addr_i.ibsr/rising.bits\[10\]._store_') that OpenSTA's get_nets --
# used internally by `report_wire_length -net` -- fails to resolve, silently
# dropping those nets from the sum. report_net_wire_length takes a dbNet
# object directly, sidestepping that name round-trip entirely.
set block [ord::get_db_block]
set scan_nets {}
set seen_nets {}
foreach inst [$block getInsts] {
  foreach iterm [$inst getITerms] {
    if { [[$iterm getMTerm] getName] eq $::env(SCAN_IN_PIN_NAME) } {
      set net [$iterm getNet]
      if { $net ne "NULL" && ![dict exists $seen_nets $net] } {
        dict set seen_nets $net 1
        lappend scan_nets $net
      }
    }
  }
}

set scan_wl_file $::env(STEP_DIR)/scan_chain_wl.rpt
grt::create_wl_report_file $scan_wl_file 0
foreach net $scan_nets {
  grt::report_net_wire_length $net 0 1 0 $scan_wl_file
}

set scan_total 0.0
set fp [open $scan_wl_file r]
while { [gets $fp line] >= 0 } {
  if { [regexp {^drt: \S+ ([0-9.]+)} $line -> wl] } {
    set scan_total [expr {$scan_total + $wl}]
  }
}
close $fp
puts "=== Scan chain nets ([llength $scan_nets] nets) routed wirelength: ${scan_total} um ==="
puts "%OL_METRIC_F dft__scan_chain_routed_wl__um $scan_total"
