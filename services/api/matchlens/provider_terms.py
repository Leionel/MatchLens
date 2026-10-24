"""Provider terms of use, quoted from the upstream agreement.

StatsBomb publishes its open data under a custom "StatsBomb Public Data User
Agreement" (Standard Terms, last updated 8 September 2023) that ships as
``LICENSE.pdf`` in the upstream repository. It is NOT a Creative Commons
licence, and the distinction is load-bearing: the agreement forbids
redistributing the data payload itself while permitting the analysis built on
top of it to be published with attribution.

Key clauses, verbatim:

  1.2.1  "The User may not: edit, distort, distribute, reproduce, sell or in
         any way provide the data to any external or third party;"
  1.2.2  "commercially exploit the data or any analysis derived from the use
         of the Service;"
  1.4    "The User is required to credit any publication of analysis formed
         from StatsBomb Data with the StatsBomb brand logo."
  7      "all data provided through the Service, is the property of StatsBomb.
         The User shall, except as expressly permitted herein, shall not
         modify, translate, transfer, distribute, license, sell or otherwise
         exploit for any purposes whatsoever any data"

Consequently MatchLens keeps every provider payload outside version control:
the raw download lands in an ignored directory, the committed manifest records
only provenance and match metadata, and any published analysis carries the
attribution below.
"""
from __future__ import annotations

STATSBOMB_LICENSE_REF = (
    "StatsBomb Public Data User Agreement (Standard Terms, last updated 8 September 2023) "
    "- https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf"
)

STATSBOMB_ATTRIBUTION_TEXT = (
    "Data provided by StatsBomb. Publications of analysis derived from this data must state "
    "the data source as StatsBomb and display the StatsBomb logo from their Media Pack "
    "(https://statsbomb.com/media-pack/)."
)

STATSBOMB_LOGO_REQUIREMENT = (
    "Visualizations derived from this data must display the StatsBomb logo per the "
    "StatsBomb Public Data User Agreement (clause 1.4)."
)

STATSBOMB_REDISTRIBUTION_RULES: tuple[str, ...] = (
    "Clause 1.2.1 forbids editing, distorting, distributing, reproducing, selling or "
    "otherwise providing the data to any external or third party.",
    "Clause 7 reserves all rights in the data to StatsBomb and forbids modifying, "
    "translating, transferring, distributing, licensing or selling it.",
    "Clause 1.2.2 forbids commercial exploitation of the data or of derived analysis.",
    "Clause 1.4 requires any publication of analysis to credit StatsBomb and display "
    "the StatsBomb brand logo.",
    "MatchLens therefore keeps every provider payload outside version control: raw "
    "downloads land in an ignored directory and only provenance metadata is committed.",
)
