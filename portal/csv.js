/* Spreadsheet export only; the original proof bundle remains authoritative. */
(() => {
  const fields = [
    "schema_version", "device_id", "sequence", "uptime_ms",
    "temperature_milli_c", "temperature_c", "simulated", "boot_id",
    "reset_reason", "tamper_open", "received_at_utc",
  ];

  function cell(value) {
    let text = value == null ? "" : String(value);
    // Quote CSV delimiters and prevent text from becoming a spreadsheet formula.
    // Numeric negative temperatures remain numbers.
    if (typeof value === "string" && /^[\s]*[=+\-@]/.test(text)) text = `'${text}`;
    return `"${text.replaceAll('"', '""')}"`;
  }

  function serializeBatch(batch) {
    const rows = [["batch_id", ...fields]];
    for (const reading of batch.readings || []) {
      rows.push([batch.batch_id, ...fields.map((field) => reading[field])]);
    }
    return "\uFEFF" + rows.map((row) => row.map(cell).join(",")).join("\r\n") + "\r\n";
  }

  globalThis.RialoCsv = { serializeBatch };
})();
