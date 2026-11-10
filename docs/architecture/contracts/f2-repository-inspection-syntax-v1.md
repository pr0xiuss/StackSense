# F2 — Repository Inspection and Syntax Evidence Contract v1.0.0

Status: **FROZEN / IMPLEMENTED**
Owner: Phase 3 Module 2 (Repository Inspection & Language Analysis)  
Consumer: Phase 3 Module 3 (Intermediate Representation & Semantic Analysis)  
Version: `1.0.0`  
Last Updated: 2026-11-06

---

## 1. Scope & Ownership

This contract establishes the normative boundary between Phase 3 Module 2 (M2) and Module 3 (M3).

1. **M2 Ownership:** M2 consumes the frozen `AnalysisInput` (F1 v1.0.0), performs file discovery and inventory classification, detects languages/runtimes/frameworks, parses source code using sandboxed parsers, extracts syntax facts and framework evidence, and produces the immutable `RepositoryInspectionResult` (F2 v1.0.0).
2. **M3 Ownership:** M3 consumes the supplied `RepositoryInspectionResult` as an immutable input. M3 normalizes syntax and framework facts into language-neutral Intermediate Representation (`IRDocument`) and performs semantic resolution.
3. **No Direct Execution:** M3 never invokes M2 directly and does not reconstruct F2. M1 orchestration supplies the immutable F2 instance in an attempt-scoped execution handoff.
4. **Boundary Restrictions:** F2 contains no raw AST/CST nodes, no source bytes, no storage keys, no absolute filesystem paths, no secrets, no cross-file resolved relationships, and no Architecture Model entities.

---

## 2. Invariants & Guarantees

### 2.1 Role vs. Outcome Separation

Every artifact from `AnalysisInput.artifact_catalog` appears exactly once in `RepositoryInspectionResult.inventory`.
M2 enforces a strict separation between **analysis role** (intended pipeline participation) and **processing outcome** (what actually occurred during execution).

- **`ArtifactAnalysisRole`:**
  - `semantic`: eligible for source code syntax extraction and semantic analysis.
  - `configuration`: eligible for structured configuration/manifest extraction.
  - `documentation`: documentation or human-readable text (metadata only).
  - `metadata_only`: preserved in inventory for statistics, but content is not parsed.
  - `ignored`: excluded by policy, ignore rules, or build/cache conventions.
  - `unsupported`: recognized file type or language not supported by Phase 3 analyzers.
  *(Invariant: `failed` is NEVER a role; attempting to use `failed` as an analysis role is rejected with an integrity error).*

- **`ArtifactProcessingOutcome`:**
  - `not_processed`: artifact has not yet been processed by the pipeline.
  - `analyzed`: successfully parsed and analyzed without errors.
  - `analyzed_with_warnings`: analyzed, but non-fatal warnings or minor syntax issues were encountered.
  - `excluded`: skipped due to exclusion rules, size bounds, or policy.
  - `unsupported`: skipped because the language or file type is unsupported.
  - `failed`: processing failed due to read error, decode error, parser crash, timeout, or cap violation.

### 2.2 Sensitive Content Policy & Allowlisted Literals

1. **Classification from Metadata Only:** Sensitive classification is performed strictly from path and metadata signals (filename, extension, path patterns). Artifacts classified as environment secrets (`.env`), private keys (`.pem`, `.key`), credentials (`credentials.json`), or tokens are assigned `metadata_only` or `ignored`, and their content is **never read or opened**.
2. **No Unallowlisted Literals:** Permitted source and configuration files may be parsed for structural facts. However, extracted facts may retain only allowlisted structural literals (e.g., module specifiers, dependency package names, declared versions, decorator names, HTTP route templates, HTTP methods). F2 facts never expose arbitrary string literals, environment values, passwords, connection strings, or secret values.
3. **Diagnostics:** Diagnostics describe reasons, rules, and locations; they never include secret values or credentials.

### 2.3 Canonical UTF-8 Source Range Coordinates

All source ranges across all parser adapters use a single unified coordinate space:
1. **Canonical Buffer:** The source bytes are decoded and re-encoded into canonical UTF-8.
2. **Byte Offsets:** `start_byte` and `end_byte` are zero-based, end-exclusive byte offsets into the canonical UTF-8 buffer (`0 <= start_byte <= end_byte`).
3. **Line Numbers:** `start_line` and `end_line` are 1-based line numbers (`1 <= start_line <= end_line`).
4. **Column Offsets:** `start_column` and `end_column` are 0-based UTF-8 byte offsets within the respective line.
5. **Encoding Metadata:** The original source encoding (`utf-8`, `ascii`, or PEP 263 detected encoding) is preserved in `SourceEncodingMetadata`.
6. **BOM Exclusion:** Any UTF-8 Byte Order Mark (`\xef\xbb\xbf`) is stripped from canonical coordinates so offsets align with parsed text.
7. **Newline Preservation:** Newlines (both LF and CRLF) are preserved exactly as present in source to maintain byte offset integrity.
8. **Strict Decoding:** Decoding failures result in an explicit `failed` outcome and a shared `AnalysisDiagnostic`; lossy replacement (`replace`) is strictly prohibited.

