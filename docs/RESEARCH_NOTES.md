# Research Notes Informing the Product

The frontend/product direction was chosen after checking adjacent benchmark work rather than assuming the category was empty.

- Zapier AutomationBench evaluates whether AI agents can complete realistic business workflows and uses programmatically verifiable outcomes. This reinforces the principle that benchmark tasks should have deterministic success criteria where possible.
- GoSmarter's material-test-certificate benchmark explicitly compared PaddleOCR + rule-based extraction with LLM extraction and documented when the simple baseline worked and where it broke. This is a concrete precedent for comparing technology classes rather than only comparing model brands.
- PaddleOCR-VL provides a practical open-source document parsing layer for future document benchmarks, so SimplyWins should not rebuild OCR research.

SimplyWins differentiates by making the **technology-selection decision** the product: the recommended method is the minimum-complexity implementation that satisfies explicit operating constraints.
