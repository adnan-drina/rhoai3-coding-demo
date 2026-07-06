# Official Doc Extraction — TPA Quick Start Guide

Extracted from Red Hat Trusted Profile Analyzer 2.2 Quick Start Guide.
Retrieved 2026-07-06.

## Chapter 1: Searching for Vulnerability Information

### Purpose

Find existing SBOM documents, VEX documents, license information, CVE
information, and advisory information for Red Hat products and packages.

### Scope Limitation

The managed service provides information only for:

- Red Hat Enterprise Linux Universal Base Image (UBI) versions 8 and 9
- The Java Quarkus library

### Prerequisites

- A Red Hat user account to access the Red Hat Hybrid Cloud Console

### Procedure

1. Open a web browser.
2. Go to the Application Services home page on the Hybrid Cloud Console.
3. Log in with credentials if prompted.
4. On the navigation menu, click **Trusted Profile Analyzer**.
5. A new browser window opens to the TPA console home page.
6. From the TPA home page navigation menu, click **Search**.
7. Enter search criteria into the dialog box.

### Results

The search results page supports filtering by Red Hat products, downloading
SBOM files, viewing package vulnerability and advisory information, and
possible remediations. The number on the Advisories tab indicates how many
times the search criteria matched.

---

## Chapter 2: Scanning a Software Bill of Materials File

### Purpose

Scan SBOM documents for vulnerability analysis. Supports:

- Standard SBOMs
- AI Bill of Materials (AIBOM) containing language models
- Cryptographic Bill of Materials (CBOM) containing keys, certificates, libraries

### Data Retention

Red Hat does not retain a copy of scanned SBOM documents.

### Prerequisites

- A Red Hat user account to access the Red Hat Hybrid Cloud Console
- An existing SBOM in one of these formats:
  - CycloneDX 1.3, 1.4, 1.5, or 1.6
  - SPDX 2.2 or 2.3

### Procedure

1. Open a web browser.
2. Go to the Application Services home page on the Hybrid Cloud Console.
3. Log in with credentials if prompted.
4. On the navigation menu, click **Trusted Profile Analyzer**.
5. A new browser window opens to the TPA console home page.
6. Click **SBOMs** from the navigation menu.
7. Click the **Generate vulnerability report** button.
8. Drag and drop the SBOM file, or click **Browse Files** and select the file.
9. After scanning completes, view the analysis summary and vulnerability
   information for included packages.

---

## Chapter 3: VS Code Dependency Analytics

### Purpose

Access RHTPA vulnerability information directly from VS Code using the
Dependency Analytics extension.

### Supported Package Managers

- Maven (`pom.xml`) — requires `mvn` in PATH
- NPM (`package.json`) — requires `npm` in PATH
- Go (`go.mod`) — requires `go` in PATH
- Python (`requirements.txt`) — requires `python3/pip3` or `python/pip` in PATH
- Gradle Groovy DSL (`build.gradle`) / Kotlin DSL (`build.gradle.kts`)
- Yarn (Berry and Classic)
- Dockerfiles — requires `syft` in PATH

### Binary Path Configuration

VS Code by default executes binaries in the system PATH. To use alternate
paths, access extension settings -> Workspace tab -> search "executable" ->
specify absolute paths for Maven, Node, Python, or Go binaries.

### Triggering a Vulnerability Report

- Open a manifest file, hover over a dependency with the wavy-red inline
  Component Analysis marker, click Quick Fix, then Detailed Vulnerability Report
- Open a manifest file and click the pie chart icon
- Right-click the manifest in Explorer view -> Red Hat Dependency Analytics Report
- From the vulnerability pop-up alert, click Open detailed vulnerability report

### Excluding Packages (exhortignore)

Use the `exhortignore` comment tag in the manifest file:

**Maven (pom.xml):**

```xml
<dependency> <!--exhortignore-->
  <groupId>...</groupId>
  <artifactId>...</artifactId>
  <version>...</version>
</dependency>
```

**Go (go.mod):**

```go
require (
    github.com/example/pkg v1.0.0 // indirect exhortignore
)
```

**Python (requirements.txt):**

```text
click==8.0.4 #exhortignore
```

**Gradle (build.gradle):**

```groovy
dependencies {
    implementation "groupId:artifactId:version" // exhortignore
}
```

---

## Chapter 4: IntelliJ Dependency Analytics

### Purpose

Access RHTPA vulnerability information from IntelliJ IDEA using the Dependency
Analytics plugin. Identical ecosystem and format support as VS Code.

### Triggering a Vulnerability Report

- Open a manifest file, hover over a flagged dependency, click
  Detailed Vulnerability Report
- Right-click the manifest in the Project window -> Dependency Analytics Report

### Excluding Packages

Same `exhortignore` comment syntax as VS Code (see Chapter 3 examples).

---

## Key Concepts Summary

| Concept | Description |
|---------|-------------|
| SBOM | Software Bill of Materials — inventory of software components |
| AIBOM | AI Bill of Materials — SBOM variant for language models |
| CBOM | Cryptographic Bill of Materials — keys, certs, crypto libraries |
| VEX | Vulnerability Exploitability eXchange — exploitability context for CVEs |
| CVE | Common Vulnerabilities and Exposures — standardized vulnerability IDs |
| CycloneDX | SBOM format (supported: 1.3, 1.4, 1.5, 1.6) |
| SPDX | SBOM format (supported: 2.2, 2.3) |
| Dependency Analytics | IDE extension/plugin for inline vulnerability scanning |
| exhortignore | Comment tag to exclude packages from Dependency Analytics scanning |