---

## 3. Schema Specification

### 3.1 Source Range & Metadata

```python
@dataclass(frozen=True)
class SourceRange:
    start_byte: int      # 0-based, end-exclusive
    end_byte: int        # 0-based, end-exclusive
    start_line: int      # 1-based
    end_line: int        # 1-based
    start_column: int    # 0-based UTF-8 byte column
    end_column: int      # 0-based UTF-8 byte column

@dataclass(frozen=True)
class SourceEncodingMetadata:
    detected_encoding: str
    has_bom: bool
    line_count: int
    byte_count: int
    is_utf8_clean: bool
```

### 3.2 Tagged Syntax Facts

All syntax facts inherit a common structure and provide a deterministic `fact_key`.

1. **`DeclarationFact`:**
   - `kind`: `module`, `package`, `class`, `function`, `method`, `interface`, `type_alias`, `variable`, `react_component`
   - `name`: declared identifier
   - `qualified_name`: dot-separated or container-qualified identifier if determinable locally
   - `container_key`: parent declaration's `fact_key` if nested
   - `modifiers`: e.g. `async`, `export`, `static`, `abstract`
   - `decorators`: tuple of decorator names
   - `signature_text`: safely bounded parameter/return type signature
   - `declaration_range`: outer range of the entire declaration
   - `name_range`: range of the identifier name

2. **`ImportFact`:**
   - `kind`: `module`, `named`, `default`, `all`, `side_effect`
   - `source_module`: imported module specifier (e.g. `express`, `../utils`)
   - `relative_level`: 0 for absolute, >0 for relative imports (`.` = 1, `..` = 2)
   - `imported_name`: specific symbol imported, or `None` for module/default
   - `local_alias`: local binding name if aliased
   - `is_type_only`: `True` for TypeScript `import type`
   - `is_commonjs`: `True` for `require()`
   - `range`: source range of the import statement

3. **`ExportFact`:**
   - `kind`: `named`, `default`, `all`, `re_export`
   - `local_name`: identifier in current file
   - `exported_name`: published name
   - `source_module`: target module if re-exporting (`export ... from ...`)
   - `is_type_only`: `True` for TypeScript `export type`
   - `is_commonjs`: `True` for `module.exports`
   - `range`: source range of the export statement

4. **`ReferenceFact`:**
   - `kind`: `call`, `name`, `attribute`, `inheritance`, `decorator`, `react_composition`
   - `source_declaration_key`: enclosing declaration `fact_key` if inside a function/class
   - `target_name`: unresolved target identifier as written in source
   - `range`: source range of the reference

5. **`FrameworkFact`:**
   - `framework_name`: e.g. `django`, `flask`, `fastapi`, `express`, `nestjs`, `nextjs`
   - `artifact_id`: UUID of the originating artifact
   - `fact_type`: e.g. `route`, `middleware`, `controller`, `module`, `service`
   - `name`: route path, controller name, or component name
   - `details`: bounded metadata dictionary (HTTP method, route template)
   - `supporting_fact_keys`: tuple of generic declaration/import/call `fact_key`s
   - `range`: source range if applicable

6. **`ManifestFact`:**
   - `manifest_type`: `package.json`, `requirements.txt`, `pyproject.toml`
   - `name`: dependency or package name
   - `version`: declared version constraint
   - `scope`: `dependencies`, `devDependencies`, `install_requires`
   - `is_dev`: boolean
   - `raw_key`: manifest configuration key
   - `range`: source range in manifest if determinable

### 3.3 SyntaxDocument

```python
@dataclass(frozen=True)
class SyntaxDocument:
    artifact_id: UUID
    path: str
    content_hash: str
    language: str                       # python, javascript, typescript, jsx, tsx
    language_version: str | None
    parser_adapter_id: str              # python-ast, tree-sitter-javascript, tree-sitter-typescript
    parser_adapter_version: str
    grammar_abi_version: int | None
    parse_status: ParseStatus           # parsed, parsed_with_errors, failed
    encoding_metadata: SourceEncodingMetadata
    facts: tuple[SyntaxFact, ...]
    diagnostic_ids: tuple[str, ...]
```

### 3.4 RepositoryInspectionResult (Root)

```python
@dataclass(frozen=True)
class RepositoryInspectionResult:
    f2_version: str = "1.0.0"
    analysis_id: UUID
    project_id: UUID
    repository_id: UUID
    snapshot_id: UUID
    analyzer_version: str
    configuration_fingerprint: str
    inventory: tuple[ArtifactInventoryEntry, ...]
    syntax_documents: tuple[SyntaxDocument, ...]
    language_detections: tuple[LanguageDetection, ...]
    runtime_detections: tuple[RuntimeDetection, ...]
    framework_detections: tuple[FrameworkDetection, ...]
    coverage: InspectionCoverage
    diagnostic_ids: tuple[str, ...]
```

