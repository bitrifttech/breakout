# /world Directory

This directory contains seed data for the AI Discovery experiment. It is mounted read-only into the agent container at `/world`.

## Purpose
- Provide initial data for the agent to explore and discover.
- Encourage building reusable tools and documenting findings in artifacts like `MAP.md`, `LOG.md`, `TOOLS.md`, and `PLAN.md`.

## Contents
- `data.csv`: A small CSV file with sample data (id, value, tag).
- `puzzles/hidden.txt`: A hint for further exploration.

## Hints
- Start by listing and examining the files here.
- Look for patterns or clues that might lead to building tools (e.g., for parsing CSV data efficiently).
