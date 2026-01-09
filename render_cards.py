#!/usr/bin/env python3
"""Compatibility CLI shim — delegates to the refactored package modules.

This file preserves the original command-line interface while the
implementation lives in `deck_pdf_generator` package modules.
"""

from __future__ import annotations

import os
import glob
import argparse
import logging
from typing import List, Optional
from collections import Counter
from prettytable import PrettyTable

from deck_pdf_generator import config, fonts, parser, render


def validate_xml(xml_path: str, xsd_path: str) -> None:
    """Validate `xml_path` against XSD at `xsd_path` if lxml is available.

    This is a light-weight helper kept here for backward compatibility.
    """
    try:
        from lxml import etree as LET  # type: ignore
    except Exception:
        logging.warning("lxml not available; skipping XSD validation for %s", xml_path)
        return

    try:
        schema_doc = LET.parse(xsd_path)
        schema = LET.XMLSchema(schema_doc)
        doc = LET.parse(xml_path)
        if not schema.validate(doc):
            raise RuntimeError(f"XML {xml_path} failed XSD validation against {xsd_path}")
    except Exception as e:
        raise


def main() -> None:
    parser_arg = argparse.ArgumentParser(description="Render Gnarl cards from XML to PDF")
    parser_arg.add_argument("-i", "--input", default="cards.xml",
                            help="Input XML file or directory containing *.xml files")
    parser_arg.add_argument("-x", "--xsd", default=None,
                            help="Optional XSD file to validate XML against (if omitted, looks for cards.xsd)")
    parser_arg.add_argument("--color", dest="color", action="store_true", default=False,
                            help="Render in color (default: black & white)")
    parser_arg.add_argument("-o", "--outdir", default=os.path.join("out"),
                            help="Output directory for generated PDFs")
    parser_arg.add_argument("--check-icons", dest="check_icons", action="store_true", default=False,
                            help="Check whether configured icon glyphs are present in the font and print a log")

    args = parser_arg.parse_args()

    inpath = args.input
    xsd_path = args.xsd or ("cards.xsd" if os.path.exists("cards.xsd") else None)
    use_color = args.color

    if args.check_icons:
        fonts.check_icon_glyphs()
        return

    # Collect xml files
    xml_files: List[str] = []
    if os.path.isdir(inpath):
        xml_files = sorted(glob.glob(os.path.join(inpath, "*.xml")))
        if not xml_files:
            raise RuntimeError(f"No .xml files found in directory: {inpath}")
    elif os.path.isfile(inpath):
        xml_files = [inpath]
    else:
        raise RuntimeError(f"Input path not found: {inpath}")

    os.makedirs(args.outdir, exist_ok=True)

    overall_counts: Counter = Counter()
    for xml_path in xml_files:
        if xsd_path and os.path.exists(xsd_path):
            validate_xml(xml_path, xsd_path)
            logging.info(f"XML {xml_path} validated against {xsd_path}")

        cards = parser.parse_cards(xml_path)
        if not cards:
            logging.info(f"No cards found in {xml_path}, skipping")
            continue

        # accumulate counts per deck for global statistics
        deck_names = [(getattr(c, 'deck', None) or 'loot') for c in cards]
        counts = Counter(deck_names)
        overall_counts.update(counts)

        base = os.path.splitext(os.path.basename(xml_path))[0]
        out_pdf = os.path.join(args.outdir, f"{base}_gnarl_cards.pdf")
        render.render_pdf(cards, out_pdf, color=use_color)
        logging.info(f"OK: Rendered {len(cards)} cards to {out_pdf}")

    # After processing all files, print aggregated statistics
    pt = PrettyTable(["Balíček", "Počet"])
    for name, cnt in sorted(overall_counts.items()):
        pt.add_row([name, cnt])
    print("\nSouhrnná statistika karet:")
    print(pt)
    print(f"Celkem: {sum(overall_counts.values())}")


if __name__ == "__main__":
    main()