---

## 4. Deterministic Ordering & Fact Keys

1. **Path Ordering:** All lists of files, inventory entries, and syntax documents are sorted lexicographically by normalized repository-relative POSIX path.
2. **Fact Ordering:** Facts within a `SyntaxDocument` are sorted deterministically by:
   `(artifact.path, range.start_byte, range.end_byte, fact_kind, fact_key)`.
3. **Fact Key Derivation:**
   `fact_key = f"{artifact_path}::{fact_kind}::{discriminator}::{start_byte}_{end_byte}"`
   Fact keys are deterministic, document-local strings. They are never database primary keys and never M4 Architecture Model logical IDs.
4. **Serialization:** Canonical serialization produces UTF-8 JSON with sorted dictionary keys, no extraneous whitespace, and no volatile timestamps.

---

## 5. Parser Execution & Isolation Sandbox

1. **Process Boundary:** All parsing runs in a dedicated OS child process.
2. **Resource Limits:**
   - Per-file hard wall-clock timeout: default 30.0 seconds.
   - Per-file maximum size: default 5 MiB (5,242,880 bytes).
   - Per-artifact syntax facts: maximum 25,000.
   - Per-analysis syntax facts: maximum 250,000.
   - Canonical serialized F2 result: maximum 50 MiB (52,428,800 bytes).
   - Hard process memory ceiling: 512 MiB.
   - Child CPU time, output file size, open file descriptor count, process count,
     and core dump size are constrained with kernel resource limits.
3. **Environment Stripping:** The child process receives an allowlisted environment with all secrets, tokens, cloud credentials, and database URLs stripped.
4. **No Network or Host-File Access:** On the supported Linux worker platform,
   a seccomp filter returns `EPERM` for socket/network syscalls and for opening or
   mutating host files after trusted parser modules and approved source codecs are
   loaded. Source is supplied only through bounded stdin IPC; repository source
   paths are never passed as filesystem capabilities.
5. **No Code Execution:** Parsers parse grammar and AST/CST only. Untrusted source code is never executed, imported, or loaded as a Python module.
6. **Descriptor Isolation:** Unrelated file descriptors and sockets are closed (`close_fds=True`).
7. **Fail-Closed Startup:** A child probe verifies the same kernel sandbox used
   for parsing. Unsupported platforms, missing seccomp support, failed resource
   limits, or ineffective network/filesystem denial make parsing unavailable;
   no weaker in-process fallback is permitted.
8. **Bounded IPC:** stdin, stdout, and stderr are handled concurrently under the
   wall-clock deadline. A child that does not read input, exceeds either output
   ceiling, or leaves an IPC thread blocked is forcibly terminated.
9. **Atomic Cap Failure:** Crossing any fact or serialized-result cap emits the
   shared `resource_limit_exceeded` diagnostic and marks the affected artifact or
   repository result failed. An incomplete or apparently successful truncated fact
   set is never returned. Per-artifact failure discards that artifact's facts while
   independent artifacts continue; aggregate cap failure rejects all accumulated
   syntax documents for that result.

---

## 6. M1 Handoff & Recovery Semantics

1. **Attempt-Scoped Handoff:** M2 produces the complete `RepositoryInspectionResult` into an attempt-scoped in-memory handoff owned by M1 orchestration.
2. **M3 Consumption:** M3 consumes the supplied F2 instance directly. M3 has no dependency on M2 and cannot trigger M2 execution.
3. **Handoff Loss & Recovery:** If worker restart or node failure loses the in-memory handoff, M1 orchestration executes an internal recovery-only rebuild of M2 using the exact same `AnalysisInput`, effective configuration fingerprint, and analyzer/grammar versions before invoking M3.
4. **Immutability of Lifecycle:** Recovery rebuilds byte-equivalent F2 without modifying already-completed M1 Stage records, without altering Analysis/Job states, and without emitting new public event types.

---

## 7. Change Control

F2 v1.0.0 is implemented, contract-tested, consumer-reviewed, owner-approved,
and frozen as of 2026-11-06. The consumer review exercised the immutable
parser-neutral result through the M3 consumer stub and confirmed that no parser
object, source byte, M2 service, or recovery operation is required by a consumer.
M3 implementation has not started. Any breaking change (modifying existing
fields, changing coordinate semantics, or altering fact keys) requires a major
version increment (`2.0.0`) and joint approval from both M2 and M3 module owners.

Freeze verification: focused M2 tests passed `71` tests with `3` platform-only
skips; the full Python regression passed `568` tests with `3` platform-only skips.
Full Ruff, strict Mypy over `171` backend source files, full-project sequential
Black, dependency consistency, and diff-whitespace checks passed.

