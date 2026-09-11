# Native GB28181 service dependencies

The executable statically links reSIProcate's resip/rutil libraries and bundled ares DNS code. cpp-httplib and nlohmann/json are used through their headers. Full upstream license files are copied into the build's `licenses` directory and included in the Windows package.

| Dependency | Pinned revision | Source |
| --- | --- | --- |
| reSIProcate | 1.14.0, `632e215c2ca9aee5416bfe1808851ea6fa380044` | https://github.com/resiprocate/resiprocate |
| nlohmann/json | 3.11.3 | https://github.com/nlohmann/json |
| cpp-httplib | 0.18.6 | https://github.com/yhirose/cpp-httplib |

Archive SHA-256 checksums are enforced by CMake. The TURN, recon/media, SIP proxy and database applications in the reSIProcate repository are not linked into this executable.

Bundled ares includes code with the following notice (see `rutil/dns/ares` in reSIProcate):

Copyright 1998 by the Massachusetts Institute of Technology.

Permission to use, copy, modify, and distribute this software and its documentation for any purpose and without fee is hereby granted, provided that the above copyright notice appear in all copies and that both that copyright notice and this permission notice appear in supporting documentation, and that the name of M.I.T. not be used in advertising or publicity pertaining to distribution of the software without specific, written prior permission. M.I.T. makes no representations about the suitability of this software for any purpose. It is provided "as is" without express or implied warranty.
