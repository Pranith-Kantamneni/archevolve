# ARCHEVOLVE Evaluation Documentation

## Evaluator Overview

Five separate evaluators assess architecture quality across the approved objectives. Each evaluator returns a normalized score (0-100) and a short reasoning string.

## Cost Evaluator

**Score Range**: 0-100 (higher = lower cost)

**Scoring Rules**:
- Each service penalizes 3 points
- Each managed service penalizes 2 points
- Each database penalizes 5 points
- Each cache penalizes 2 points
- Each messaging component penalizes 2 points
- Each gateway penalizes 1 point

**Reasoning Examples**:
- "Uses 3 managed service(s), which adds operational cost but reduces engineering overhead. Has 1 database component(s), which contributes to infrastructure cost."
- "Few services keep infrastructure cost moderate."

## Security Evaluator

**Score Range**: 0-100 (higher = more secure)

**Scoring Rules**:
- Base score: 50
- +20 if authentication mechanism present
- +15 if API gateway present, -5 if absent
- +5 if monolithic (smaller attack surface), +2 if microservices (defense in depth)

**Reasoning Examples**:
- "Monolithic architecture has smaller attack surface. API gateway provides security controls and request filtering. Authentication mechanism present."
- "No API gateway, expanded attack surface. No explicit authentication component."

## Reliability Evaluator

**Score Range**: 0-100 (higher = more reliable)

**Scoring Rules**:
- Base score: 50
- +20 if 3+ instances provide redundancy
- +10 if 2 instances provide some redundancy
- +10 if cache present (reduces database load)
- +10 if messaging present (decouples services, improves fault tolerance)
- +10 if managed database includes reliability features
- -5 if monolithic with no cache (single point of failure risk)

**Reasoning Examples**:
- "3 instances provide redundancy. Cache reduces database load, improving reliability. Managed database includes reliability features."
- "2 instance provides some redundancy."

## Performance Evaluator

**Score Range**: 0-100 (higher = better performance)

**Scoring Rules**:
- Base score: 50
- +25 if cache present (reduces latency)
- +5 if API gateway present (enables routing and optimization)
- +5 if async communication, -3 if sync communication
- -10 if many services (>5) with communication overhead, +2 if distributed with parallelism benefit

**Reasoning Examples**:
- "Cache present, reducing latency for repeated requests. Asynchronous communication improves throughput. API gateway enables request routing and optimization."
- "Synchronous communication used. No cache; performance depends on database latency."

## Scalability Evaluator

**Score Range**: 0-100 (higher = more scalable)

**Scoring Rules**:
- Base score: 50
- +20 if not monolithic (enables horizontal scaling)
- -10 if monolithic (significant scaling limitations)
- +15 if messaging present (supports event-driven scaling)
- +10 if cache present (supports read scalability)
- +5 if managed services can scale automatically

**Reasoning Examples**:
- "Modular architecture enables horizontal scaling. Messaging infrastructure supports event-driven scaling. Cache supports read scalability."
- "Monolithic architecture limits horizontal scaling."