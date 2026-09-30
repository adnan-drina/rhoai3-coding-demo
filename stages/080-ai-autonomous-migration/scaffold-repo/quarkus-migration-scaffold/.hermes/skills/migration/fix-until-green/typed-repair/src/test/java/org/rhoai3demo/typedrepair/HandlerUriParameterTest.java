package org.rhoai3demo.typedrepair;

import static org.assertj.core.api.Assertions.assertThat;
import static org.openrewrite.java.Assertions.java;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.openrewrite.java.JavaParser;
import org.openrewrite.test.RecipeSpec;
import org.openrewrite.test.RewriteTest;
import org.openrewrite.test.TypeValidation;

/**
 * V26-2 qualification of handler-uri-parameter: before/after, argument order
 * and null tolerance, unchanged negatives, second application, same-named
 * types, renamed packages, unsupported builder uses and missing type facts
 * refused before any edit.
 */
class HandlerUriParameterTest implements RewriteTest {

    @Override
    public void defaults(RecipeSpec spec) {
        spec.parser(JavaParser.fromJavaVersion().dependsOn(Stubs.WEB)).validateRecipeSerialization(false);
    }

    static String path(String pkg) {
        return "src/main/java/" + pkg.replace('.', '/') + "/rest/TypeController.java";
    }

    static HandlerUriParameter recipe(String pkg, Report r, String member) {
        return new HandlerUriParameter(List.of(new HandlerUriParameter.Site(path(pkg), pkg + ".rest.TypeController", member,
                "ucBuilder")), r);
    }

    static String dto(String pkg) {
        return "package " + pkg + ".rest; public class TypeDto { public Integer getId() { return null; } "
                + "public String getName() { return null; } }";
    }

