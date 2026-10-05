#!/usr/bin/env python3
"""generator-template.py answers one upstream template from the pinned generator, bounded and read-only, and
never writes inside the product (v30 H-1/H-2, t_6fa85bc5)."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("generator_template", HERE / "generator-template.py")
GT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(GT)  # type: ignore[union-attr]

POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <properties><openapi-generator.version>7.25.0</openapi-generator.version></properties>
  <build><plugins>
    <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-compiler-plugin</artifactId><version>3.13.0</version></plugin>
    <plugin><groupId>org.openapitools</groupId><artifactId>openapi-generator-maven-plugin</artifactId>
      <version>${openapi-generator.version}</version></plugin>
  </plugins></build>
</project>
"""
TEMPLATE = "\n".join("line %d {{#required}}@NotNull{{/required}}" % n for n in range(1, 251))


def main() -> int:
    ok = True

    def check(cond, what, detail=""):
        nonlocal ok
        print(("ok " if cond else "FAIL ") + what + ("" if cond else ": %r" % (detail,)))
        ok = ok and cond

    root, repo = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
    (root / "pom.xml").write_text(POM)
    os.environ["HERMES_KANBAN_TASK"] = "t_6fa85bc5"
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))

    gens = GT.generators(root / "pom.xml")
    check([g["version"] for g in gens] == ["7.25.0"], "the generator version is the pom's, its property resolved", gens)

    rc, text = GT.answer(root, template="JavaJaxRS/spec/beanValidation.mustache", repo=repo)
    check(rc == 2 and ".derived/scratch/t_6fa85bc5" in text and "/projects/modernized" not in text,
          "jar absent: the fetch command targets the card's sanctioned scratch, nothing is downloaded", text)

    jar = GT.codegen_jar(gens[0], repo)
    jar.parent.mkdir(parents=True)
    with zipfile.ZipFile(str(jar), "w") as z:
        z.writestr("JavaJaxRS/spec/beanValidation.mustache", TEMPLATE)
        z.writestr("JavaJaxRS/spec/pojo.mustache", "pojo")
        z.writestr("Java/beanValidation.mustache", "other")
    rc, text = GT.answer(root, template="JavaJaxRS/spec/beanValidation.mustache", repo=repo)
    check(rc == 0 and "7.25.0" in text and "lines 1-200 of 250" in text and "--lines 201:250" in text,
          "the template text is bounded and names the version and the rest", text.splitlines()[0])
    rc, text = GT.answer(root, template="JavaJaxRS/spec/beanValidation.mustache", lines="240:250", repo=repo)
    check(rc == 0 and "line 250" in text and "line 239" not in text, "a line range answers exactly that range")
    rc, text = GT.answer(root, template="JavaJaxRS/spec/beanValidation.mustache", lines="1:1000", repo=repo)
    body = [x for x in text.splitlines()[1:]]
    check(rc == 0 and len(body) == GT.LIMIT_LINES and "--lines 201:250" in text,
          "an explicit range is still one page at most, with the continuation named", (len(body), text.splitlines()[0]))
    for bad in ("x:y", "300:400", "50:10"):
        rc, text = GT.answer(root, template="JavaJaxRS/spec/beanValidation.mustache", lines=bad, repo=repo)
        check(rc == 1 and "--lines 1:" in text, "a malformed or empty range is answered with a usable range (%s)" % bad, text)
    rc, text = GT.answer(root, listing="JavaJaxRS/spec/", repo=repo)
    check(rc == 0 and "2 entr" in text and "pojo.mustache" in text, "a prefix lists the templates", text)
    rc, text = GT.answer(root, listing="Nope/", repo=repo)
    check(rc == 0 and "0 entries" in text and "do not repeat" in text, "an empty listing is stated as an answer", text)
    rc, text = GT.answer(root, template="spec/beanValidation.mustache", repo=repo)
    check(rc == 1 and "JavaJaxRS/spec/beanValidation.mustache" in text, "a wrong path names the same file name's real paths", text)
    after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    check(before == after, "the product root is unchanged by every query", (before, after))
    (root / "pom.xml").write_text(POM.replace("openapi-generator-maven-plugin", "something-else"))
    rc, text = GT.answer(root, template="x", repo=repo)
    check(rc == 1 and "0 catalogued generator" in text, "no generator declared: stated, nothing guessed", text)
    sys.path.insert(0, str(HERE))
    import brief as B
    lines = B.scratch_lines({"write_set": ["src/main/resources/openapi-templates/beanValidation.mustache"]})
    check(any(".derived/scratch/t_6fa85bc5/" in x for x in lines) and any("generator-template.py" in x for x in lines),
          "the brief names the sanctioned scratch and, for a template card, the lookup", lines)
    check(len(B.scratch_lines({"write_set": ["src/main/java/A.java"]})) == 1, "a card without templates gets only the scratch line")
    from _loop_common import is_product_path
    check(not is_product_path(GT.scratch_dir() + "/openapi-generator-7.25.0.jar") and is_product_path(".tmp-og/x.jar"),
          "the sanctioned scratch is not a product path (no drift, no park); the v30 location was")
    # specimen/generator-agnostic: the plugin -> codegen mapping is the catalog's; a renamed, invented generator
    # described by its own catalog row is served the same way, and an uncatalogued one is not guessed
    cat = {"build_plugins": {"com.acme.build:contract-codegen-plugin": {"template_source": {"artifact": "com.acme.build:contract-codegen"}}}}
    other = Path(tempfile.mkdtemp())
    (other / "pom.xml").write_text(POM.replace("org.openapitools", "com.acme.build")
                                   .replace("openapi-generator-maven-plugin", "contract-codegen-plugin")
                                   .replace("openapi-generator.version", "codegen.version"))
    g2 = GT.generators(other / "pom.xml", cat)
    check([(g["codegen_group"], g["codegen_artifact"], g["version"]) for g in g2] == [("com.acme.build", "contract-codegen", "7.25.0")],
          "a renamed generator is resolved from its catalog row", g2)
    jar2 = GT.codegen_jar(g2[0], repo)
    jar2.parent.mkdir(parents=True)
    with zipfile.ZipFile(str(jar2), "w") as z:
        z.writestr("Server/model.mustache", "line 1\nline 2")
    rc, text = GT.answer(other, template="Server/model.mustache", repo=repo, catalog=cat)
    check(rc == 0 and "com.acme.build:contract-codegen:7.25.0" in text and "line 2" in text,
          "its template is served from its own codegen artifact", text)
    rc, text = GT.answer(other, template="Server/model.mustache", repo=repo, catalog={"build_plugins": {}})
    check(rc == 1 and "not guessed" in text, "an uncatalogued generator plugin is refused, never guessed", text)
    check(GT.codegen_map().get(("org.openapitools", "openapi-generator-maven-plugin")) == ("org.openapitools", "openapi-generator"),
          "the golden catalog describes the OpenAPI generator's template source")
    print("OK: generator-template" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
