#!/usr/bin/env bash

rm -rf "$HOME/.agents/skills/review-loop"
mkdir -p "$HOME/.agents/skills" && cp -a -- ./review-loop "$HOME/.agents/skills/"
