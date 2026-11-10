# Lessons learned

Shared memory for every project and every agent session. Add an entry when something cost real time to figure out:
a quirk, a fix, a working config, or a measurement. Newest first. Be specific: chip, board, IDF version, and what
the symptom looked like, so a future search finds it.

Format: `- **YYYY-MM-DD, <topic>** (<board/project>): symptom → cause → fix.`

---

- **2026-11-10, IDF v6 core dump config** (template): `CONFIG_ESP_COREDUMP_DATA_FORMAT_ELF` no longer exists in v6
  (ELF is the only format). It was silently ignored until `esp.py build`'s config check flagged it. Removed it from
  the template.
