"""
Court Module
============
Adversarial courtroom for competitive intelligence.

Components:
- argument_builder: Builds argument banks from research
- advocates: Runs advocate debates (Ollama)
- judge: Deliberates and delivers verdict (Groq)
- verdict: Processes and saves verdicts

All components are now vertical-aware.
"""

from court.argument_builder import build_arguments, build_all_arguments, get_dimensions_for_vertical
from court.judge import deliberate, parse_verdict

__all__ = [
    "build_arguments",
    "build_all_arguments",
    "get_dimensions_for_vertical",
    "deliberate",
    "parse_verdict"
]