    @ParameterizedTest
    @CsvSource({"org.springframework.samples.petclinic", "com.example.ledger", "io.acme.depot.api"})
    void translatesTheParameterAndItsLocationTogether(String pkg) {
        Report r = new Report();
        rewriteRun(spec -> spec.recipe(recipe(pkg, r, "add")),
                java(dto(pkg), s -> s.path("src/main/java/" + pkg.replace('.', '/') + "/rest/TypeDto.java")),
                java("package " + pkg + ".rest;\n\n"
                                + "import org.springframework.http.HttpHeaders;\n"
                                + "import org.springframework.web.bind.annotation.PostMapping;\n"
                                + "import org.springframework.web.bind.annotation.RequestBody;\n"
                                + "import org.springframework.web.util.UriComponentsBuilder;\n\n"
                                + "public class TypeController {\n"
                                + "    @PostMapping(\"\")\n"
                                + "    public HttpHeaders add(@RequestBody TypeDto type, UriComponentsBuilder ucBuilder) {\n"
                                + "        HttpHeaders headers = new HttpHeaders();\n"
                                + "        headers.setLocation(ucBuilder.path(\"/api/types/{id}\").buildAndExpand(type.getId()).toUri());\n"
                                + "        return headers;\n"
                                + "    }\n"
                                + "}\n",
                        "package " + pkg + ".rest;\n\n"
                                + "import jakarta.ws.rs.core.Context;\n"
                                + "import jakarta.ws.rs.core.UriInfo;\n"
                                + "import org.springframework.http.HttpHeaders;\n"
                                + "import org.springframework.web.bind.annotation.PostMapping;\n"
                                + "import org.springframework.web.bind.annotation.RequestBody;\n\n"
                                + "import java.util.Objects;\n\n"
                                + "public class TypeController {\n"
                                + "    @PostMapping(\"\")\n"
                                + "    public HttpHeaders add(@RequestBody TypeDto type, @Context UriInfo uriInfo) {\n"
                                + "        HttpHeaders headers = new HttpHeaders();\n"
                                + "        headers.setLocation(uriInfo.getBaseUriBuilder().path(\"/api/types/{id}\").build(Objects.toString(type.getId(), \"\")));\n"
                                + "        return headers;\n"
                                + "    }\n"
                                + "}\n",
                        s -> s.path(path(pkg))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.APPLIED);
    }

    @Test
    void keepsTemplatesArgumentOrderAndLiteralArguments() {
        String pkg = "org.acme.ledger";
        Report r = new Report();
        rewriteRun(spec -> spec.recipe(recipe(pkg, r, "add")),
                java(dto(pkg), s -> s.path("src/main/java/org/acme/ledger/rest/TypeDto.java")),
                java("package org.acme.ledger.rest;\n\n"
                                + "import java.net.URI;\n"
                                + "import java.util.Objects;\n"
                                + "import org.springframework.web.util.UriComponentsBuilder;\n\n"
                                + "public class TypeController {\n"
                                + "    static final String BASE = \"/api/books\";\n"
                                + "    public URI add(TypeDto type, int shelf, UriComponentsBuilder ucBuilder) {\n"
                                + "        return ucBuilder.path(BASE).path(\"/{shelf}/{name}/{kind}\").buildAndExpand(shelf, type.getName(), \"x\").toUri();\n"
                                + "    }\n"
                                + "}\n",
                        "package org.acme.ledger.rest;\n\n"
                                + "import java.net.URI;\n"
                                + "import java.util.Objects;\n\n"
                                + "import jakarta.ws.rs.core.Context;\n"
                                + "import jakarta.ws.rs.core.UriInfo;\n\n"
                                + "public class TypeController {\n"
                                + "    static final String BASE = \"/api/books\";\n"
                                + "    public URI add(TypeDto type, int shelf, @Context UriInfo uriInfo) {\n"
                                + "        return uriInfo.getBaseUriBuilder().path(BASE).path(\"/{shelf}/{name}/{kind}\").build(Objects.toString(shelf, \"\"), Objects.toString(type.getName(), \"\"), \"x\");\n"
                                + "    }\n"
                                + "}\n",
                        s -> s.path(path(pkg))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.APPLIED);
    }

    static final String DONE = "package org.acme.ledger.rest;\n\n"
            + "import jakarta.ws.rs.core.Context;\n"
            + "import jakarta.ws.rs.core.UriInfo;\n\n"
            + "import java.net.URI;\n"
            + "import java.util.Objects;\n\n"
            + "public class TypeController {\n"
            + "    public URI add(TypeDto type, @Context UriInfo uriInfo) {\n"
            + "        return uriInfo.getBaseUriBuilder().path(\"/api/types/{id}\").build(Objects.toString(type.getId(), \"\"));\n"
            + "    }\n"
            + "}\n";

    @Test
    void alreadyTranslatedIsKeptAndSaysSo() {
        Report r = new Report();
        rewriteRun(spec -> spec.recipe(recipe("org.acme.ledger", r, "add")),
                java(dto("org.acme.ledger"), s -> s.path("src/main/java/org/acme/ledger/rest/TypeDto.java")),
                java(DONE, s -> s.path(path("org.acme.ledger"))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.ALREADY);
    }

    static String using(String body) {
        return "package org.acme.ledger.rest;\n\n"
                + "import java.net.URI;\n"
                + "import org.springframework.web.util.UriComponentsBuilder;\n\n"
                + "public class TypeController {\n"
                + "    public URI add(TypeDto type, UriComponentsBuilder ucBuilder) {\n"
                + body
                + "    }\n"
                + "    URI helper(UriComponentsBuilder b) { return null; }\n"
                + "}\n";
    }

    void refused(String body, String reasonFragment) {
        Report r = new Report();
        rewriteRun(spec -> spec.recipe(recipe("org.acme.ledger", r, "add")),
                java(dto("org.acme.ledger"), s -> s.path("src/main/java/org/acme/ledger/rest/TypeDto.java")),
                java(using(body), s -> s.path(path("org.acme.ledger"))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.UNRESOLVED);
        assertThat(String.join(" ", r.reasons())).contains(reasonFragment);
    }

    @Test
    void aBuilderPassedElsewhereIsRefusedWithoutPartialEdit() {
        refused("        URI u = ucBuilder.path(\"/a/{id}\").buildAndExpand(type.getId()).toUri();\n"
                + "        return helper(ucBuilder);\n", "outside <builder>.path");
    }

    @Test
    void aMapExpansionIsRefused() {
        refused("        return ucBuilder.path(\"/a/{id}\").buildAndExpand(java.util.Map.of(\"id\", 1)).toUri();\n",
                "Map expansion is unsupported");
    }

    @Test
    void aQueryParameterIsRefused() {
        refused("        return ucBuilder.path(\"/a\").queryParam(\"q\", 1).buildAndExpand().toUri();\n",
                "outside <builder>.path");
    }

    @Test
    void anUnusedBuilderIsReplacedAndNothingElseChanges() {
        Report r = new Report();
        String before = "package org.acme.ledger.rest;\n\n"
                + "import java.net.URI;\n"
                + "import org.springframework.web.util.UriComponentsBuilder;\n\n"
                + "public class TypeController {\n"
                + "    public URI add(TypeDto type, UriComponentsBuilder ucBuilder) {\n"
                + "        return null;\n"
                + "    }\n"
                + "}\n";
        String after = "package org.acme.ledger.rest;\n\n"
                + "import java.net.URI;\n\n"
                + "import jakarta.ws.rs.core.Context;\n"
                + "import jakarta.ws.rs.core.UriInfo;\n\n"
                + "public class TypeController {\n"
                + "    public URI add(TypeDto type, @Context UriInfo uriInfo) {\n"
                + "        return null;\n"
                + "    }\n"
                + "}\n";
        rewriteRun(spec -> spec.recipe(recipe("org.acme.ledger", r, "add")),
                java(dto("org.acme.ledger"), s -> s.path("src/main/java/org/acme/ledger/rest/TypeDto.java")),
                java(before, after, s -> s.path(path("org.acme.ledger"))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.APPLIED);
    }

    @Test
    void aNameConflictIsRefused() {
        refused("        Object uriInfo = null;\n"
                + "        return ucBuilder.path(\"/a/{id}\").buildAndExpand(type.getId()).toUri();\n", "already names uriInfo");
    }

    @Test
    void aSameNamedTypeFromAnotherPackageIsNotTheBuilder() {
        Report r = new Report();
        String other = "package org.acme.ledger.rest;\n\n"
                + "import com.other.web.UriComponentsBuilder;\n\n"
                + "public class TypeController {\n"
                + "    public Object add(TypeDto type, UriComponentsBuilder ucBuilder) {\n"
                + "        return ucBuilder.path(\"/a\");\n"
                + "    }\n"
                + "}\n";
        rewriteRun(spec -> spec.recipe(recipe("org.acme.ledger", r, "add")),
                java(dto("org.acme.ledger"), s -> s.path("src/main/java/org/acme/ledger/rest/TypeDto.java")),
                java(other, s -> s.path(path("org.acme.ledger"))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.UNRESOLVED);
        assertThat(String.join(" ", r.reasons())).contains("com.other.web.UriComponentsBuilder, not");
    }

    @Test
    void aHelperTakingTheBuilderIsNotAHandlerSiteAndStaysUnchanged() {
        String pkg = "org.acme.ledger";
        Report r = new Report();
        String before = "package org.acme.ledger.rest;\n\n"
                + "import java.net.URI;\n"
                + "import org.springframework.web.util.UriComponentsBuilder;\n\n"
                + "public class TypeController {\n"
                + "    public URI add(TypeDto type, UriComponentsBuilder ucBuilder) {\n"
                + "        return ucBuilder.path(\"/a/{id}\").buildAndExpand(type.getId()).toUri();\n"
                + "    }\n"
                + "    URI helper(UriComponentsBuilder ucBuilder) { return ucBuilder.path(\"/h\").buildAndExpand().toUri(); }\n"
                + "}\n";
        String after = "package org.acme.ledger.rest;\n\n"
                + "import java.net.URI;\n"
                + "import java.util.Objects;\n\n"
                + "import jakarta.ws.rs.core.Context;\n"
                + "import jakarta.ws.rs.core.UriInfo;\n"
                + "import org.springframework.web.util.UriComponentsBuilder;\n\n"
                + "public class TypeController {\n"
                + "    public URI add(TypeDto type, @Context UriInfo uriInfo) {\n"
                + "        return uriInfo.getBaseUriBuilder().path(\"/a/{id}\").build(Objects.toString(type.getId(), \"\"));\n"
                + "    }\n"
                + "    URI helper(UriComponentsBuilder ucBuilder) { return ucBuilder.path(\"/h\").buildAndExpand().toUri(); }\n"
                + "}\n";
        rewriteRun(spec -> spec.recipe(recipe(pkg, r, "add")),
                java(dto(pkg), s -> s.path("src/main/java/org/acme/ledger/rest/TypeDto.java")),
                java(before, after, s -> s.path(path(pkg))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.APPLIED);
    }

    @Test
    void theBuilderApiMissingFromTheClasspathIsUnresolved() {
        Report r = new Report();
        String src = "package org.acme.ledger.rest;\n\n"
                + "import java.net.URI;\n"
                + "import org.springframework.web.util.UriComponentsBuilder;\n\n"
                + "public class TypeController {\n"
                + "    public URI add(TypeDto type, UriComponentsBuilder ucBuilder) {\n"
                + "        return ucBuilder.path(\"/a/{id}\").buildAndExpand(type.getId()).toUri();\n"
                + "    }\n"
                + "}\n";
        rewriteRun(spec -> spec.recipe(recipe("org.acme.ledger", r, "add"))
                        .parser(JavaParser.fromJavaVersion().dependsOn(
                                "package jakarta.ws.rs.core; public interface UriInfo {}"))
                        .typeValidationOptions(TypeValidation.none()),
                java(dto("org.acme.ledger"), s -> s.path("src/main/java/org/acme/ledger/rest/TypeDto.java")),
                java(src, s -> s.path(path("org.acme.ledger"))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.UNRESOLVED);
    }

    @Test
    void aSiteThatDoesNotExistIsUnresolved() {
        Report r = new Report();
        rewriteRun(spec -> spec.recipe(recipe("org.acme.ledger", r, "create")),
                java(dto("org.acme.ledger"), s -> s.path("src/main/java/org/acme/ledger/rest/TypeDto.java")),
                java(DONE, s -> s.path(path("org.acme.ledger"))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.UNRESOLVED);
    }
}
