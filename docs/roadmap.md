# CNC Assistant — Roadmap 🧠🏭

This document describes how CNC Assistant evolves
from a rule-based assistant into a full CNC-specific AI model.

The goal is not to replace machinists,
but to capture and scale their experience.

---

## 🎯 Vision

CNC Assistant should behave like:
> an experienced CNC operator standing next to you,
> reasoning, explaining decisions, and learning from your corrections.

---

## 🧩 Core Principles

- Context first (never ask twice)
- Assumptions before questions
- Explanation over calculation
- Feedback is more valuable than accuracy
- LLM is a tool, not the core

---

## 🟢 Phase 1 — AI-like Rule-Based Assistant (Current)

**Status: IN PROGRESS**

### Goals
- Look and feel like an AI without LLM
- Collect high-quality real CNC dialogs
- Build operator trust

### Features
- [x] Persistent per-user context
- [x] FSM-driven dialog logic
- [x] Assumptions engine
- [x] Rule-based cutting modes
- [x] Human-readable explanations
- [x] Feedback collection (👍 / ❌ / corrections)

### Output
- Stable assistant behavior
- Dialog + correction dataset
- First real operator feedback

---

## 🟡 Phase 2 — Learning from Corrections (No LLM)

**Status: Planned**

### Goals
- Improve rules automatically
- Rank recommendations by real usage
- Reduce operator corrections over time

### Features
- [ ] Correction frequency analysis
- [ ] Rule confidence scoring
- [ ] Personalized preferences per operator
- [ ] Adaptive defaults (per material / machine)
- [ ] Operator skill profiling

### Output
- Smarter rule engine
- Data-driven tuning
- Personalized behavior

---

## 🟠 Phase 3 — Hybrid AI (Rules + Small LLM)

**Status: Planned**

### Goals
- Natural language understanding
- Better intent recognition
- Keep deterministic safety

### Features
- [ ] Small open-source LLM (7B–13B)
- [ ] LLM for intent + explanation
- [ ] Rules for final numbers
- [ ] Retrieval from real dialogs
- [ ] Confidence-aware fallback to rules

### Output
- Natural conversation
- Explainable recommendations
- Safe industrial behavior

---

## 🔴 Phase 4 — CNC-Specific LLM

**Status: Future**

### Goals
- Train a CNC-domain AI model
- Encode real operator experience
- Replace static rule tables

### Dataset
- Real dialogs (`dialogs.jsonl`)
- Operator corrections (`corrections.jsonl`)
- Machine + tool metadata

### Features
- [ ] Fine-tuned CNC LLM
- [ ] Chain-of-thought style reasoning
- [ ] Multi-language support (EN / RU / CN)
- [ ] Machine-aware recommendations
- [ ] Continual learning loop

### Output
- CNC-native AI
- Domain expertise at scale

---

## 🌍 Multi-Language Strategy

- Phase 1: Rule-based output templates
- Phase 2: Localized explanations
- Phase 3: LLM-based translation
- Phase 4: Native multilingual reasoning

Languages:
- English
- Russian
- Chinese

---

## 📊 Success Metrics

| Metric | Target |
|------|-------|
| Context re-ask rate | < 5% |
| Operator corrections | ↓ over time |
| Reuse by same users | ↑ |
| Trust feedback | High |
| Dataset size | 50k+ dialogs |

---

## ⚠️ Safety & Responsibility

CNC Assistant:
- does not execute G-code
- does not control machines
- always explains assumptions
- requires human validation

---

## 🧠 Philosophy

> First, collect experience.  
> Then, structure it.  
> Only then, train intelligence.

---

