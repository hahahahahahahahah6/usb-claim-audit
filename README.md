# usb-claim-audit

Version 0.1.0. An offline static checker comparing documented wired device
capabilities with provider-resolved discovery calls in Python source.
Audited source is parsed with AST and never executed. No runtime dependencies.
Python 3.9 or newer is required. This machine has only `python3`.

```sh
python3 -m pip install .
usb-claim-audit /path/to/project
python3 -m usb_claim_audit /path/to/project --json
python3 -m usb_claim_audit /path/to/project --verbose --ignore 'docs/archive/*'
python3 -m usb_claim_audit /path/to/project --fail-on MEDIUM
python3 -m usb_claim_audit --version
python3 -m unittest discover
python3 -m build
```

Root README.md and Markdown under any docs path component are scanned.
Fenced blocks are excluded; inline code counts. Paragraph lines are joined,
case is folded, contractions expanded, hyphens replaced with spaces, and
whitespace collapsed. Exact word boundaries apply; longer negative spans are
removed before positive matching. The complete vocabulary follows.

```text
connects to usb devices
connect to usb devices
connects via usb
connect via usb
connects over usb
connect over usb
reads from usb devices
read from usb devices
writes to usb devices
write to usb devices
reads data from usb devices
read data from usb devices
writes data to usb devices
write data to usb devices
transfers files over usb
transfer files over usb
transfers data over usb
transfer data over usb
transfers files via usb
transfer files via usb
detects usb devices
detect usb devices
lists usb devices
list usb devices
finds usb devices
find usb devices
communicates over usb
communicate over usb
communicates via usb
communicate via usb
controls usb devices
control usb devices
supports usb devices
usb device support
usb connectivity
supports usb
usb support
uses usb
use usb
does not connect to usb devices
does not connect via usb
does not connect over usb
does not read from usb devices
does not write to usb devices
does not transfer files over usb
does not transfer data over usb
does not detect usb devices
does not list usb devices
does not communicate over usb
does not communicate via usb
does not support usb devices
does not support usb
does not use usb
usb connectivity not supported
usb not supported
no usb support
without usb support
no usb connectivity
without usb connectivity
no usb
without usb
```

`documented-usb-claim-false` is HIGH without production evidence and MEDIUM
when evidence occurs only in test source. The following rule is HIGH when
production evidence contradicts the documentation:

```text
documented-no-usb-claim-false
```
 Each family
produces at most one finding. Default failure threshold is HIGH; MEDIUM can
be selected. JSON contains verdict, findings (rule, severity, message), and
scanned count. Exit codes are 0 for PASS, 2 for FAIL, and 1 for usage errors.
MEDIUM findings remain visible even when the verdict is PASS.

## Limitations

Only the exact vocabulary in the fenced block constitutes claims. A bare
protocol word, chapter title, dependency name, or instruction asking the user
to attach a cable or plug in a device does not qualify. Charging, serial
ports, printing, and file export descriptions do not qualify either.

Imports, strings, comments, docstrings, unbound transfers, logging functions,
and web route decorators are insufficient. System device listing helpers
launched through subprocess are excluded: shell command names in strings
are not evidence. Discovery through pyusb's core find function counts by
itself, including aliased imports, bound handles, and chained transfers.
This checks source fingerprints, not successful hardware access, permissions,
reachability, or whether a discovery returns a device. Syntax-invalid files
provide no evidence. Dynamic imports and runtime rebinding are not resolved.

Production scanning excludes tests, test-named modules, fixtures, docs,
examples, and symlinks. Test evidence only affects the MEDIUM variant.
Environment files are never opened. A positive claim without source is HIGH;
an absence claim without source is consistent. With no claim, the audit passes
regardless of source evidence. Ignore globs match paths relative to the root.
