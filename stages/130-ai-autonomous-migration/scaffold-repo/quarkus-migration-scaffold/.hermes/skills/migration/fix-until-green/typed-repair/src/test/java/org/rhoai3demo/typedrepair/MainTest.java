package org.rhoai3demo.typedrepair;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/**
 * The executor contract end to end (V26-1/V26-2): the complete patch is staged,
 * never written into the candidate; the same inputs give the identical patch in
 * any source order; a patch outside the grant is refused and nothing staged;
 * missing target symbols on the candidate's own classpath are unresolved; the
 * retired builder API resolves only from the separate api_classpath (the
 * frozen source's own jar).
 */
class MainTest {

    @TempDir
    static Path tmp;
    static Path candidateCp;
    static Path apiCp;

    static void compile(Path out, String[] sources) throws IOException {
        Path src = Files.createTempDirectory(tmp, "src");
        List<String> files = new ArrayList<>();
        int i = 0;
        for (String s : sources) {
            String pkg = s.substring("package ".length(), s.indexOf(';')).trim();
            String name = s.replaceAll("(?s).*public (?:@interface|interface|abstract class|class) (\\w+).*", "$1");
            Path f = src.resolve(pkg.replace('.', '/')).resolve(name + ".java");
            Files.createDirectories(f.getParent());
            Files.writeString(f, s);
            files.add(f.toString());
            i++;
        }
        Files.createDirectories(out);
        JavaCompiler jc = ToolProvider.getSystemJavaCompiler();
        List<String> args = new ArrayList<>(List.of("-d", out.toString()));
        args.addAll(files);
        assertThat(jc.run(null, null, null, args.toArray(new String[0]))).isZero();
    }

    @BeforeAll
    static void classpaths() throws IOException {
        candidateCp = tmp.resolve("candidate-cp");
        apiCp = tmp.resolve("api-cp");
        List<String> cand = new ArrayList<>(List.of(Stubs.CDI));
        List<String> api = new ArrayList<>();
        for (String s : Stubs.WEB) {
            if (s.startsWith("package org.springframework.web.util")) {
                api.add(s);
            } else if (!s.startsWith("package com.other")) {
                cand.add(s);
            }
        }
        compile(candidateCp, cand.toArray(new String[0]));
        compile(apiCp, api.toArray(new String[0]));
    }

    static final String CONTROLLER = "package org.acme.ledger.rest;\n\n"
            + "import java.net.URI;\n"
            + "import org.springframework.web.util.UriComponentsBuilder;\n\n"
            + "public class TypeController {\n"
            + "    public URI add(TypeDto type, UriComponentsBuilder ucBuilder) {\n"
            + "        return ucBuilder.path(\"/api/types/{id}\").buildAndExpand(type.getId()).toUri();\n"
            + "    }\n"
            + "}\n";
    static final String DTO = "package org.acme.ledger.rest;\npublic class TypeDto { public Integer getId() { return null; } }\n";
    static final String CTRL = "src/main/java/org/acme/ledger/rest/TypeController.java";
    static final String DTOP = "src/main/java/org/acme/ledger/rest/TypeDto.java";

    static Path project(String name) throws IOException {
        Path root = tmp.resolve(name);
        Files.createDirectories(root.resolve(CTRL).getParent());
        Files.writeString(root.resolve(CTRL), CONTROLLER);
        Files.writeString(root.resolve(DTOP), DTO);
        return root;
    }

    static Path request(Path root, List<String> sources, List<String> allowed, List<String> cp, List<String> api)
            throws IOException {
        Map<String, Object> req = new LinkedHashMap<>();
        req.put("schema", Main.REQUEST_SCHEMA);
        req.put("recipe", "handler-uri-parameter");
        req.put("recipe_version", "1");
        req.put("operation", "handler-uri-parameter");
        req.put("root", root.toString());
        req.put("sources", sources);
        req.put("classpath", cp);
        req.put("api_classpath", api);
        req.put("allowed_paths", allowed);
        req.put("candidate_paths", List.of(CTRL));
        req.put("target", Map.of("sites", List.of(Map.of("path", CTRL, "type", "org.acme.ledger.rest.TypeController",
                "member", "add", "parameter", "ucBuilder"))));
        Path f = Files.createTempFile(tmp, "req", ".json");
        Main.mapper().writeValue(f.toFile(), req);
        return f;
    }

