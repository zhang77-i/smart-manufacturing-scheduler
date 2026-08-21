# Smart Manufacturing Scheduler

A constraint optimization based production scheduling system for intelligent manufacturing.

## Overview

This project focuses on production scheduling problems with:

- Multiple jobs
- Heterogeneous machines
- Process precedence constraints
- Machine capacity constraints
- Delivery deadline requirements

The system combines mathematical optimization and heuristic search to generate feasible and efficient production plans.

## Architecture

```
Production Data
      |
      v
Model Construction
      |
      v
CP-SAT Solver
      |
      v
Schedule Optimization
      |
      v
Evaluation & Visualization
```

## Methods

### Constraint Programming

- OR-Tools CP-SAT
- Interval Variables
- NoOverlap Constraints
- Precedence Constraints

### Optimization Objectives

- Makespan minimization
- Tardiness reduction
- Resource utilization improvement

## Project Structure

```
smart-manufacturing-scheduler
|
├── model
│   ├── variables.py
│   ├── constraints.py
│   └── objective.py
|
├── solver
│   ├── cp_sat_solver.py
│   └── heuristic.py
|
├── benchmark
|
├── visualization
|
└── requirements.txt
```

## Learning Goals

This repository demonstrates the workflow of converting manufacturing requirements into optimization models and solving complex scheduling problems with modern operations research methods.
