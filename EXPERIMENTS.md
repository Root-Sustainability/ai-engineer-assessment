# Address Similarity Experiments & Rationale

This document outlines the reasoning, experiments, and decisions made while developing the address similarity scoring function for the Root Sustainability assessment.

## 1. Problem Context

The core challenge is to verify if a user-provided address (often messy, incomplete, or in a different language) matches the geocoded result returned by Mapbox. I need a similarity score between `0.0` (no match) and `1.0` (perfect match) to flag potential mismatches for human review.

## 2. Possible Approaches

I considered two main paradigms for solving this: Machine Learning (ML) and Algorithmic/Heuristic.

### A. Machine Learning (ML) Approach
*Using embeddings (e.g., BERT, Sentence-Transformers) or a trained classifier.*

**Pros:**
- **Semantic Understanding**: Can learn that "NY" implies "New York" without explicit rules.
- **Context Awareness**: Can potentially distinguish between "Street" and "Avenue" based on context.
- **Scalability**: Once trained, handles new data patterns without manual rule updates.

**Cons:**
- **Data Requirement**: Requires a large, labeled dataset of matching/non-matching pairs to fine-tune effectively. I only have a small validation set.
- **"Black Box"**: Hard to explain *why* a model gave a score of 0.42. Users might lose trust if they can't see the logic.
- **Latency**: Heavy models are slow to run, especially for bulk uploads without GPU support.
- **Overkill**: For a 3-hour assessment, setting up a training pipeline is inefficient.

### B. Algorithmic / Heuristic Approach
*Using string distance metrics (Levenshtein, Jaccard) and explicit rules.*

**Pros:**
- **Transparent**: I know exactly why a score is low (e.g., "Country mismatch penalty applied").
- **Fast**: Simple string operations are extremely efficient.
- **Deterministic**: Same input always gives same output.
- **Easy to Debug**: I can print intermediate steps to see where the logic fails.

**Cons:**
- **Brittle**: Can fail on unseen patterns if rules aren't comprehensive.
- **Manual Effort**: Requires manually curating lists of aliases (e.g., "Deutschland" -> "Germany").

### Decision
**I chose the Algorithmic Approach.**
Given the constraints (3-hour timeline, need for explainability, small dataset), a robust heuristic system is the most pragmatic choice. It allows me to explicitly encode domain knowledge (like "Different countries = No Match") that an ML model might miss without massive training data.

## 3. The Implementation Strategy

My solution uses a **Multi-Stage Scoring System** with **Penalties**.

### Why multiple algorithms?
Address differences come in various forms. No single metric captures them all:

1.  **Sequence Matcher (Ratcliff/Obershelp)**:
    -   *Good for*: Typos and character-level differences.
    -   *Example*: "Appel" vs "Apple" -> High score.
    -   *Fails on*: Reordering ("123 Main St" vs "Main St 123").

2.  **Token Set Ratio (Jaccard-like)**:
    -   *Good for*: Reordered words.
    -   *Example*: "Berlin, Germany" vs "Germany, Berlin" -> High score (1.0).
    -   *Fails on*: Typos ("Berln" vs "Berlin").

3.  **Substring Match**:
    -   *Good for*: Partial information.
    -   *Example*: "Berlin" vs "Berlin, Germany" -> Useful signal.

**Strategy: `max(seq_score, token_score, substring_score)`**
I take the *maximum* because if *any* of these signals is strong, there is a high probability of a match. I don't want a low sequence score (due to reordering) to drag down a perfect token match.

### Why Penalties?
The "Max" strategy is optimistic—it tries to find a match. However, some differences are "deal-breakers" regardless of textual similarity. I apply multiplicative penalties to enforce these constraints.

1.  **Country Mismatch (0.1x)**:
    -   *Why*: "Paris, Texas" and "Paris, France" are textually similar but geographically distinct.
    -   *Logic*: If the algorithm identifies explicit countries (e.g., "USA" vs "France") and they don't match, the score is crushed.

2.  **Number Mismatch (0.5x)**:
    -   *Why*: "10 Main St" and "20 Main St" are neighbors, not the same place.
    -   *Logic*: If both have numbers but they are disjoint sets, penalize.

3.  **POI Mismatch (0.8x)**:
    -   *Why*: "Shanghai" (City) vs "Port of Shanghai" (Specific Location).
    -   *Logic*: If one contains "Airport/Port" keywords and the other doesn't, reduce confidence.

4.  **Strict Postcode Check (0.5x)**:
    -   *Why*: Postcodes are high-precision identifiers. Mismatch here is a strong negative signal.

## 4. Future Improvements

If I had more time or data, I would:
-   **Use a Geocoding Parser**: Libraries like `libpostal` can parse addresses into components (Street, City, Zip) for component-wise comparison.
-   **Hybrid Approach**: Use a lightweight ML model (like a Gradient Boosted Tree) to learn the optimal *weights* for my heuristic scores instead of hardcoding them.
-   **Expand Alias Lists**: My current country/city list is small. I'd integrate a comprehensive gazetteer.