    static List<String> treeSnapshot(Path root) throws IOException {
        try (Stream<Path> s = Files.walk(root)) {
            return s.filter(Files::isRegularFile).map(p -> {
                try {
                    return root.relativize(p) + "=" + Files.readString(p, StandardCharsets.UTF_8).hashCode();
                } catch (IOException e) {
                    throw new RuntimeException(e);
                }
            }).sorted().collect(Collectors.toList());
        }
    }

    @Test
    void stagesTheCompletePatchWithoutTouchingTheCandidateAndRepeatsIdentically() throws IOException {
        Path root = project("p1");
        List<String> before = treeSnapshot(root);
        Map<String, Object> a = Main.run(request(root, List.of(CTRL, DTOP), List.of(CTRL), List.of(candidateCp.toString()),
                List.of(apiCp.toString())), tmp.resolve("out-a"));
        assertThat(a.get("outcome")).isEqualTo("applied");
        assertThat(treeSnapshot(root)).isEqualTo(before);
        String staged = Files.readString(tmp.resolve("out-a/staged").resolve(CTRL));
        assertThat(staged).contains("@Context UriInfo uriInfo")
                .contains("uriInfo.getBaseUriBuilder().path(\"/api/types/{id}\").build(Objects.toString(type.getId(), \"\"))")
                .doesNotContain("UriComponentsBuilder");
        // the same inputs in another source order: the identical patch
        List<String> reordered = new ArrayList<>(List.of(CTRL, DTOP));
        Collections.reverse(reordered);
        Main.run(request(root, reordered, List.of(CTRL), List.of(candidateCp.toString()), List.of(apiCp.toString())),
                tmp.resolve("out-b"));
        assertThat(Files.readString(tmp.resolve("out-b/patch.diff"))).isEqualTo(Files.readString(tmp.resolve("out-a/patch.diff")));
        // applied by the caller, a second application changes nothing
        Files.writeString(root.resolve(CTRL), staged);
        Map<String, Object> c = Main.run(request(root, List.of(CTRL, DTOP), List.of(CTRL),
                List.of(candidateCp.toString()), List.of(apiCp.toString())), tmp.resolve("out-c"));
        assertThat(c.get("outcome")).isEqualTo("already-in-required-form");
        assertThat(tmp.resolve("out-c/staged")).doesNotExist();
    }

    @Test
    void aPatchOutsideTheGrantIsRefusedAndNothingIsStaged() throws IOException {
        Path root = project("p2");
        Map<String, Object> r = Main.run(request(root, List.of(CTRL, DTOP), List.of(DTOP),
                List.of(candidateCp.toString()), List.of(apiCp.toString())), tmp.resolve("out-d"));
        assertThat(r.get("outcome")).isEqualTo("failed");
        assertThat(String.valueOf(r.get("reasons"))).contains("outside the issued write grant");
        assertThat(tmp.resolve("out-d/staged")).doesNotExist();
        assertThat((List<?>) r.get("changes")).isEmpty();
    }

    @Test
    void missingTargetSymbolsOnTheCandidateClasspathAreUnresolved() throws IOException {
        Path root = project("p3");
        Map<String, Object> r = Main.run(request(root, List.of(CTRL, DTOP), List.of(CTRL), List.of(apiCp.toString()),
                List.of()), tmp.resolve("out-e"));
        assertThat(r.get("outcome")).isEqualTo("unresolved");
        assertThat(String.valueOf(r.get("reasons"))).contains("jakarta.ws.rs.core.UriInfo");
    }

    @Test
    void withoutTheSourceApiJarTheBuilderIsNotAttributedAndNothingIsEdited() throws IOException {
        Path root = project("p4");
        Map<String, Object> r = Main.run(request(root, List.of(CTRL, DTOP), List.of(CTRL), List.of(candidateCp.toString()),
                List.of()), tmp.resolve("out-f"));
        assertThat(r.get("outcome")).isEqualTo("unresolved");
        assertThat(tmp.resolve("out-f/staged")).doesNotExist();
    }

    @Test
    void anUnknownRecipeIsNotApplicable() throws IOException {
        Path root = project("p5");
        Path f = request(root, List.of(CTRL), List.of(CTRL), List.of(), List.of());
        String text = Files.readString(f).replace("\"handler-uri-parameter\"", "\"no-such-recipe\"");
        Files.writeString(f, text);
        assertThat(Main.run(f, tmp.resolve("out-g")).get("outcome")).isEqualTo("not-applicable");
    }
}
